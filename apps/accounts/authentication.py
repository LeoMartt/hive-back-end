import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
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

        if not token.strip():
            raise AuthenticationFailed("Access Token não informado.")

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

        try:
            entra_object_id = uuid.UUID(str(entra_object_id))
        except (AttributeError, TypeError, ValueError) as exc:
            raise AuthenticationFailed("Claim 'oid' do Access Token é inválido.") from exc

        email = (claims.get("preferred_username") or claims.get("email") or "").strip()
        if not email:
            raise AuthenticationFailed("Access Token não contém um e-mail válido.")

        email = Usuario.objects.normalize_email(email)
        nome_completo = claims.get("name", "").strip()

        conflito_email = (
            Usuario.objects.filter(email__iexact=email)
            .exclude(entra_object_id=entra_object_id)
            .exists()
        )
        if conflito_email:
            raise AuthenticationFailed(
                "Já existe um usuário com este e-mail, mas vinculado a outra identidade."
            )

        defaults = {
            "username": f"entra_{entra_object_id}",
            "email": email,
            "first_name": nome_completo,
            "iniciais": self._gerar_iniciais(nome_completo, email),
            "is_active": True,
        }

        try:
            with transaction.atomic():
                usuario, criado = Usuario.objects.update_or_create(
                    entra_object_id=entra_object_id,
                    defaults=defaults,
                )

                if criado:
                    usuario.set_unusable_password()
                    usuario.save(update_fields=["password"])
        except IntegrityError as exc:
            raise AuthenticationFailed("Não foi possível provisionar o usuário.") from exc

        return usuario

    @staticmethod
    def _gerar_iniciais(nome: str, email: str) -> str:
        partes = nome.split()

        if len(partes) >= 2:
            return f"{partes[0][0]}{partes[-1][0]}".upper()

        if len(partes) == 1:
            return partes[0][:2].upper()

        return email.split("@")[0][:2].upper()

    def authenticate_header(self, request):
        return self.keyword
