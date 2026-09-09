from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.projects.models import NoHierarquia, Project

from ..models import Activity


class ActivityModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            username="gestor",
            email="gestor@fumep.edu.br",
            password="senha-local-dev",
        )
        cls.project = Project.objects.create(
            nome="ERP UAT",
            modo=Project.Modo.UAT,
            nivel1_nome="Área",
            nivel2_nome="Processo",
            criado_por=cls.usuario,
        )
        cls.raiz = NoHierarquia.objects.create(
            projeto=cls.project,
            nivel=NoHierarquia.Nivel.NIVEL_1,
            nome="Fiscal",
        )
        cls.processo = NoHierarquia.objects.create(
            projeto=cls.project,
            parent=cls.raiz,
            nivel=NoHierarquia.Nivel.NIVEL_2,
            nome="NF-e",
        )

    def test_codigo_visivel_e_derivado_do_id(self):
        activity = Activity.objects.create(
            projeto=self.project,
            no=self.processo,
            nome="Validar NF-e",
            tester=self.usuario,
            desenvolvedor=self.usuario,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
        )

        self.assertEqual(activity.codigo_visivel, f"ATV-{activity.id:04d}")

    def test_uat_nao_aceita_no_nivel_1(self):
        activity = Activity(
            projeto=self.project,
            no=self.raiz,
            nome="Atividade inválida",
            tester=self.usuario,
            desenvolvedor=self.usuario,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
        )

        with self.assertRaises(ValidationError):
            activity.full_clean()

    def test_cutover_aceita_no_nivel_1(self):
        cutover = Project.objects.create(
            nome="ERP Cutover",
            modo=Project.Modo.CUTOVER,
            nivel1_nome="Frente",
            criado_por=self.usuario,
        )
        no = NoHierarquia.objects.create(
            projeto=cutover,
            nivel=NoHierarquia.Nivel.NIVEL_1,
            nome="Cargas",
        )
        activity = Activity(
            projeto=cutover,
            no=no,
            nome="Importar clientes",
            tester=self.usuario,
            desenvolvedor=self.usuario,
            data_inicio_planejada=date(2026, 9, 1),
            data_conclusao_planejada=date(2026, 9, 2),
        )

        activity.full_clean()

    def test_data_planejada_inicio_nao_pode_ser_maior_que_conclusao(self):
        activity = Activity(
            projeto=self.project,
            no=self.processo,
            nome="Datas inválidas",
            tester=self.usuario,
            desenvolvedor=self.usuario,
            data_inicio_planejada=date(2026, 9, 3),
            data_conclusao_planejada=date(2026, 9, 2),
        )

        with self.assertRaises(ValidationError):
            activity.full_clean()
