"""Validação de Access Tokens emitidos pelo Microsoft Entra ID.

O frontend (React + MSAL) obtém o Access Token diretamente do Entra ID. O backend nunca
faz login — só valida o token recebido em cada requisição, conferindo assinatura, emissor,
audiência e expiração contra as chaves públicas (JWKS) do tenant.
"""

from functools import lru_cache

import jwt
from jwt import PyJWKClient

from .exceptions import TokenInvalido

ALGORITMOS_ACEITOS = ["RS256"]


@lru_cache(maxsize=1)
def _jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


class EntraTokenValidator:
    """Valida um Access Token do Entra ID para um tenant/audiência específicos."""

    def __init__(self, tenant_id: str, client_id: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.audiences = (client_id, f"api://{client_id}")
        self.issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        self.jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"

    def validar(self, token: str) -> dict:
        """Retorna os claims do token se ele for válido, ou levanta TokenInvalido."""
        try:
            signing_key = _jwk_client(self.jwks_url).get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=ALGORITMOS_ACEITOS,
                audience=self.audiences,
                issuer=self.issuer,
            )
        except jwt.PyJWTError as exc:
            raise TokenInvalido(str(exc)) from exc
