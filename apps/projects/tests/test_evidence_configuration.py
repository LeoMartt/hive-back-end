from datetime import date
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.activities.models import Activity
from apps.activities.services import concluir_activity
from apps.issues.models import Issue
from apps.projects.models import EvidenceRuleChange, Membership, NoHierarquia, Papel, Project


class EvidenceConfigurationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = Usuario.objects.create_user(username="config_manager", email="manager@example.test")
        cls.tester = Usuario.objects.create_user(username="config_tester", email="tester@example.test")
        cls.dev = Usuario.objects.create_user(username="config_dev", email="dev@example.test")
        cls.projects = []
        cls.evidence = {"fileName": "proof.png", "contentType": "image/png", "sizeLabel": "1 KB"}
        for mode in (Project.Modo.UAT, Project.Modo.CUTOVER):
            project = Project.objects.create(
                nome=f"Configuracoes {mode}", modo=mode, nivel1_nome="Modulo",
                nivel2_nome="Processo" if mode == Project.Modo.UAT else None, criado_por=cls.manager,
            )
            root = NoHierarquia.objects.create(projeto=project, nivel=1, nome="Financeiro")
            node = root if mode == Project.Modo.CUTOVER else NoHierarquia.objects.create(
                projeto=project, parent=root, nivel=2, nome="Pagamentos",
            )
            for user, code in ((cls.manager, Papel.Codigo.GESTOR), (cls.tester, Papel.Codigo.TESTER), (cls.dev, Papel.Codigo.DEV)):
                Membership.objects.create(projeto=project, usuario=user, papel=Papel.objects.get(codigo=code))
            cls.projects.append((project, node))

    def configure(self, project, activity_required, issue_required, max_mb=1):
        self.client.force_authenticate(user=self.manager)
        url = reverse("projects:detail", kwargs={"project_id": project.id})
        payload = {"exigirEvidenciaAtividade": activity_required, "exigirEvidenciaIssue": issue_required, "anexoMaxMb": max_mb}
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        reloaded = self.client.get(url)
        for key, value in payload.items():
            self.assertEqual(reloaded.data[key], value)
        project.refresh_from_db()

    def activity(self, project, node):
        return Activity.objects.create(
            projeto=project, no=node, nome="Teste de evidencia", tester=self.tester,
            desenvolvedor=self.dev, data_inicio_planejada=date(2026, 10, 1),
            data_conclusao_planejada=date(2026, 10, 2), status=Activity.Status.LIBERADO,
        )

    def test_alteracoes_registram_autor_valores_e_nao_geram_historico_sem_mudanca(self):
        for project, _ in self.projects:
            self.configure(project, False, False, max_mb=2)
            change = EvidenceRuleChange.objects.get(projeto=project)
            self.assertEqual(change.usuario, self.manager)
            self.assertEqual(change.autor, self.manager.email)
            self.assertEqual(change.valores_anteriores, {
                "exigir_evidencia_atividade": True, "exigir_evidencia_issue": True, "anexo_max_mb": 10,
            })
            self.assertEqual(change.valores_novos, {
                "exigir_evidencia_atividade": False, "exigir_evidencia_issue": False, "anexo_max_mb": 2,
            })
            self.configure(project, False, False, max_mb=2)
            self.assertEqual(project.alteracoes_regras_evidencia.count(), 1)
            url = reverse("projects:detail", kwargs={"project_id": project.id})
            response = self.client.patch(url, {"anexoMaxMb": 0}, format="json")
            self.assertEqual(response.status_code, 400)
            self.client.force_authenticate(user=self.dev)
            response = self.client.patch(url, {"exigirEvidenciaAtividade": True}, format="json")
            self.assertEqual(response.status_code, 403)
            self.assertEqual(project.alteracoes_regras_evidencia.count(), 1)

    def test_impacto_conta_somente_atividades_pendentes_e_exige_gestor(self):
        for project, node in self.projects:
            for status in Activity.Status.values:
                activity = self.activity(project, node)
                Activity.objects.filter(pk=activity.pk).update(status=status)
            url = reverse("projects:evidence-impact", kwargs={"project_id": project.id})
            self.client.force_authenticate(user=self.manager)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["pendingActivities"], 3)
            for user in (self.tester, self.dev):
                self.client.force_authenticate(user=user)
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_alteracao_pelo_admin_tambem_registra_historico(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from apps.projects.admin import ProjectAdmin

        project, _ = self.projects[0]
        request = RequestFactory().post("/admin/projects/project/")
        request.user = self.manager
        project.exigir_evidencia_issue = False
        ProjectAdmin(Project, admin.site).save_model(request, project, form=None, change=True)
        change = EvidenceRuleChange.objects.get(projeto=project)
        self.assertEqual(change.usuario, self.manager)
        self.assertTrue(change.valores_anteriores["exigir_evidencia_issue"])
        self.assertFalse(change.valores_novos["exigir_evidencia_issue"])

    def test_alteracao_nao_invalida_registros_antigos_mas_rege_proximas_acoes(self):
        for project, node in self.projects:
            self.configure(project, False, False)
            self.client.force_authenticate(user=self.tester)
            completed = self.activity(project, node)
            response = self.client.post(reverse("activities:complete", kwargs={"project_id": project.id, "activity_id": completed.id}), {}, format="json")
            self.assertEqual(response.status_code, 200)
            linked = self.activity(project, node)
            response = self.client.post(reverse("issues:list", kwargs={"project_id": project.id}), self.issue_payload(linked), format="json")
            self.assertEqual(response.status_code, 201)
            issue = Issue.objects.get(atividade=linked)
            self.configure(project, True, True)
            completed.refresh_from_db()
            issue.refresh_from_db()
            self.assertEqual(completed.status, Activity.Status.CONCLUIDO)
            self.assertIsNone(completed.evidencia_aprovacao)
            self.assertEqual(issue.status, Issue.Status.ABERTA)
            self.assertIsNone(issue.anexo_abertura)
            self.client.force_authenticate(user=self.tester)
            pending = self.activity(project, node)
            url = reverse("activities:complete", kwargs={"project_id": project.id, "activity_id": pending.id})
            self.assertEqual(self.client.post(url, {}, format="json").status_code, 400)
            self.configure(project, False, False)
            self.client.force_authenticate(user=self.tester)
            self.assertEqual(self.client.post(url, {}, format="json").status_code, 200)

    def issue_payload(self, activity, impeditiva=True):
        return {"title": "Falha", "description": "Descricao", "type": "requisito", "impact": "alto",
                "impeditiva": impeditiva, "relatedActivityId": activity.codigo_visivel, "developerId": str(self.dev.id)}

    def test_flags_salvas_sao_respeitadas_separadamente_em_uat_e_cutover(self):
        for project, node in self.projects:
            for activity_required in (False, True):
                for issue_required in (False, True):
                    with self.subTest(mode=project.modo, activity_required=activity_required, issue_required=issue_required):
                        self.configure(project, activity_required, issue_required)
                        self.client.force_authenticate(user=self.tester)
                        for payload, fmt in (({}, "json"), ({"approvalEvidence": None}, "json"), ({"approvalNote": "Sem anexo"}, "multipart")):
                            activity = self.activity(project, node)
                            response = self.client.post(reverse("activities:complete", kwargs={"project_id": project.id, "activity_id": activity.id}), payload, format=fmt)
                            self.assertEqual(response.status_code, 400 if activity_required else 200, response.data)
                            activity.refresh_from_db()
                            self.assertEqual(activity.status, Activity.Status.LIBERADO if activity_required else Activity.Status.CONCLUIDO)
                            self.assertIsNone(activity.evidencia_aprovacao)
                        for impeditiva in (False, True):
                            activity = self.activity(project, node)
                            response = self.client.post(reverse("issues:list", kwargs={"project_id": project.id}), self.issue_payload(activity, impeditiva), format="json")
                            required = issue_required and impeditiva
                            disallowed = project.modo == Project.Modo.CUTOVER and not impeditiva
                            self.assertEqual(response.status_code, 400 if required or disallowed else 201, response.data)

    def test_servico_de_conclusao_tambem_respeita_a_flag(self):
        for project, node in self.projects:
            self.configure(project, False, True)
            activity = self.activity(project, node)
            concluir_activity(activity=activity, evidencia_aprovacao=None, usuario=self.tester)
            self.assertEqual(activity.status, Activity.Status.CONCLUIDO)
            self.configure(project, True, False)
            activity = self.activity(project, node)
            with self.assertRaises(ValidationError):
                concluir_activity(activity=activity, evidencia_aprovacao=None, usuario=self.tester)

    @patch("apps.activities.services.upload_evidencia")
    @patch("apps.issues.services.upload_evidencia")
    def test_limite_de_tamanho_em_todos_os_uploads_inclusive_evidencia_opcional(self, issue_upload, activity_upload):
        for project, node in self.projects:
            for max_mb, size, allowed in ((1, 1024 * 1024, True), (1, 1024 * 1024 + 1, False), (2, 1024 * 1024 + 1, True)):
                for kind in ("activity", "opening", "solution"):
                    with self.subTest(mode=project.modo, kind=kind, max_mb=max_mb, size=size):
                        self.configure(project, False, False, max_mb)
                        activity_upload.reset_mock()
                        issue_upload.reset_mock()
                        activity_upload.return_value = self.evidence
                        issue_upload.return_value = self.evidence
                        activity = self.activity(project, node)
                        file = SimpleUploadedFile("proof.png", b"x" * size, content_type="image/png")
                        self.client.force_authenticate(user=self.tester)
                        if kind == "activity":
                            url = reverse("activities:complete", kwargs={"project_id": project.id, "activity_id": activity.id})
                            payload = {"approvalFile": file}
                            upload = activity_upload
                        elif kind == "opening":
                            url = reverse("issues:list", kwargs={"project_id": project.id})
                            payload = {**self.issue_payload(activity), "openingFile": file}
                            upload = issue_upload
                        else:
                            issue = Issue.objects.create(
                                projeto=project, atividade=activity, titulo="Falha", descricao="Descricao",
                                tipo=Issue.Tipo.REQUISITO, impacto=Issue.Impacto.ALTO,
                                tester=self.tester, desenvolvedor=self.dev, status=Issue.Status.EM_ANALISE,
                            )
                            self.client.force_authenticate(user=self.dev)
                            url = reverse("issues:propose-solution", kwargs={"project_id": project.id, "issue_id": issue.id})
                            payload = {"proposedSolution": "Corrigido", "solutionFile": file}
                            upload = issue_upload
                        response = self.client.post(url, payload, format="multipart")
                        expected = (201 if kind == "opening" else 200) if allowed else 400
                        self.assertEqual(response.status_code, expected, response.data)
                        self.assertEqual(upload.call_count, int(allowed))
                        if not allowed:
                            activity.refresh_from_db()
                            self.assertEqual(activity.status, Activity.Status.LIBERADO)

    def test_audio_e_video_continuam_proibidos_com_obrigatoriedade_desligada(self):
        for project, node in self.projects:
            self.configure(project, False, False)
            for filename, mime in (("audio.mp3", "audio/mpeg"), ("video.mp4", "video/mp4")):
                with self.subTest(mode=project.modo, filename=filename):
                    activity = self.activity(project, node)
                    self.client.force_authenticate(user=self.tester)
                    metadata = {"fileName": filename, "contentType": mime}
                    response = self.client.post(reverse("activities:complete", kwargs={"project_id": project.id, "activity_id": activity.id}), {"approvalEvidence": metadata}, format="json")
                    self.assertEqual(response.status_code, 400)
                    response = self.client.post(reverse("issues:list", kwargs={"project_id": project.id}), {**self.issue_payload(activity), "openingAttachment": metadata}, format="json")
                    self.assertEqual(response.status_code, 400)

    def test_flag_de_issue_se_aplica_a_abertura_impeditiva_nao_a_solucao(self):
        for project, node in self.projects:
            self.configure(project, True, True)
            activity = self.activity(project, node)
            issue = Issue.objects.create(
                projeto=project, atividade=activity, titulo="Falha", descricao="Descricao",
                tipo=Issue.Tipo.REQUISITO, impacto=Issue.Impacto.ALTO, impeditiva=True,
                tester=self.tester, desenvolvedor=self.dev, status=Issue.Status.EM_ANALISE,
            )
            self.client.force_authenticate(user=self.dev)
            response = self.client.post(reverse("issues:propose-solution", kwargs={"project_id": project.id, "issue_id": issue.id}), {"proposedSolution": "Corrigido"}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
