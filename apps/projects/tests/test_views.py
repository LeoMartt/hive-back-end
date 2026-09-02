from django.urls import reverse
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario

from ..models import Membership, Papel, Project


class ProjectListViewTests(APITestCase):
    url = reverse("projects:list")

    @classmethod
    def setUpTestData(cls):
        cls.gestor = Usuario.objects.create_user(
            username="gestor",
            email="gestor@fumep.edu.br",
            password="senha-local-dev",
            first_name="Gestor Um",
            iniciais="GU",
        )
        cls.outro_usuario = Usuario.objects.create_user(
            username="outro",
            email="outro@fumep.edu.br",
            password="senha-local-dev",
            first_name="Outro Usuário",
            iniciais="OU",
        )
        cls.admin = Usuario.objects.create_superuser(
            username="admin",
            email="admin@fumep.edu.br",
            password="senha-local-dev",
        )
        cls.papel_gestor = Papel.objects.get(codigo=Papel.Codigo.GESTOR)
        cls.papel_tester = Papel.objects.get(codigo=Papel.Codigo.TESTER)
        cls.crm = Project.objects.create(
            nome="CRM Homologação Comercial",
            modo=Project.Modo.UAT,
            nivel1_nome="Área",
            nivel2_nome="Cenário",
            criado_por=cls.gestor,
        )
        cls.erp = Project.objects.create(
            nome="ERP Cutover",
            modo=Project.Modo.CUTOVER,
            nivel1_nome="Módulo",
            criado_por=cls.outro_usuario,
        )
        Membership.objects.create(
            usuario=cls.gestor,
            projeto=cls.crm,
            papel=cls.papel_gestor,
        )
        Membership.objects.create(
            usuario=cls.gestor,
            projeto=cls.crm,
            papel=cls.papel_tester,
        )
        Membership.objects.create(
            usuario=cls.outro_usuario,
            projeto=cls.erp,
            papel=cls.papel_gestor,
        )

    def test_sem_autenticacao_retorna_401(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_lista_apenas_projetos_do_usuario_autenticado(self):
        self.client.force_authenticate(user=self.gestor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        project = response.data[0]
        self.assertEqual(project["id"], str(self.crm.id))
        self.assertEqual(project["name"], self.crm.nome)
        self.assertEqual(project["mode"], "uat")
        self.assertEqual(project["activityCount"], 0)
        self.assertEqual(project["completedCount"], 0)
        self.assertEqual(project["hierarchyLevels"], ["Área", "Cenário"])
        self.assertEqual(project["progressPercent"], 0)
        self.assertIsNone(project["spi"])
        self.assertEqual(parse_datetime(project["updatedAt"]), self.crm.atualizado_em)
        self.assertEqual(
            project["team"],
            [
                {
                    "id": str(self.gestor.id),
                    "initials": "GU",
                    "name": "Gestor Um",
                    "email": "gestor@fumep.edu.br",
                    "role": "Gestor de Projetos",
                },
                {
                    "id": str(self.gestor.id),
                    "initials": "GU",
                    "name": "Gestor Um",
                    "email": "gestor@fumep.edu.br",
                    "role": "Tester",
                },
            ],
        )

    def test_lista_tambem_funciona_sem_barra_final_para_frontend(self):
        self.client.force_authenticate(user=self.gestor)

        response = self.client.get("/api/projects")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_staff_lista_todos_os_projetos(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual({project["name"] for project in response.data}, {self.crm.nome, self.erp.nome})
