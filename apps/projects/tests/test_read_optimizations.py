from datetime import date, timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.activities.models import Activity, ActivityPredecessor
from apps.issues.models import Issue
from apps.projects.models import Membership, NoHierarquia, Papel, Project


class ReadOptimizationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = Usuario.objects.create_user(username="reads", email="reads@example.test")
        cls.project = Project.objects.create(nome="Reads", modo="CUTOVER", nivel1_nome="Modulo", criado_por=cls.user)
        cls.node = NoHierarquia.objects.create(projeto=cls.project, nivel=1, nome="Modulo")
        Membership.objects.create(projeto=cls.project, usuario=cls.user, papel=Papel.objects.get(codigo="GESTOR"))

    def setUp(self):
        self.client.force_authenticate(self.user)

    def activity(self, **extra):
        fields = dict(projeto=self.project, no=self.node, tester=self.user, desenvolvedor=self.user,
            nome="Activity", data_inicio_planejada=date(2026, 10, 1), data_conclusao_planejada=date(2026, 10, 3),
            resultado_esperado="Full result", observacoes="Full notes", historico_status=[{"at": "2026-10-01T00:00:00Z", "text": "Created"}])
        fields.update(extra)
        return Activity.objects.create(**fields)

    def issue(self, activity, **extra):
        fields = dict(projeto=self.project, atividade=activity, tester=self.user, desenvolvedor=self.user,
            titulo="Issue", descricao="Full description", nota_impacto="Full impact", tipo="DADOS", impacto="ALTO")
        fields.update(extra)
        return Issue.objects.create(**fields)

    def url(self, namespace, name, **extra):
        return reverse(f"{namespace}:{name}", kwargs={"project_id": self.project.id, **extra})

    def test_summary_and_detail_contracts_and_filtered_export(self):
        first = self.activity()
        second = self.activity()
        ActivityPredecessor.objects.create(atividade=second, predecessora=first)
        self.issue(second)
        self.issue(second, status="CANCELADA")
        response = self.client.get(self.url("activities", "list"), {"view": "summary"})
        self.assertEqual(response.status_code, 200)
        row = next(row for row in response.data if row["numericId"] == second.id)
        self.assertEqual(row["issueCount"], 1)
        self.assertEqual(row["predecessors"], [first.codigo_visivel])
        for field in ("auditTrail", "notes", "expectedResult", "approvalEvidence", "attachments"):
            self.assertNotIn(field, row)
        full = self.client.get(self.url("activities", "detail", activity_id=second.id))
        self.assertEqual(full.data["expectedResult"], "Full result")
        self.assertIn("auditTrail", full.data)
        export = self.client.get(self.url("activities", "list"), {"ids": str(second.id)})
        self.assertEqual([row["numericId"] for row in export.data], [second.id])
        self.assertEqual(export.data[0]["notes"], "Full notes")

    def test_issue_summary_filters_and_full_detail(self):
        first = self.activity()
        second = self.activity()
        issue = self.issue(first, solucao_proposta="Full solution")
        self.issue(second)
        response = self.client.get(self.url("issues", "list"), {"view": "summary", "activityId": first.id})
        self.assertEqual(len(response.data), 1)
        self.assertNotIn("description", response.data[0])
        self.assertNotIn("openingAttachment", response.data[0])
        full = self.client.get(self.url("issues", "detail", issue_id=issue.id))
        self.assertEqual(full.data["description"], "Full description")
        export = self.client.get(self.url("issues", "list"), {"ids": str(issue.id)})
        self.assertEqual(len(export.data), 1)
        self.assertEqual(export.data[0]["proposedSolution"], "Full solution")

    def query_count(self, url, params=None):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url, params or {})
            self.assertEqual(response.status_code, 200, response.data)
        return len(queries)

    def test_activity_query_count_does_not_grow_per_row(self):
        self.issue(self.activity())
        url = self.url("activities", "list")
        before = self.query_count(url, {"view": "summary"})
        for index in range(20):
            self.issue(self.activity(nome=f"More {index}"))
        self.assertEqual(self.query_count(url, {"view": "summary"}), before)

    def test_project_query_count_does_not_grow_per_project(self):
        self.activity()
        before = self.query_count(reverse("projects:list"))
        for index in range(5):
            project = Project.objects.create(nome=f"More {index}", modo="CUTOVER", nivel1_nome="Modulo", criado_por=self.user)
            Membership.objects.create(projeto=project, usuario=self.user, papel=Papel.objects.get(codigo="GESTOR"))
        self.assertEqual(self.query_count(reverse("projects:list")), before)

    def test_dashboard_preserves_metrics_curve_and_recent_contract(self):
        completed = self.activity(status="CONCLUIDO", data_conclusao_real=date(2026, 10, 2))
        self.activity(status="LIBERADO", data_conclusao_planejada=date(2026, 10, 5))
        self.activity(status="CANCELADO", data_conclusao_planejada=date(2026, 10, 8))
        issue = self.issue(completed, status="CONCLUIDA")
        now = timezone.now()
        Issue.objects.filter(pk=issue.id).update(criada_em=now - timedelta(days=2), resolvida_em=now)
        self.issue(completed, status="CANCELADA")
        response = self.client.get(self.url("projects", "dashboard"), {"today": "2026-10-04"})
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data
        self.assertEqual(data["activities"], {"total": 3, "concluido": 1, "liberado": 1, "bloqueado": 0, "aguardando": 0, "atrasado": 0})
        self.assertEqual(data["issues"]["canceladas"], 1)
        self.assertEqual(data["issues"]["tempoMedioResolucaoDias"], 2)
        self.assertAlmostEqual(data["spi"], 1 / 1.5)
        self.assertEqual(data["indicators"], {"pace": 100, "quality": 100, "backlog": 50})
        self.assertEqual(data["curve"]["labels"], ["01/10", "02/10", "03/10", "04/10", "05/10"])
        self.assertEqual(data["curve"]["plannedCounts"], [0, 0, 1, 1, 2])
        self.assertEqual(data["curve"]["realizedCounts"], [0, 1, 1, 1, None])
        self.assertEqual(len(data["recent"]), 5)
        self.assertNotIn("description", data)

    def test_dashboard_empty_late_project_and_permissions(self):
        url = self.url("projects", "dashboard")
        empty = self.client.get(url).data
        self.assertIsNone(empty["spi"])
        self.assertEqual(empty["curve"]["total"], 0)
        self.activity()
        data = self.client.get(url, {"today": "2026-10-06"}).data
        self.assertEqual(data["curve"]["labels"][-1], "06/10")
        self.assertEqual(data["curve"]["planned"][-1], 100)
        self.assertEqual(data["curve"]["realized"][-1], 0)
        self.assertEqual(data["activities"]["atrasado"], 1)
        self.assertEqual(self.client.get(url, {"today": "invalid"}).status_code, 400)
        other = Usuario.objects.create_user(username="outsider", email="outsider@example.test")
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        Membership.objects.create(projeto=self.project, usuario=other, papel=Papel.objects.get(codigo="TESTER"))
        self.project.matriz_permissoes = {"dashboard_view": {"TESTER": False}}
        self.project.save()
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_dashboard_query_count_does_not_grow_per_activity(self):
        self.issue(self.activity())
        url = self.url("projects", "dashboard")
        before = self.query_count(url)
        for index in range(20):
            self.issue(self.activity(nome=f"More {index}"))
        self.assertEqual(self.query_count(url), before)
