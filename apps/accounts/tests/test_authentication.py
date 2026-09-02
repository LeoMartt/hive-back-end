import uuid
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
        self.assertEqual(response.data["nome"], CLAIMS_VALIDOS["name"])
        self.assertEqual(response.data["iniciais"], "TU")
        self.assertEqual(Usuario.objects.filter(entra_object_id=CLAIMS_VALIDOS["oid"]).count(), 1)

        usuario = Usuario.objects.get(entra_object_id=CLAIMS_VALIDOS["oid"])
        self.assertIsInstance(usuario.id, uuid.UUID)
        self.assertIsInstance(usuario.entra_object_id, uuid.UUID)
        self.assertEqual(usuario.username, f"entra_{CLAIMS_VALIDOS['oid']}")
        self.assertEqual(usuario.first_name, CLAIMS_VALIDOS["name"])
        self.assertEqual(usuario.iniciais, "TU")
        self.assertFalse(usuario.has_usable_password())

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

    @patch("apps.accounts.authentication.EntraTokenValidator.validar")
    def test_claims_com_oid_invalido_retorna_401(self, mock_validar):
        mock_validar.return_value = {**CLAIMS_VALIDOS, "oid": "oid-invalido"}

        response = self._autenticar()

        self.assertEqual(response.status_code, 401)

    @patch("apps.accounts.authentication.EntraTokenValidator.validar")
    def test_claims_sem_email_retorna_401(self, mock_validar):
        mock_validar.return_value = {"oid": CLAIMS_VALIDOS["oid"], "name": "Sem Email"}

        response = self._autenticar()

        self.assertEqual(response.status_code, 401)

    @patch("apps.accounts.authentication.EntraTokenValidator.validar")
    def test_email_existente_com_outro_oid_retorna_401(self, mock_validar):
        Usuario.objects.create_user(
            username="admin-dev",
            email=CLAIMS_VALIDOS["preferred_username"],
            password="senha-local-dev",
        )
        mock_validar.return_value = CLAIMS_VALIDOS

        response = self._autenticar()

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Usuario.objects.filter(entra_object_id=CLAIMS_VALIDOS["oid"]).exists())

    @patch("apps.accounts.authentication.EntraTokenValidator.validar")
    def test_iniciais_usam_email_quando_nome_nao_vem_no_token(self, mock_validar):
        mock_validar.return_value = {
            "oid": "22222222-2222-2222-2222-222222222222",
            "preferred_username": "qa@fumep.edu.br",
        }

        response = self._autenticar()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["iniciais"], "QA")
