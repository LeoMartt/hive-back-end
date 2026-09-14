from datetime import date

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.activities.models import Activity, ActivityPredecessor
from apps.projects.models import Membership, NoHierarquia, Papel, Project

from ..models import Issue


class IssueViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gestor = Usuario.objects.create_user(
            username="gestor",
            email="gestor@fumep.edu.br",
            password="senha-local-dev",
            first_name="Gestor Um",
            iniciais="GU",
        )
        cls.tester = Usuario.objects.create_user(
            username="tester",
            email="tester@fumep.edu.br",
            password="senha-local-dev",
            first_name="Tester Um",
            iniciais="TU",
        )
        cls.dev = Usuario.objects.create_user(
            username="dev",
            email="dev@fumep.edu.br",
            password="senha-local-dev",
            first_name="Dev Um",
            iniciais="DU",
        )
        cls.outro_dev = Usuario.objects.create_user(
            username="outro-dev",
            email="outro-dev@fumep.edu.br",
            password="senha-local-dev",
            first_name="Outro Dev",
            iniciais="OD",
        )
        cls.outro = Usuario.objects.create_user(
            username="outro",
            email="outro@fumep.edu.br",
            password="senha-local-dev",
        )
        cls.papel_gestor = Papel.objects.get(codigo=Papel.Codigo.GESTOR)
        cls.papel_tester = Papel.objects.get(codigo=Papel.Codigo.TESTER)
        cls.papel_dev = Papel.objects.get(codigo=Papel.Codigo.DEV)
        cls.project = Project.objects.create(
            nome="ERP UAT Issues",
            modo=Project.Modo.UAT,
            nivel1_nome="Área",
            nivel2_nome="Processo",
            criado_por=cls.gestor,
        )
        cls.raiz = NoHierarquia.objects.create(
            projeto=cls.project,
            nivel=NoHierarquia.Nivel.NIVEL_1,
            nome="Faturamento",
        )
        cls.processo = NoHierarquia.objects.create(
            projeto=cls.project,
            parent=cls.raiz,
            nivel=NoHierarquia.Nivel.NIVEL_2,
            nome="Emissão de NF-e",
        )
        for usuario, papel in [
            (cls.gestor, cls.papel_gestor),
            (cls.tester, cls.papel_tester),
            (cls.dev, cls.papel_dev),
            (cls.outro_dev, cls.papel_dev),
        ]:
            Membership.objects.create(usuario=usuario, projeto=cls.project, papel=papel)

    def criar_activity(self, status=Activity.Status.LIBERADO):
        return Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar cálculo de ICMS",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=status,
            area="Fiscal",
        )

    def payload_issue(self, activity):
        return {
            "title": "Alíquota incorreta na NF-e",
            "description": "Valor calculado diferente do esperado.",
            "type": "requisito",
            "impeditiva": True,
            "impact": "alto",
            "impactNote": "bloqueia o cenário fiscal",
            "developerId": str(self.dev.id),
            "relatedActivityId": activity.codigo_visivel,
            "openingAttachment": {
                "fileName": "evidencia.pdf",
                "sizeLabel": "10 KB",
                "uploadedBy": "Tester Um",
                "uploadedAt": "2026-09-01T10:00:00",
            },
        }

    def test_tester_cria_issue_vinculada_a_activity(self):
        activity = self.criar_activity()
        self.client.force_authenticate(user=self.tester)

        response = self.client.post(
            reverse("issues:list", kwargs={"project_id": self.project.id}),
            self.payload_issue(activity),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        issue = Issue.objects.get()
        activity.refresh_from_db()
        self.assertEqual(issue.atividade, activity)
        self.assertEqual(issue.status, Issue.Status.ABERTA)
        self.assertEqual(activity.status, Activity.Status.BLOQUEADO)
        self.assertEqual(activity.numero_retest, 1)
        self.assertEqual(issue.tester, self.tester)
        self.assertEqual(issue.desenvolvedor, self.dev)
        self.assertEqual(response.data["id"], issue.codigo_visivel)
        self.assertEqual(response.data["relatedActivityId"], activity.codigo_visivel)
        self.assertEqual(response.data["status"], "aberta")

    def test_issue_nao_impeditiva_nao_bloqueia_activity(self):
        activity = self.criar_activity()
        payload = self.payload_issue(activity)
        payload["impeditiva"] = False
        self.client.force_authenticate(user=self.tester)

        response = self.client.post(
            reverse("issues:list", kwargs={"project_id": self.project.id}),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.LIBERADO)
        self.assertEqual(activity.numero_retest, 0)

    def test_dev_nao_cria_issue(self):
        activity = self.criar_activity()
        self.client.force_authenticate(user=self.dev)

        response = self.client.post(
            reverse("issues:list", kwargs={"project_id": self.project.id}),
            self.payload_issue(activity),
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_start_analysis_e_manual_e_apenas_dev_responsavel(self):
        activity = self.criar_activity()
        issue = Issue.objects.create(
            projeto=self.project,
            atividade=activity,
            titulo="Erro fiscal",
            descricao="Falhou.",
            tipo=Issue.Tipo.REQUISITO,
            impacto=Issue.Impacto.ALTO,
            impeditiva=True,
            tester=self.tester,
            desenvolvedor=self.dev,
        )
        self.client.force_authenticate(user=self.outro_dev)

        denied = self.client.post(
            reverse("issues:start-analysis", kwargs={"project_id": self.project.id, "issue_id": issue.id})
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(user=self.dev)
        response = self.client.post(
            reverse("issues:start-analysis", kwargs={"project_id": self.project.id, "issue_id": issue.id})
        )

        self.assertEqual(response.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.EM_ANALISE)
        self.assertIsNotNone(issue.analise_iniciada_em)

    def test_dev_propoe_solucao(self):
        activity = self.criar_activity()
        issue = Issue.objects.create(
            projeto=self.project,
            atividade=activity,
            titulo="Erro fiscal",
            descricao="Falhou.",
            tipo=Issue.Tipo.REQUISITO,
            impacto=Issue.Impacto.ALTO,
            impeditiva=True,
            tester=self.tester,
            desenvolvedor=self.dev,
            status=Issue.Status.EM_ANALISE,
        )
        self.client.force_authenticate(user=self.dev)

        response = self.client.post(
            reverse("issues:propose-solution", kwargs={"project_id": self.project.id, "issue_id": issue.id}),
            {"proposedSolution": "Ajustado cálculo de ICMS."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.SOLUCAO_PROPOSTA)
        self.assertEqual(issue.solucao_proposta, "Ajustado cálculo de ICMS.")

    def test_tester_resolve_issue_e_libera_activity_sem_outras_issues_abertas(self):
        activity = self.criar_activity(status=Activity.Status.BLOQUEADO)
        issue = Issue.objects.create(
            projeto=self.project,
            atividade=activity,
            titulo="Erro fiscal",
            descricao="Falhou.",
            tipo=Issue.Tipo.REQUISITO,
            impacto=Issue.Impacto.ALTO,
            impeditiva=True,
            tester=self.tester,
            desenvolvedor=self.dev,
            status=Issue.Status.SOLUCAO_PROPOSTA,
        )
        self.client.force_authenticate(user=self.tester)

        response = self.client.post(
            reverse("issues:resolve", kwargs={"project_id": self.project.id, "issue_id": issue.id})
        )

        self.assertEqual(response.status_code, 200)
        issue.refresh_from_db()
        activity.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.CONCLUIDA)
        self.assertEqual(activity.status, Activity.Status.LIBERADO)

    def test_resolve_issue_nao_libera_activity_com_outra_issue_aberta(self):
        activity = self.criar_activity(status=Activity.Status.BLOQUEADO)
        issue = Issue.objects.create(
            projeto=self.project,
            atividade=activity,
            titulo="Erro fiscal",
            descricao="Falhou.",
            tipo=Issue.Tipo.REQUISITO,
            impacto=Issue.Impacto.ALTO,
            impeditiva=True,
            tester=self.tester,
            desenvolvedor=self.dev,
            status=Issue.Status.SOLUCAO_PROPOSTA,
        )
        Issue.objects.create(
            projeto=self.project,
            atividade=activity,
            titulo="Outro erro",
            descricao="Ainda aberto.",
            tipo=Issue.Tipo.DADOS,
            impacto=Issue.Impacto.MEDIO,
            impeditiva=False,
            tester=self.tester,
            desenvolvedor=self.dev,
            status=Issue.Status.ABERTA,
        )
        self.client.force_authenticate(user=self.tester)

        response = self.client.post(
            reverse("issues:resolve", kwargs={"project_id": self.project.id, "issue_id": issue.id})
        )

        self.assertEqual(response.status_code, 200)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.BLOQUEADO)

    def test_resolve_issue_respeita_predecessora_pendente(self):
        predecessor = self.criar_activity(status=Activity.Status.LIBERADO)
        activity = self.criar_activity(status=Activity.Status.BLOQUEADO)
        ActivityPredecessor.objects.create(atividade=activity, predecessora=predecessor)
        issue = Issue.objects.create(
            projeto=self.project,
            atividade=activity,
            titulo="Erro fiscal",
            descricao="Falhou.",
            tipo=Issue.Tipo.REQUISITO,
            impacto=Issue.Impacto.ALTO,
            impeditiva=True,
            tester=self.tester,
            desenvolvedor=self.dev,
            status=Issue.Status.SOLUCAO_PROPOSTA,
        )
        self.client.force_authenticate(user=self.tester)

        response = self.client.post(
            reverse("issues:resolve", kwargs={"project_id": self.project.id, "issue_id": issue.id})
        )

        self.assertEqual(response.status_code, 200)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.AGUARDANDO)

    def test_cancelar_activity_cancela_issues_abertas(self):
        activity = self.criar_activity(status=Activity.Status.BLOQUEADO)
        issue = Issue.objects.create(
            projeto=self.project,
            atividade=activity,
            titulo="Erro fiscal",
            descricao="Falhou.",
            tipo=Issue.Tipo.REQUISITO,
            impacto=Issue.Impacto.ALTO,
            impeditiva=True,
            tester=self.tester,
            desenvolvedor=self.dev,
            status=Issue.Status.EM_ANALISE,
        )
        self.client.force_authenticate(user=self.gestor)

        response = self.client.post(
            reverse("activities:cancel", kwargs={"project_id": self.project.id, "activity_id": activity.id})
        )

        self.assertEqual(response.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.CANCELADA)
