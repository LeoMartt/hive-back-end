from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APITestCase

from integrations.microsoft.entra.exceptions import TokenInvalido

from ..models import Usuario

CLAIMS_VALIDOS = {
    "oid": "11111111-1111-1111-1111-111111111111",
    "preferred_username": "tester@fumep.edu.br",
    "name": "Tester Um",
}


class MeViewTests(APITestCase):
    url = reverse("accounts:me")

    def _autenticar(self, token="token-qualquer"):
        return self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_sem_header_authorization_retorna_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    @patch("apps.accounts.authentication.EntraTokenValidator.validar")
    def test_token_invalido_retorna_401(self, mock_validar):
        mock_validar.side_effect = TokenInvalido("assinatura inválida")

        response = self._autenticar()

        self.assertEqual(response.status_code, 401)

    @patch("apps.accounts.authentication.EntraTokenValidator.validar")
    def test_token_valido_autoprovisiona_usuario(self, mock_validar):
        mock_validar.return_value = CLAIMS_VALIDOS

        response = self._autenticar()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], CLAIMS_VALIDOS["preferred_username"])
        self.assertEqual(response.data["entra_object_id"], CLAIMS_VALIDOS["oid"])
        self.assertEqual(Usuario.objects.filter(entra_object_id=CLAIMS_VALIDOS["oid"]).count(), 1)

    @patch("apps.accounts.authentication.EntraTokenValidator.validar")
    def test_segundo_acesso_reaproveita_usuario_existente(self, mock_validar):
        mock_validar.return_value = CLAIMS_VALIDOS

        self._autenticar()
        self._autenticar()

        self.assertEqual(Usuario.objects.filter(entra_object_id=CLAIMS_VALIDOS["oid"]).count(), 1)

    @patch("apps.accounts.authentication.EntraTokenValidator.validar")
    def test_claims_sem_oid_retorna_401(self, mock_validar):
        mock_validar.return_value = {"name": "Sem OID"}

        response = self._autenticar()

        self.assertEqual(response.status_code, 401)
