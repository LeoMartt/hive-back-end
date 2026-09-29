from datetime import date
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.projects.models import Membership, NoHierarquia, Papel, Project

from ..models import Activity, ActivityPredecessor


class ActivityViewTests(APITestCase):
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
        cls.outro = Usuario.objects.create_user(
            username="outro",
            email="outro@fumep.edu.br",
            password="senha-local-dev",
        )
        cls.papel_gestor = Papel.objects.get(codigo=Papel.Codigo.GESTOR)
        cls.papel_tester = Papel.objects.get(codigo=Papel.Codigo.TESTER)
        cls.papel_dev = Papel.objects.get(codigo=Papel.Codigo.DEV)
        cls.project = Project.objects.create(
            nome="ERP UAT",
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
        ]:
            Membership.objects.create(usuario=usuario, projeto=cls.project, papel=papel)

    def evidencia(self, file_name="evidencia.pdf", content_type="application/pdf"):
        return {
            "fileName": file_name,
            "sizeLabel": "10 KB",
            "uploadedBy": "Tester Um",
            "uploadedAt": "2026-09-01T10:00:00",
            "contentType": content_type,
        }

    def test_sem_autenticacao_retorna_401(self):
        response = self.client.get(reverse("activities:list", kwargs={"project_id": self.project.id}))

        self.assertEqual(response.status_code, 401)

    def test_gestor_cria_activity_sem_predecessora_liberada(self):
        self.client.force_authenticate(user=self.gestor)
        payload = {
            "nodeId": str(self.processo.id),
            "name": "Validar cálculo de ICMS",
            "testerId": str(self.tester.id),
            "developerId": str(self.dev.id),
            "plannedStart": "2026-09-01",
            "plannedEnd": "2026-09-05",
            "area": "Fiscal",
            "system": "SAP",
            "transaction": "VF01",
            "expectedResult": "NF-e emitida sem divergência.",
            "notes": "Cenário principal.",
        }

        response = self.client.post(
            reverse("activities:list", kwargs={"project_id": self.project.id}),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        activity = Activity.objects.get()
        self.assertEqual(activity.status, Activity.Status.LIBERADO)
        self.assertEqual(response.data["id"], activity.codigo_visivel)
        self.assertEqual(response.data["numericId"], activity.id)
        self.assertEqual(response.data["module"], "Faturamento")
        self.assertEqual(response.data["process"], "Emissão de NF-e")
        self.assertEqual(response.data["tester"], "Tester Um")
        self.assertEqual(response.data["dev"], "Dev Um")
        self.assertEqual(response.data["status"], "liberado")

    def test_activity_com_predecessora_nasce_aguardando(self):
        predecessor = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Preparar massa",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=Activity.Status.LIBERADO,
        )
        self.client.force_authenticate(user=self.gestor)

        response = self.client.post(
            reverse("activities:list", kwargs={"project_id": self.project.id}),
            {
                "nodeId": str(self.processo.id),
                "name": "Executar teste",
                "testerId": str(self.tester.id),
                "developerId": str(self.dev.id),
                "plannedStart": "2026-09-03",
                "plannedEnd": "2026-09-05",
                "predecessorIds": [predecessor.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        activity = Activity.objects.get(nome="Executar teste")
        self.assertEqual(activity.status, Activity.Status.AGUARDANDO)
        self.assertTrue(
            ActivityPredecessor.objects.filter(atividade=activity, predecessora=predecessor).exists()
        )
        self.assertEqual(response.data["predecessors"], [predecessor.codigo_visivel])

    def test_import_csv_cria_activities_com_predecessoras_temporarias(self):
        self.client.force_authenticate(user=self.gestor)
        content = (
            "Modulo,Processo,Atividade nome,Tester email,Dev email,Data inicio planejado,"
            "Data final planejada,Id lista sequencial (temporario),Predecessores,Sistema,Area,"
            "Transação,Resultado esperado,Observações\n"
            "Faturamento,Emissão de NF-e,Preparar massa,tester@fumep.edu.br,dev@fumep.edu.br,"
            "01/09/2026,02/09/2026,1,,SAP,Fiscal,VF01,Massa preparada,Primeira linha\n"
            "Faturamento,Emissão de NF-e,Executar teste,tester@fumep.edu.br,dev@fumep.edu.br,"
            "03/09/2026,05/09/2026,2,1,SAP,Fiscal,VF02,NF-e emitida,Depende da linha 1\n"
        )
        uploaded = SimpleUploadedFile(
            "atividades.csv",
            content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("activities:import", kwargs={"project_id": self.project.id}),
            {"file": uploaded},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["created"], 2)
        first = Activity.objects.get(nome="Preparar massa")
        second = Activity.objects.get(nome="Executar teste")
        self.assertEqual(first.status, Activity.Status.LIBERADO)
        self.assertEqual(second.status, Activity.Status.AGUARDANDO)
        self.assertEqual(first.sistema, "SAP")
        self.assertTrue(ActivityPredecessor.objects.filter(atividade=second, predecessora=first).exists())
        self.assertEqual(response.data["activities"][1]["predecessors"], [first.codigo_visivel])

    def test_import_csv_com_erro_nao_cria_nada(self):
        self.client.force_authenticate(user=self.gestor)
        content = (
            "Modulo,Processo,Atividade nome,Tester email,Dev email,Data inicio planejado,"
            "Data final planejada,Id lista sequencial (temporario),Predecessores\n"
            "Faturamento,Emissão de NF-e,Executar teste,inexistente@fumep.edu.br,dev@fumep.edu.br,"
            "03/09/2026,05/09/2026,1,\n"
        )
        uploaded = SimpleUploadedFile(
            "atividades.csv",
            content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("activities:import", kwargs={"project_id": self.project.id}),
            {"file": uploaded},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("rows", response.data)
        self.assertEqual(Activity.objects.count(), 0)

    def test_create_rejeita_tester_sem_membership_tester(self):
        self.client.force_authenticate(user=self.gestor)

        response = self.client.post(
            reverse("activities:list", kwargs={"project_id": self.project.id}),
            {
                "nodeId": str(self.processo.id),
                "name": "Executar teste",
                "testerId": str(self.gestor.id),
                "developerId": str(self.dev.id),
                "plannedStart": "2026-09-03",
                "plannedEnd": "2026-09-05",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("testerId", response.data)

    def test_create_rejeita_no_nivel_1_para_uat(self):
        self.client.force_authenticate(user=self.gestor)

        response = self.client.post(
            reverse("activities:list", kwargs={"project_id": self.project.id}),
            {
                "nodeId": str(self.raiz.id),
                "name": "Executar teste",
                "testerId": str(self.tester.id),
                "developerId": str(self.dev.id),
                "plannedStart": "2026-09-03",
                "plannedEnd": "2026-09-05",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("nodeId", response.data)

    def test_membro_do_projeto_lista_activities(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
        )
        self.client.force_authenticate(user=self.tester)

        response = self.client.get(reverse("activities:list", kwargs={"project_id": self.project.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], activity.codigo_visivel)

    def test_usuario_fora_do_projeto_nao_lista_activities(self):
        self.client.force_authenticate(user=self.outro)

        response = self.client.get(reverse("activities:list", kwargs={"project_id": self.project.id}))

        self.assertEqual(response.status_code, 404)

    def test_gestor_atualiza_activity(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
        )
        self.client.force_authenticate(user=self.gestor)

        response = self.client.patch(
            reverse("activities:detail", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {"name": "Validar NF-e atualizada", "area": "Fiscal"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        activity.refresh_from_db()
        self.assertEqual(activity.nome, "Validar NF-e atualizada")
        self.assertEqual(activity.area, "Fiscal")

    def test_gestor_nao_troca_no_da_activity(self):
        outro_processo = NoHierarquia.objects.create(
            projeto=self.project,
            parent=self.raiz,
            nivel=NoHierarquia.Nivel.NIVEL_2,
            nome="Recebimento",
        )
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
        )
        self.client.force_authenticate(user=self.gestor)

        response = self.client.patch(
            reverse("activities:detail", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {"nodeId": str(outro_processo.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        activity.refresh_from_db()
        self.assertEqual(activity.no_id, self.processo.id)

    def test_activity_concluida_nao_e_atualizada(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=Activity.Status.CONCLUIDO,
        )
        self.client.force_authenticate(user=self.gestor)

        response = self.client.patch(
            reverse("activities:detail", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {"name": "Não deve mudar"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        activity.refresh_from_db()
        self.assertEqual(activity.nome, "Validar NF-e")

    def test_gestor_atualiza_activity_bloqueada(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=Activity.Status.BLOQUEADO,
        )
        self.client.force_authenticate(user=self.gestor)

        response = self.client.patch(
            reverse("activities:detail", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {"notes": "Aguardando ajuste do desenvolvedor."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.BLOQUEADO)
        self.assertEqual(activity.observacoes, "Aguardando ajuste do desenvolvedor.")

    def test_nao_gestor_nao_atualiza_activity(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
        )
        self.client.force_authenticate(user=self.tester)

        response = self.client.patch(
            reverse("activities:detail", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {"name": "Não deve mudar"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_gestor_cancela_activity(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
        )
        self.client.force_authenticate(user=self.gestor)

        response = self.client.post(
            reverse("activities:cancel", kwargs={"project_id": self.project.id, "activity_id": activity.id})
        )

        self.assertEqual(response.status_code, 200)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.CANCELADO)
        self.assertEqual(response.data["status"], "cancelado")

    def test_tester_conclui_activity_propria(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=Activity.Status.LIBERADO,
        )
        self.client.force_authenticate(user=self.tester)

        response = self.client.post(
            reverse("activities:complete", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {
                "approvalNote": "Cenário validado.",
                "approvalEvidence": self.evidencia(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.CONCLUIDO)
        self.assertEqual(response.data["status"], "concluido")
        self.assertEqual(activity.observacao_aprovacao, "Cenário validado.")
        self.assertEqual(activity.evidencia_aprovacao["fileName"], "evidencia.pdf")
        self.assertEqual(response.data["approvalEvidence"]["fileName"], "evidencia.pdf")

    @patch("apps.activities.services.upload_evidencia")
    def test_tester_conclui_activity_com_upload_real_de_evidencia(self, upload_evidencia):
        upload_evidencia.return_value = {
            **self.evidencia("print-validacao.png", "image/png"),
            "storagePath": "projects/proj/activities/ATV-0001/approval/abc-print-validacao.png",
            "url": "https://storage.test/blob?sas=1",
            "urlExpiresAt": "2027-03-01T10:00:00+00:00",
        }
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=Activity.Status.LIBERADO,
        )
        uploaded = SimpleUploadedFile(
            "print-validacao.png",
            b"fake image",
            content_type="image/png",
        )
        self.client.force_authenticate(user=self.tester)

        response = self.client.post(
            reverse("activities:complete", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {
                "approvalNote": "Cenário validado.",
                "approvalFile": uploaded,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.CONCLUIDO)
        self.assertEqual(activity.evidencia_aprovacao["storagePath"], upload_evidencia.return_value["storagePath"])
        self.assertEqual(response.data["approvalEvidence"]["url"], "https://storage.test/blob?sas=1")
        upload_evidencia.assert_called_once()

    def test_concluir_activity_sem_evidencia_retorna_400(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=Activity.Status.LIBERADO,
        )
        self.client.force_authenticate(user=self.tester)

        response = self.client.post(
            reverse("activities:complete", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {"approvalNote": "Cenário validado."},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.LIBERADO)

    def test_concluir_activity_rejeita_audio_video_como_evidencia(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=Activity.Status.LIBERADO,
        )
        self.client.force_authenticate(user=self.tester)

        response = self.client.post(
            reverse("activities:complete", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {
                "approvalNote": "Cenário validado.",
                "approvalEvidence": self.evidencia("evidencia.mp4", "video/mp4"),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.LIBERADO)

    def test_tester_bloqueia_activity_propria(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=Activity.Status.LIBERADO,
        )
        self.client.force_authenticate(user=self.tester)

        response = self.client.post(
            reverse("activities:block", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {"reason": "Divergência encontrada."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.BLOQUEADO)
        self.assertEqual(response.data["status"], "bloqueado")

    def test_dev_nao_bloqueia_activity(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=Activity.Status.LIBERADO,
        )
        self.client.force_authenticate(user=self.dev)

        response = self.client.post(
            reverse("activities:block", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {"reason": "Dev não deve reprovar."},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        activity.refresh_from_db()
        self.assertEqual(activity.status, Activity.Status.LIBERADO)

    def test_activity_cancelada_nao_e_atualizada(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.tester,
            desenvolvedor=self.dev,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
            status=Activity.Status.CANCELADO,
        )
        self.client.force_authenticate(user=self.gestor)

        response = self.client.patch(
            reverse("activities:detail", kwargs={"project_id": self.project.id, "activity_id": activity.id}),
            {"name": "Não deve mudar"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        activity.refresh_from_db()
        self.assertEqual(activity.nome, "Validar NF-e")
