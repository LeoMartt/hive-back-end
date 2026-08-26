from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from integrations.microsoft.entra.exceptions import TokenInvalido
from integrations.microsoft.entra.validator import EntraTokenValidator

from .models import Usuario


class EntraIDAuthentication(BaseAuthentication):
    """Autentica requisições via Access Token do Microsoft Entra ID.

    Espera o header `Authorization: Bearer <token>`. O usuário é auto-provisionado
    no primeiro acesso a partir dos claims do token (não existe cadastro manual).
    """

    keyword = "Bearer"

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header:
            return None

        try:
            keyword, token = header.split(" ", 1)
        except ValueError:
            raise AuthenticationFailed("Header Authorization mal formatado.")

        if keyword.lower() != self.keyword.lower():
            return None

        validator = EntraTokenValidator(
            tenant_id=settings.AZURE_TENANT_ID,
            client_id=settings.AZURE_CLIENT_ID,
        )
        try:
            claims = validator.validar(token)
        except TokenInvalido as exc:
            raise AuthenticationFailed(f"Access Token inválido: {exc}") from exc

        usuario = self._obter_ou_criar_usuario(claims)
        return (usuario, token)

    def _obter_ou_criar_usuario(self, claims: dict) -> Usuario:
        entra_object_id = claims.get("oid")
        if not entra_object_id:
            raise AuthenticationFailed("Access Token não contém o claim 'oid'.")

        email = claims.get("preferred_username") or claims.get("email") or ""
        nome_completo = claims.get("name", "")

        usuario, _ = Usuario.objects.update_or_create(
            entra_object_id=entra_object_id,
            defaults={
                "username": entra_object_id,
                "email": email,
                "first_name": nome_completo,
            },
        )
        return usuario

    def authenticate_header(self, request):
        return self.keyword
