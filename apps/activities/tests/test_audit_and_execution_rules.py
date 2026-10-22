from datetime import date
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.activities.models import Activity, ActivityStatusEvent
from apps.activities.services import criar_activity, concluir_activity, salvar_activity
from apps.issues.models import Issue
from apps.issues.services import criar_issue, liberar_activity_se_sem_issues_bloqueadoras
from apps.projects.models import Membership, NoHierarquia, Papel, Project
from apps.projects.spi import calcular_spi


class AuditAndExecutionRulesTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = Usuario.objects.create_user(username="rules_manager", first_name="Gestor Original", email="rules_manager@example.test")
        cls.tester = Usuario.objects.create_user(username="rules_tester", first_name="Tester Original", email="rules_tester@example.test")
        cls.dev = Usuario.objects.create_user(username="rules_dev", first_name="Dev Original", email="rules_dev@example.test")
        cls.projects = []
        for mode in ("UAT", "CUTOVER"):
            project = Project.objects.create(nome=f"Execution {mode}", modo=mode, nivel1_nome="Modulo",
                nivel2_nome="Processo" if mode == "UAT" else None, criado_por=cls.manager,
                exigir_evidencia_atividade=False, exigir_evidencia_issue=False)
            root = NoHierarquia.objects.create(projeto=project, nivel=1, nome="Modulo")
            node = NoHierarquia.objects.create(projeto=project, parent=root, nivel=2, nome="Processo") if mode == "UAT" else root
            for user, code in ((cls.manager, "GESTOR"), (cls.tester, "TESTER"), (cls.dev, "DEV")):
                Membership.objects.create(projeto=project, usuario=user, papel=Papel.objects.get(codigo=code))
            cls.projects.append((project, node))

    def activity(self, index=0):
        project, node = self.projects[index]
        return criar_activity(projeto=project, usuario=self.manager, dados={"nodeId": node.id, "name": "Audit activity",
            "testerId": self.tester.id, "developerId": self.dev.id,
            "plannedStart": date(2026, 10, 1), "plannedEnd": date(2026, 10, 5)})

    def issue(self, activity, impeditiva=True):
        self.client.force_authenticate(self.tester)
        return self.client.post(reverse("issues:list", kwargs={"project_id": activity.projeto_id}), {
            "title": "Issue", "description": "Details", "type": "dados", "impact": "alto", "impeditiva": impeditiva,
            "developerId": str(self.dev.id), "relatedActivityId": activity.codigo_visivel}, format="json")

    def propose(self, issue):
        self.client.force_authenticate(self.dev)
        kwargs = {"project_id": issue.projeto_id, "issue_id": issue.id}
        self.assertEqual(self.client.post(reverse("issues:start-analysis", kwargs=kwargs)).status_code, 200)
        return self.client.post(reverse("issues:propose-solution", kwargs=kwargs), {"proposedSolution": "Fixed"}, format="json")

    def test_cutover_rejects_non_blocking_issue_in_api_and_service(self):
        activity = self.activity(1)
        response = self.issue(activity, False)
        self.assertEqual(response.status_code, 400)
        self.assertIn("impeditiva", response.data)
        self.assertFalse(Issue.objects.exists())
        with self.assertRaises(Exception) as error:
            criar_issue(projeto=activity.projeto, usuario=self.tester, dados={"activity": activity, "impeditiva": False})
        self.assertIn("impeditiva", str(error.exception))
        with self.assertRaises(ValidationError):
            Issue(projeto=activity.projeto, atividade=activity, impeditiva=False).clean()
        self.assertEqual(self.issue(activity, True).status_code, 201)

    def test_uat_still_accepts_non_blocking_issue(self):
        activity = self.activity()
        self.assertEqual(self.issue(activity, False).status_code, 201)
        activity.refresh_from_db()
        self.assertEqual(activity.status, "LIBERADO")
        self.assertEqual(activity.numero_retest, 0)

    def test_retest_only_when_last_blocker_releases_activity_once(self):
        for index in (0, 1):
            activity = self.activity(index)
            self.assertEqual(self.issue(activity).status_code, 201)
            self.assertEqual(self.issue(activity).status_code, 201)
            activity.refresh_from_db()
            self.assertEqual(activity.numero_retest, 0)
            self.assertIsNotNone(activity.data_inicio_real)
            first, second = activity.issues.order_by("id")
            self.assertEqual(self.propose(first).status_code, 200)
            activity.refresh_from_db()
            self.assertEqual(activity.status, "BLOQUEADO")
            self.assertEqual(activity.numero_retest, 0)
            self.assertEqual(self.propose(second).status_code, 200)
            activity.refresh_from_db()
            self.assertEqual(activity.status, "LIBERADO")
            self.assertEqual(activity.numero_retest, 1)
            with transaction.atomic():
                liberar_activity_se_sem_issues_bloqueadoras(activity, usuario=self.dev)
            activity.refresh_from_db()
            self.assertEqual(activity.numero_retest, 1)
            self.issue(activity)
            third = activity.issues.order_by("id").last()
            self.assertEqual(self.propose(third).status_code, 200)
            activity.refresh_from_db()
            self.assertEqual(activity.numero_retest, 2)
            self.assertEqual(activity.eventos_status.last().autor, self.dev)

    def test_creation_block_release_and_complete_capture_actor_and_snapshots(self):
        activity = self.activity()
        self.issue(activity)
        self.propose(activity.issues.get())
        activity.refresh_from_db()
        concluir_activity(activity=activity, usuario=self.tester)
        events = list(activity.eventos_status.all())
        self.assertEqual([event.autor_id for event in events], [self.manager.id, self.tester.id, self.dev.id, self.tester.id])
        self.assertEqual([(event.status_anterior, event.status_novo) for event in events],
            [("", "LIBERADO"), ("LIBERADO", "BLOQUEADO"), ("BLOQUEADO", "LIBERADO"), ("LIBERADO", "CONCLUIDO")])
        Usuario.objects.filter(pk=self.dev.pk).update(first_name="Nome alterado")
        events[2].refresh_from_db()
        self.assertEqual(events[2].autor_nome, "Dev Original")

    def test_event_cannot_be_changed_or_deleted_even_with_raw_sql(self):
        activity = self.activity()
        event = activity.eventos_status.get()
        event.texto = "Tampered"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()
        for sql in (
            "UPDATE activities_activitystatusevent SET texto = 'Tampered' WHERE id = %s",
            "DELETE FROM activities_activitystatusevent WHERE id = %s",
        ):
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql, [event.id])
        with self.assertRaises(DatabaseError), transaction.atomic():
            ActivityStatusEvent.objects.filter(pk=event.pk).update(texto="Tampered")
        with self.assertRaises(DatabaseError), transaction.atomic():
            ActivityStatusEvent.objects.filter(pk=event.pk).delete()
        with self.assertRaises(DatabaseError), transaction.atomic():
            Activity.objects.filter(pk=activity.pk).update(historico_status=[{"text": "Tampered"}])
        event.refresh_from_db()
        self.assertEqual(event.texto, "Atividade criada")

    def test_api_rejects_history_and_counter_edits(self):
        activity = self.activity()
        self.client.force_authenticate(self.manager)
        url = reverse("activities:detail", kwargs={"project_id": activity.projeto_id, "activity_id": activity.id})
        for payload in ({"auditTrail": []}, {"historico_status": []}, {"retestCount": 20}):
            self.assertEqual(self.client.patch(url, payload, format="json").status_code, 400)
        response = self.client.get(url)
        self.assertEqual(response.data["auditTrail"][0]["authorId"], str(self.manager.id))
        self.assertEqual(response.data["auditTrail"][0]["text"], "Atividade criada")

    def test_failure_to_append_event_rolls_back_status(self):
        activity = self.activity()
        with patch("apps.activities.services.ActivityStatusEvent.objects.create", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                concluir_activity(activity=activity, usuario=self.tester)
        activity.refresh_from_db()
        self.assertEqual(activity.status, "LIBERADO")
        self.assertEqual(activity.eventos_status.count(), 1)

    def test_migration_preserves_legacy_text_and_marks_unknown_author(self):
        project, node = self.projects[0]
        activity = Activity.objects.create(projeto=project, no=node, nome="Legacy", tester=self.tester, desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 10, 1), data_conclusao_planejada=date(2026, 10, 5),
            historico_status=[{"at": "2026-10-02T12:00:00Z", "text": "Liberado → Bloqueado"}])
        import_module("apps.activities.migrations.0008_freeze_activity_audit").preserve_history(apps, SimpleNamespace(connection=connection))
        event = activity.eventos_status.get(texto="Liberado → Bloqueado")
        self.assertEqual(event.origem, "legado")
        self.assertIsNone(event.autor_id)
        self.assertEqual(event.ocorrido_em.date(), date(2026, 10, 2))
        self.assertIn("não registrado", event.autor_nome)

    def test_spi_uses_ev_pv_not_completed_fraction_and_excludes_cancelled(self):
        first = self.activity()
        Activity.objects.filter(pk=first.pk).update(status="CONCLUIDO", data_conclusao_real=date(2026, 10, 3))
        second = self.activity()
        Activity.objects.filter(pk=second.pk).update(status="BLOQUEADO", data_inicio_real=date(2026, 10, 2))
        third = self.activity()
        Activity.objects.filter(pk=third.pk).update(data_inicio_planejada=date(2026, 10, 8), data_conclusao_planejada=date(2026, 10, 10))
        cancelled = self.activity()
        Activity.objects.filter(pk=cancelled.pk).update(status="CANCELADO")
        self.assertEqual(calcular_spi(first.projeto.activities.all(), date(2026, 10, 5)), 0.75)
        self.assertIsNone(calcular_spi(first.projeto.activities.all(), date(2026, 9, 30)))
        self.client.force_authenticate(self.manager)
        with patch("apps.projects.spi.timezone.localdate", return_value=date(2026, 10, 5)):
            listing = self.client.get(reverse("projects:list"))
            row = next(item for item in listing.data if item["id"] == str(first.projeto_id))
            self.assertEqual(row["spi"], 0.75)
        dashboard = self.client.get(reverse("projects:dashboard", kwargs={"project_id": first.projeto_id}), {"today": "2026-10-05"})
        self.assertEqual(dashboard.data["spi"], 0.75)

    def test_legacy_retest_is_reconciled_only_with_complete_blocking_evidence(self):
        project, node = self.projects[0]
        activities = []
        for old_counter in (1, 3):
            activity = Activity.objects.create(projeto=project, no=node, nome="Legacy retest", tester=self.tester, desenvolvedor=self.dev,
                status="BLOQUEADO", numero_retest=old_counter, data_inicio_planejada=date(2026, 10, 1), data_conclusao_planejada=date(2026, 10, 5),
                historico_status=[{"at": "2026-10-02T12:00:00Z", "text": "Liberado → Bloqueado"}])
            Issue.objects.create(projeto=project, atividade=activity, titulo="Legacy issue", descricao="Legacy", tipo="DADOS", impacto="ALTO",
                impeditiva=True, tester=self.tester, desenvolvedor=self.dev)
            activities.append(activity)
        import_module("apps.activities.migrations.0008_freeze_activity_audit").preserve_history(apps, SimpleNamespace(connection=connection))
        activities[0].refresh_from_db(); activities[1].refresh_from_db()
        self.assertEqual(activities[0].numero_retest, 0)
        self.assertTrue(activities[0].eventos_status.filter(origem="migracao_reteste").exists())
        self.assertEqual(activities[1].numero_retest, 3)
        self.assertFalse(activities[1].eventos_status.filter(origem="migracao_reteste").exists())

    def test_spi_start_is_half_and_zero_pv_is_undefined(self):
        activity = self.activity()
        self.assertEqual(calcular_spi(activity.projeto.activities.all(), date(2026, 10, 2)), 0)
        Activity.objects.filter(pk=activity.pk).update(data_inicio_real=date(2026, 10, 2))
        self.assertEqual(calcular_spi(activity.projeto.activities.all(), date(2026, 10, 2)), 1)
        self.assertEqual(calcular_spi(activity.projeto.activities.all(), date(2026, 10, 5)), 0.5)
        self.assertIsNone(calcular_spi(activity.projeto.activities.all(), date(2026, 9, 30)))
