from datetime import date
from unittest.mock import patch
from io import StringIO

from django.urls import reverse
from django.core.management import call_command
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.activities.models import Activity
from apps.activities.services import concluir_activity
from apps.issues.models import Issue
from apps.projects.models import Membership, NoHierarquia, Papel, Project
from apps.projects.permissions import matriz_efetiva


class ProjectPolicyTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = Usuario.objects.create_user(username="policy_manager", email="policy_manager@example.test")
        cls.tester = Usuario.objects.create_user(username="policy_tester", email="policy_tester@example.test")
        cls.dev = Usuario.objects.create_user(username="policy_dev", email="policy_dev@example.test")
        cls.other = Usuario.objects.create_user(username="policy_other", email="policy_other@example.test")
        cls.projects = []
        for mode in (Project.Modo.UAT, Project.Modo.CUTOVER):
            project = Project.objects.create(nome=f"Policies {mode}", modo=mode, nivel1_nome="Modulo",
                nivel2_nome="Processo" if mode == Project.Modo.UAT else None, criado_por=cls.manager,
                exigir_evidencia_atividade=False, exigir_evidencia_issue=False)
            root = NoHierarquia.objects.create(projeto=project, nivel=1, nome="Financeiro")
            node = root if mode == Project.Modo.CUTOVER else NoHierarquia.objects.create(projeto=project, parent=root, nivel=2, nome="Teste")
            for user, role in ((cls.manager, "GESTOR"), (cls.tester, "TESTER"), (cls.dev, "DEV"), (cls.other, "DEV")):
                Membership.objects.create(projeto=project, usuario=user, papel=Papel.objects.get(codigo=role))
            cls.projects.append((project, node))

    def activity(self, project, node):
        return Activity.objects.create(projeto=project, no=node, nome="Atividade", tester=self.tester,
            desenvolvedor=self.dev, status=Activity.Status.LIBERADO, data_inicio_planejada=date(2026, 10, 1),
            data_conclusao_planejada=date(2026, 10, 2))

    def issue(self, activity, status=Issue.Status.SOLUCAO_PROPOSTA):
        return Issue.objects.create(projeto=activity.projeto, atividade=activity, titulo="Issue", descricao="Problema",
            tipo=Issue.Tipo.DADOS, impacto=Issue.Impacto.ALTO, status=status, tester=self.tester, desenvolvedor=self.dev)

    def configure(self, project, payload):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(reverse("projects:detail", kwargs={"project_id": project.id}), payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        project.refresh_from_db()
        return response

    def route(self, namespace, name, project, record=None):
        kwargs = {"project_id": project.id}
        if record is not None:
            kwargs["activity_id" if namespace == "activities" else "issue_id"] = record.id
        return reverse(f"{namespace}:{name}", kwargs=kwargs)

    def test_conclusao_tester_fecha_apenas_issues_propostas_da_atividade(self):
        for project, node in self.projects:
            activity = self.activity(project, node)
            proposed = [self.issue(activity), self.issue(activity)]
            cancelled = self.issue(activity, Issue.Status.CANCELADA)
            other = self.issue(self.activity(project, node))
            self.client.force_authenticate(self.tester)
            response = self.client.post(self.route("activities", "complete", project, activity), {}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            for issue in proposed:
                issue.refresh_from_db()
                self.assertEqual(issue.status, Issue.Status.CONCLUIDA)
                self.assertIsNotNone(issue.resolvida_em)
            cancelled.refresh_from_db(); other.refresh_from_db()
            self.assertEqual(cancelled.status, Issue.Status.CANCELADA)
            self.assertEqual(other.status, Issue.Status.SOLUCAO_PROPOSTA)
            response = self.client.get(self.route("issues", "list", project))
            self.assertEqual(sum(i["status"] == "concluida" for i in response.data), 2)

    def test_conclusao_e_issues_fazem_rollback_juntas(self):
        project, node = self.projects[0]
        activity = self.activity(project, node)
        issue = self.issue(activity)
        with patch("apps.activities.services.liberar_dependentes", side_effect=RuntimeError("rollback")):
            with self.assertRaises(RuntimeError):
                concluir_activity(activity=activity, usuario=self.tester)
        activity.refresh_from_db(); issue.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.LIBERADO)
        self.assertEqual(issue.status, Issue.Status.SOLUCAO_PROPOSTA)

    def test_reconciliacao_de_dados_antigos_simula_e_corrige_apenas_escopo_valido(self):
        project, node = self.projects[0]
        activity = self.activity(project, node)
        issue = self.issue(activity)
        untouched = self.issue(self.activity(project, node))
        Activity.objects.filter(pk=activity.pk).update(status=Activity.Status.CONCLUIDO)
        call_command("reconciliar_issues_concluidas", stdout=StringIO())
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.SOLUCAO_PROPOSTA)
        call_command("reconciliar_issues_concluidas", apply=True, project=str(project.id), stdout=StringIO())
        issue.refresh_from_db(); untouched.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.CONCLUIDA)
        self.assertIsNotNone(issue.resolvida_em)
        self.assertEqual(untouched.status, Issue.Status.SOLUCAO_PROPOSTA)

    def test_matriz_persistida_somente_no_projeto_e_revogacao_efetiva(self):
        project, node = self.projects[0]
        other_project, other_node = self.projects[1]
        def payload(n):
            return {"name": "Nova", "nodeId": str(n.id), "testerId": str(self.tester.id),
                "developerId": str(self.dev.id), "plannedStart": "2026-10-01", "plannedEnd": "2026-10-02"}
        self.configure(project, {"permissionMatrix": {"activities_create": {"DEV": True}}})
        self.client.force_authenticate(self.dev)
        self.assertEqual(self.client.post(self.route("activities", "list", project), payload(node), format="json").status_code, 201)
        self.assertEqual(self.client.post(self.route("activities", "list", other_project), payload(other_node), format="json").status_code, 403)
        response = self.client.get(reverse("projects:detail", kwargs={"project_id": project.id}))
        self.assertTrue(response.data["permissionMatrix"]["activities_create"]["DEV"])
        self.configure(project, {"permissionMatrix": {"activities_create": {"DEV": False}}})
        self.client.force_authenticate(self.dev)
        self.assertEqual(self.client.post(self.route("activities", "list", project), payload(node), format="json").status_code, 403)
        self.assertEqual(len(project.historico_politicas), 2)

    def test_matriz_rejeita_acoes_invalidas_e_nao_permite_alteracao_por_dev(self):
        project, _ = self.projects[0]
        url = reverse("projects:detail", kwargs={"project_id": project.id})
        for user in (self.dev, self.tester):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.patch(url, {"permissionMatrix": {}}, format="json").status_code, 403)
        self.client.force_authenticate(self.manager)
        for matrix in ({"invalid": {}}, {"issues_create": {"DEV": 1}}, {"issues_create": {"GESTOR": False}}, {"data_view": {"DEV": False}}):
            self.assertEqual(self.client.patch(url, {"permissionMatrix": matrix}, format="json").status_code, 400)

    def test_permissao_sobre_atividade_mantem_escopo_dos_responsaveis(self):
        project, node = self.projects[0]
        activity = self.activity(project, node)
        self.configure(project, {"permissionMatrix": {"activities_complete": {"DEV": True, "TESTER": False}}})
        for user, expected in ((self.tester, 403), (self.other, 403), (self.dev, 200)):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.post(self.route("activities", "complete", project, activity), {}, format="json").status_code, expected)

    def test_conceder_analise_ao_tester_afeta_rotas_reais(self):
        project, node = self.projects[0]
        activity = self.activity(project, node)
        issue = self.issue(activity, Issue.Status.ABERTA)
        self.configure(project, {"permissionMatrix": {"issues_analyze": {"TESTER": True}}})
        self.client.force_authenticate(self.tester)
        self.assertEqual(self.client.post(self.route("issues", "start-analysis", project, issue), {}, format="json").status_code, 200)
        response = self.client.post(self.route("issues", "propose-solution", project, issue), {"proposedSolution": "Correção"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def test_editar_nao_concede_alteracao_de_atribuicoes_por_payload_misto(self):
        project, node = self.projects[0]
        activity = self.activity(project, node)
        self.configure(project, {"permissionMatrix": {"activities_edit": {"DEV": True}}})
        self.client.force_authenticate(self.dev)
        url = self.route("activities", "detail", project, activity)
        self.assertEqual(self.client.patch(url, {"name": "Novo nome"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"name": "Tentativa", "developerId": str(self.other.id)}, format="json").status_code, 403)

    def test_retirar_visualizacao_e_exportacao_bloqueia_api(self):
        project, node = self.projects[0]
        self.activity(project, node)
        self.configure(project, {"permissionMatrix": {"data_view": {"DEV": False}, "dashboard_view": {"DEV": False}, "data_export": {"DEV": False}}})
        self.client.force_authenticate(self.dev)
        self.assertEqual(self.client.get(self.route("activities", "list", project)).status_code, 403)
        self.assertEqual(self.client.get(self.route("issues", "list", project)).status_code, 403)
        self.assertEqual(self.client.get(reverse("projects:audit-export", kwargs={"project_id": project.id})).status_code, 403)

    def test_analise_automatica_persistida_sem_alterar_issues_anteriores(self):
        for project, node in self.projects:
            activity = self.activity(project, node)
            previous = self.issue(activity, Issue.Status.ABERTA)
            self.configure(project, {"issueAutoAnalysis": True})
            self.client.force_authenticate(self.tester)
            payload = {"title": "Nova", "description": "Problema", "type": "dados", "impact": "alto",
                "impeditiva": False, "relatedActivityId": activity.codigo_visivel, "developerId": str(self.dev.id)}
            response = self.client.post(self.route("issues", "list", project), payload, format="json")
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["status"], "em_analise")
            previous.refresh_from_db()
            self.assertEqual(previous.status, Issue.Status.ABERTA)
            created = Issue.objects.exclude(pk=previous.pk).filter(atividade=activity).get()
            self.assertIsNotNone(created.analise_iniciada_em)
            self.configure(project, {"issueAutoAnalysis": False})
            self.client.force_authenticate(self.tester)
            response = self.client.post(self.route("issues", "list", project), payload, format="json")
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["status"], "aberta")
            self.assertEqual(len(project.historico_politicas), 2)

    def test_delegar_limiares_nao_concede_edicao_da_matriz(self):
        project, _ = self.projects[0]
        self.configure(project, {"permissionMatrix": {"config_thresholds": {"TESTER": True}}})
        self.client.force_authenticate(self.tester)
        url = reverse("projects:detail", kwargs={"project_id": project.id})
        self.assertEqual(self.client.patch(url, {"issueAutoAnalysis": True}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"permissionMatrix": {}}, format="json").status_code, 403)

    def test_multiplos_papeis_acumulam_permissoes(self):
        project, node = self.projects[0]
        activity = self.activity(project, node)
        Membership.objects.create(projeto=project, usuario=self.tester, papel=Papel.objects.get(codigo="DEV"))
        matrix = matriz_efetiva(project)
        matrix["activities_complete"]["TESTER"] = False
        matrix["activities_complete"]["DEV"] = True
        self.configure(project, {"permissionMatrix": matrix})
        Activity.objects.filter(pk=activity.pk).update(desenvolvedor=self.tester)
        self.client.force_authenticate(self.tester)
        self.assertEqual(self.client.post(self.route("activities", "complete", project, activity), {}, format="json").status_code, 200)
