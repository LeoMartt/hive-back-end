from datetime import date
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.activities.models import Activity
from apps.issues.models import Issue
from apps.projects.models import Membership, NoHierarquia, Papel, Project


class PermissionMatrixTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {
            name: Usuario.objects.create_user(username=name, email=f"{name}@example.test")
            for name in ("gestor", "tester", "dev", "outro_tester", "outro_dev", "multipapel", "externo")
        }
        cls.projects = []
        cls.evidence = {
            "fileName": "evidencia.png", "sizeLabel": "1 KB", "contentType": "image/png",
            "uploadedBy": "Tester", "uploadedAt": "2026-10-16T10:00:00Z",
        }
        for mode in (Project.Modo.UAT, Project.Modo.CUTOVER):
            project = Project.objects.create(
                nome=f"Matriz {mode}", modo=mode, nivel1_nome="Modulo",
                nivel2_nome="Processo" if mode == Project.Modo.UAT else None,
                criado_por=cls.users["gestor"],
            )
            root = NoHierarquia.objects.create(projeto=project, nivel=1, nome="Financeiro")
            node = root
            if mode == Project.Modo.UAT:
                node = NoHierarquia.objects.create(projeto=project, parent=root, nivel=2, nome="Pagamentos")
            for name, codes in {
                "gestor": [Papel.Codigo.GESTOR], "tester": [Papel.Codigo.TESTER],
                "dev": [Papel.Codigo.DEV], "outro_tester": [Papel.Codigo.TESTER],
                "outro_dev": [Papel.Codigo.DEV],
                "multipapel": [Papel.Codigo.TESTER, Papel.Codigo.DEV, Papel.Codigo.GESTOR],
            }.items():
                for code in codes:
                    Membership.objects.create(usuario=cls.users[name], projeto=project, papel=Papel.objects.get(codigo=code))
            activity = Activity.objects.create(
                projeto=project, no=node, nome="Validar pagamento", tester=cls.users["tester"],
                desenvolvedor=cls.users["dev"], data_inicio_planejada=date(2026, 10, 1),
                data_conclusao_planejada=date(2026, 10, 2), status=Activity.Status.LIBERADO,
            )
            issue = Issue.objects.create(
                projeto=project, atividade=activity, titulo="Erro de pagamento", descricao="Falha.",
                tipo=Issue.Tipo.REQUISITO, impacto=Issue.Impacto.ALTO, impeditiva=True,
                tester=cls.users["tester"], desenvolvedor=cls.users["dev"],
            )
            cls.projects.append((project, root, node, activity, issue))

    def test_acoes_da_matriz_por_papel_e_modo(self):
        managers = {"gestor", "multipapel"}
        testers = managers | {"tester"}
        developers = managers | {"dev"}
        members = set(self.users) - {"externo"}
        for project, root, node, activity, issue in self.projects:
            project_kwargs = {"project_id": project.id}
            activity_kwargs = {**project_kwargs, "activity_id": activity.id}
            issue_kwargs = {**project_kwargs, "issue_id": issue.id}
            create_activity = {
                "nodeId": str(node.id), "name": "Nova atividade", "testerId": str(self.users["tester"].id),
                "developerId": str(self.users["dev"].id), "plannedStart": "2026-10-01", "plannedEnd": "2026-10-02",
            }
            create_issue = {
                "title": "Nova issue", "description": "Falha.", "type": "requisito", "impact": "alto",
                "impeditiva": True, "relatedActivityId": activity.codigo_visivel,
                "developerId": str(self.users["dev"].id), "openingAttachment": self.evidence,
            }
            member_id = Membership.objects.get(projeto=project, usuario=self.users["outro_tester"]).id
            cases = [
                ("projects:detail", "get", project_kwargs, {}, members, 200),
                ("activities:list", "get", project_kwargs, {}, members, 200),
                ("issues:list", "get", project_kwargs, {}, members, 200),
                ("projects:hierarchy-list", "get", project_kwargs, {}, members, 200),
                ("projects:memberships-list", "get", project_kwargs, {}, members, 200),
                ("projects:detail", "patch", project_kwargs, {"name": "Nome alterado"}, managers, 200),
                ("projects:detail", "patch", project_kwargs, {
                    "hierarchyLevels": ["Nova area", "Novo processo"] if project.modo == Project.Modo.UAT else ["Nova area"],
                }, managers, 200),
                ("projects:detail", "patch", project_kwargs, {"spiSaudavel": 0.95, "spiCritico": 0.6}, managers, 200),
                ("projects:detail", "patch", project_kwargs, {"anexoMaxMb": 20}, managers, 200),
                ("projects:hierarchy-list", "post", project_kwargs, {"level": 1, "name": "Novo modulo"}, managers, 201),
                ("projects:hierarchy-detail", "patch", {**project_kwargs, "node_id": root.id}, {"name": "Modulo alterado"}, managers, 200),
                ("projects:memberships-list", "post", project_kwargs, {
                    "id": str(self.users["externo"].id), "name": "Externo", "email": self.users["externo"].email, "role": "Tester",
                }, managers, 201),
                ("projects:memberships-detail", "delete", {**project_kwargs, "membership_id": member_id}, {}, managers, 204),
                ("activities:list", "post", project_kwargs, create_activity, managers, 201),
                ("activities:detail", "patch", activity_kwargs, {"name": "Atividade alterada"}, managers, 200),
                ("activities:detail", "patch", activity_kwargs, {"testerId": str(self.users["outro_tester"].id)}, managers, 200),
                ("activities:cancel", "post", activity_kwargs, {}, managers, 200),
                ("activities:complete", "post", activity_kwargs, {"approvalEvidence": self.evidence}, testers, 200),
                ("activities:block", "post", activity_kwargs, {"reason": "Falha."}, testers, 200),
                ("issues:list", "post", project_kwargs, create_issue, testers, 201),
                ("issues:start-analysis", "post", issue_kwargs, {}, developers, 200),
                ("issues:propose-solution", "post", issue_kwargs, {"proposedSolution": "Corrigido."}, developers, 200),
                ("issues:cancel", "post", issue_kwargs, {}, developers, 200),
                ("issues:resolve", "post", issue_kwargs, {}, testers, 200),
            ]
            for route, method, kwargs, payload, allowed, success_code in cases:
                for name, user in self.users.items():
                    with self.subTest(mode=project.modo, route=route, method=method, user=name):
                        with transaction.atomic():
                            if route in {"issues:propose-solution", "issues:cancel", "issues:resolve"}:
                                state = Issue.Status.SOLUCAO_PROPOSTA if route == "issues:resolve" else Issue.Status.EM_ANALISE
                                Issue.objects.filter(pk=issue.pk).update(status=state)
                            self.client.force_authenticate(user=user)
                            response = getattr(self.client, method)(reverse(route, kwargs=kwargs), payload, format="json")
                            expected = 404 if name == "externo" else success_code if name in allowed else 403
                            self.assertEqual(response.status_code, expected, response.data)
                            transaction.set_rollback(True)

    @patch("apps.activities.views.importar_activities_de_arquivo")
    def test_importacao_em_massa_exige_gestor(self, importer):
        for project, _, _, activity, _ in self.projects:
            for name, user in self.users.items():
                with self.subTest(mode=project.modo, user=name):
                    importer.reset_mock()
                    importer.return_value = [activity]
                    self.client.force_authenticate(user=user)
                    response = self.client.post(
                        reverse("activities:import", kwargs={"project_id": project.id}),
                        {"file": SimpleUploadedFile("atividades.csv", b"Modulo;Atividade\nFinanceiro;Teste")}, format="multipart",
                    )
                    expected = 404 if name == "externo" else 201 if name in {"gestor", "multipapel"} else 403
                    self.assertEqual(response.status_code, expected, response.data)
                    self.assertEqual(importer.call_count, int(expected == 201))

    def test_atribuicao_antiga_nao_substitui_papel_removido(self):
        for project, _, _, activity, issue in self.projects:
            for name, removed, replacement, route, kwargs, payload in [
                ("tester", Papel.Codigo.TESTER, Papel.Codigo.DEV, "activities:complete", {"activity_id": activity.id}, {"approvalEvidence": self.evidence}),
                ("tester", Papel.Codigo.TESTER, Papel.Codigo.DEV, "issues:list", {}, {
                    "title": "Nova issue", "description": "Falha.", "type": "requisito", "impact": "alto", "impeditiva": True,
                    "relatedActivityId": activity.codigo_visivel, "developerId": str(self.users["dev"].id), "openingAttachment": self.evidence,
                }),
                ("dev", Papel.Codigo.DEV, Papel.Codigo.TESTER, "issues:start-analysis", {"issue_id": issue.id}, {}),
            ]:
                with self.subTest(mode=project.modo, route=route):
                    with transaction.atomic():
                        user = self.users[name]
                        Membership.objects.filter(projeto=project, usuario=user, papel__codigo=removed).delete()
                        Membership.objects.create(projeto=project, usuario=user, papel=Papel.objects.get(codigo=replacement))
                        self.client.force_authenticate(user=user)
                        response = self.client.post(reverse(route, kwargs={"project_id": project.id, **kwargs}), payload, format="json")
                        self.assertEqual(response.status_code, 403, response.data)
                        transaction.set_rollback(True)
