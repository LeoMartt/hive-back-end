from uuid import uuid4

from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario

from ..models import Membership, NoHierarquia, Papel, Project


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

    def test_rota_sem_barra_final_nao_e_contrato_da_api(self):
        self.client.force_authenticate(user=self.gestor)

        response = self.client.get("/api/projects")

        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.url.endswith("/api/projects/"))

    def test_staff_lista_todos_os_projetos_ativos(self):
        self.client.force_authenticate(user=self.admin)
        self.crm.ativo = False
        self.crm.save(update_fields=["ativo"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual({project["name"] for project in response.data}, {self.erp.nome})

    def test_lista_ignora_projetos_inativos(self):
        self.client.force_authenticate(user=self.gestor)
        self.crm.ativo = False
        self.crm.save(update_fields=["ativo"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_lista_ordena_por_criacao_mais_recente(self):
        self.client.force_authenticate(user=self.gestor)
        mais_novo = Project.objects.create(
            nome="Projeto Mais Novo",
            modo=Project.Modo.CUTOVER,
            nivel1_nome="Frente",
            criado_por=self.gestor,
        )
        Membership.objects.create(
            usuario=self.gestor,
            projeto=mais_novo,
            papel=self.papel_gestor,
        )
        Project.objects.filter(id=mais_novo.id).update(criado_em=timezone.now())

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], str(mais_novo.id))

    def test_lista_paginar_quando_usuario_tem_mais_de_dez_projetos(self):
        self.client.force_authenticate(user=self.gestor)
        for indice in range(10):
            project = Project.objects.create(
                nome=f"Projeto Extra {indice}",
                modo=Project.Modo.UAT,
                nivel1_nome="Área",
                nivel2_nome="Cenário",
                criado_por=self.gestor,
            )
            Membership.objects.create(
                usuario=self.gestor,
                projeto=project,
                papel=self.papel_gestor,
            )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 11)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertEqual(len(response.data["results"]), 10)

    def test_cria_projeto_com_memberships_do_payload_e_gestor_criador(self):
        self.client.force_authenticate(user=self.gestor)
        entra_id = uuid4()
        payload = {
            "name": "Portal RH",
            "description": "Homologação do onboarding",
            "mode": "uat",
            "hierarchyLevels": ["Área", "Cenário"],
            "team": [
                {
                    "id": str(entra_id),
                    "initials": "DU",
                    "name": "Dev Um",
                    "email": "dev.um@fumep.edu.br",
                    "role": "Desenvolvedor",
                }
            ],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        project = Project.objects.get(nome="Portal RH")
        self.assertEqual(project.criado_por, self.gestor)
        self.assertEqual(project.nomes_niveis_hierarquia, ["Área", "Cenário"])
        self.assertTrue(
            Membership.objects.filter(
                usuario=self.gestor,
                projeto=project,
                papel__codigo=Papel.Codigo.GESTOR,
            ).exists()
        )
        self.assertTrue(
            Membership.objects.filter(
                usuario__entra_object_id=entra_id,
                projeto=project,
                papel__codigo=Papel.Codigo.DEV,
            ).exists()
        )
        self.assertIn(
            {
                "id": str(entra_id),
                "initials": "DU",
                "name": "Dev Um",
                "email": "dev.um@fumep.edu.br",
                "role": "Desenvolvedor",
            },
            response.data["team"],
        )

    def test_nao_cria_projeto_ativo_com_mesmo_nome_e_modo(self):
        self.client.force_authenticate(user=self.gestor)
        payload = {
            "name": self.crm.nome,
            "description": "",
            "mode": "uat",
            "hierarchyLevels": ["Área", "Cenário"],
            "team": [],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("nome", response.data)

    def test_cria_projeto_com_mesmo_nome_em_modo_diferente(self):
        self.client.force_authenticate(user=self.gestor)
        payload = {
            "name": self.crm.nome,
            "description": "",
            "mode": "cutover",
            "hierarchyLevels": ["Frente"],
            "team": [],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)

    def test_cria_projeto_cutover_rejeita_dois_niveis(self):
        self.client.force_authenticate(user=self.gestor)
        payload = {
            "name": "ERP Cutover",
            "description": "",
            "mode": "cutover",
            "hierarchyLevels": ["Módulo", "Cenário"],
            "team": [],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("hierarchyLevels", response.data)

    def test_detalhe_do_projeto_retorna_configuracoes(self):
        self.client.force_authenticate(user=self.gestor)

        response = self.client.get(reverse("projects:detail", kwargs={"project_id": self.crm.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.crm.id))
        self.assertEqual(response.data["description"], self.crm.descricao)
        self.assertEqual(response.data["agingAlertaDias"], 2)
        self.assertEqual(response.data["agingRiscoDias"], 6)
        self.assertEqual(response.data["anexoMaxMb"], 10)
        self.assertTrue(response.data["exigirEvidenciaAtividade"])
        self.assertTrue(response.data["exigirEvidenciaIssue"])

    def test_gestor_atualiza_configuracoes_do_projeto(self):
        self.client.force_authenticate(user=self.gestor)
        url = reverse("projects:detail", kwargs={"project_id": self.crm.id})
        payload = {
            "name": "CRM Homologação Comercial 2",
            "hierarchyLevels": ["Frente", "Cenário"],
            "agingAlertaDias": 3,
            "agingRiscoDias": 8,
            "anexoMaxMb": 15,
            "exigirEvidenciaIssue": False,
        }

        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.crm.refresh_from_db()
        self.assertEqual(self.crm.nome, "CRM Homologação Comercial 2")
        self.assertEqual(self.crm.nomes_niveis_hierarquia, ["Frente", "Cenário"])
        self.assertEqual(self.crm.aging_alerta_dias, 3)
        self.assertEqual(self.crm.aging_risco_dias, 8)
        self.assertEqual(self.crm.anexo_max_mb, 15)
        self.assertFalse(self.crm.exigir_evidencia_issue)

    def test_usuario_sem_papel_gestor_nao_atualiza_projeto(self):
        Membership.objects.create(
            usuario=self.outro_usuario,
            projeto=self.crm,
            papel=self.papel_tester,
        )
        self.client.force_authenticate(user=self.outro_usuario)

        response = self.client.patch(
            reverse("projects:detail", kwargs={"project_id": self.crm.id}),
            {"name": "Não deve mudar"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_gestor_desativa_projeto_em_vez_de_apagar(self):
        self.client.force_authenticate(user=self.gestor)

        response = self.client.delete(reverse("projects:detail", kwargs={"project_id": self.crm.id}))

        self.assertEqual(response.status_code, 204)
        self.crm.refresh_from_db()
        self.assertFalse(self.crm.ativo)
        self.assertTrue(Project.objects.filter(id=self.crm.id).exists())
        self.assertEqual(self.client.get(self.url).data, [])

    def test_usuario_sem_papel_gestor_nao_desativa_projeto(self):
        Membership.objects.create(
            usuario=self.outro_usuario,
            projeto=self.crm,
            papel=self.papel_tester,
        )
        self.client.force_authenticate(user=self.outro_usuario)

        response = self.client.delete(reverse("projects:detail", kwargs={"project_id": self.crm.id}))

        self.assertEqual(response.status_code, 403)
        self.crm.refresh_from_db()
        self.assertTrue(self.crm.ativo)

    def test_lista_papeis(self):
        self.client.force_authenticate(user=self.gestor)

        response = self.client.get(reverse("projects:roles-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [papel["codigo"] for papel in response.data],
            [Papel.Codigo.GESTOR, Papel.Codigo.TESTER, Papel.Codigo.DEV],
        )

    def test_gestor_cria_e_lista_nos_de_hierarquia(self):
        self.client.force_authenticate(user=self.gestor)
        url = reverse("projects:hierarchy-list", kwargs={"project_id": self.crm.id})

        raiz_response = self.client.post(
            url,
            {"level": 1, "name": "Fiscal", "order": 1},
            format="json",
        )
        filho_response = self.client.post(
            url,
            {
                "parentId": raiz_response.data["id"],
                "level": 2,
                "name": "Cenário A",
                "order": 1,
            },
            format="json",
        )
        list_response = self.client.get(url)

        self.assertEqual(raiz_response.status_code, 201)
        self.assertEqual(filho_response.status_code, 201)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 2)
        self.assertEqual(list_response.data[0]["name"], "Fiscal")
        self.assertEqual(list_response.data[1]["parentId"], raiz_response.data["id"])

    def test_no_de_hierarquia_nao_pode_ser_removido(self):
        self.client.force_authenticate(user=self.gestor)
        raiz = NoHierarquia.objects.create(
            projeto=self.crm,
            nivel=NoHierarquia.Nivel.NIVEL_1,
            nome="Fiscal",
        )

        response = self.client.delete(
            reverse(
                "projects:hierarchy-detail",
                kwargs={"project_id": self.crm.id, "node_id": raiz.id},
            )
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(NoHierarquia.objects.filter(id=raiz.id).exists())

    def test_cutover_rejeita_no_de_hierarquia_nivel_2(self):
        self.client.force_authenticate(user=self.outro_usuario)
        url = reverse("projects:hierarchy-list", kwargs={"project_id": self.erp.id})
        raiz = NoHierarquia.objects.create(
            projeto=self.erp,
            nivel=NoHierarquia.Nivel.NIVEL_1,
            nome="Módulo Financeiro",
        )

        response = self.client.post(
            url,
            {"parentId": str(raiz.id), "level": 2, "name": "Cenário A"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_gestor_convida_e_remove_membership(self):
        self.client.force_authenticate(user=self.gestor)
        url = reverse("projects:memberships-list", kwargs={"project_id": self.crm.id})
        entra_id = uuid4()

        create_response = self.client.post(
            url,
            {
                "id": str(entra_id),
                "initials": "TU",
                "name": "Tester Um",
                "email": "tester.um@fumep.edu.br",
                "role": "Tester",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["id"], str(entra_id))
        self.assertEqual(create_response.data["roleCode"], Papel.Codigo.TESTER)

        delete_response = self.client.delete(
            reverse(
                "projects:memberships-detail",
                kwargs={
                    "project_id": self.crm.id,
                    "membership_id": create_response.data["membershipId"],
                },
            )
        )

        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(Membership.objects.filter(id=create_response.data["membershipId"]).exists())
