from unittest.mock import MagicMock, patch

import jwt
from django.test import SimpleTestCase

from integrations.microsoft.entra.exceptions import TokenInvalido
from integrations.microsoft.entra.validator import EntraTokenValidator

TENANT_ID = "22222222-2222-2222-2222-222222222222"
CLIENT_ID = "33333333-3333-3333-3333-333333333333"


class EntraTokenValidatorTests(SimpleTestCase):
    def setUp(self):
        self.validator = EntraTokenValidator(tenant_id=TENANT_ID, client_id=CLIENT_ID)

    @patch("integrations.microsoft.entra.validator.jwt.decode")
    @patch("integrations.microsoft.entra.validator._jwk_client")
    def test_token_valido_retorna_claims(self, mock_jwk_client, mock_decode):
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="chave")
        mock_decode.return_value = {"oid": "abc", "name": "Fulano"}

        claims = self.validator.validar("token-valido")

        self.assertEqual(claims, {"oid": "abc", "name": "Fulano"})
        mock_decode.assert_called_once_with(
            "token-valido",
            "chave",
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        )

    @patch("integrations.microsoft.entra.validator.jwt.decode")
    @patch("integrations.microsoft.entra.validator._jwk_client")
    def test_token_expirado_levanta_token_invalido(self, mock_jwk_client, mock_decode):
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="chave")
        mock_decode.side_effect = jwt.ExpiredSignatureError("expirado")

        with self.assertRaises(TokenInvalido):
            self.validator.validar("token-expirado")

    @patch("integrations.microsoft.entra.validator.jwt.decode")
    @patch("integrations.microsoft.entra.validator._jwk_client")
    def test_audience_invalida_levanta_token_invalido(self, mock_jwk_client, mock_decode):
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="chave")
        mock_decode.side_effect = jwt.InvalidAudienceError("audience errada")

        with self.assertRaises(TokenInvalido):
            self.validator.validar("token-audience-errada")

    @patch("integrations.microsoft.entra.validator._jwk_client")
    def test_chave_de_assinatura_nao_encontrada_levanta_token_invalido(self, mock_jwk_client):
        mock_jwk_client.return_value.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientError(
            "chave não encontrada"
        )

        with self.assertRaises(TokenInvalido):
            self.validator.validar("token-sem-chave")
