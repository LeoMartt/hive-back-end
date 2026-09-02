from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import Usuario

from ..models import Membership, NoHierarquia, Papel, Project


class ProjectModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            username="gestor",
            email="gestor@fumep.edu.br",
            password="senha-local-dev",
        )

    def test_project_defaults_refletem_modelagem(self):
        project = Project.objects.create(
            nome="CRM Homologação Comercial",
            modo=Project.Modo.UAT,
            nivel1_nome="Área",
            nivel2_nome="Cenário",
            criado_por=self.usuario,
        )

        self.assertEqual(project.aging_alerta_dias, 2)
        self.assertEqual(project.aging_risco_dias, 6)
        self.assertEqual(project.spi_saudavel, Decimal("0.90"))
        self.assertEqual(project.spi_critico, Decimal("0.75"))
        self.assertEqual(project.anexo_max_mb, 10)
        self.assertTrue(project.exigir_evidencia_atividade)
        self.assertTrue(project.exigir_evidencia_issue)
        self.assertEqual(project.proximo_codigo_atividade, 1)
        self.assertEqual(project.proximo_codigo_issue, 1)
        self.assertEqual(project.nomes_niveis_hierarquia, ["Área", "Cenário"])

    def test_project_cutover_nao_aceita_segundo_nivel(self):
        project = Project(
            nome="ERP Cutover",
            modo=Project.Modo.CUTOVER,
            nivel1_nome="Módulo",
            nivel2_nome="Cenário",
            criado_por=self.usuario,
        )

        with self.assertRaises(ValidationError):
            project.full_clean()


class NoHierarquiaModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            username="gestor",
            email="gestor@fumep.edu.br",
            password="senha-local-dev",
        )
        cls.project = Project.objects.create(
            nome="CRM Homologação Comercial",
            modo=Project.Modo.UAT,
            nivel1_nome="Área",
            nivel2_nome="Cenário",
            criado_por=cls.usuario,
        )

    def test_no_nivel_1_nao_aceita_parent(self):
        raiz = NoHierarquia.objects.create(
            projeto=self.project,
            nivel=NoHierarquia.Nivel.NIVEL_1,
            nome="Fiscal",
        )
        no = NoHierarquia(
            projeto=self.project,
            parent=raiz,
            nivel=NoHierarquia.Nivel.NIVEL_1,
            nome="Cenário A",
        )

        with self.assertRaises(ValidationError):
            no.full_clean()

    def test_no_nivel_2_exige_parent_do_mesmo_projeto(self):
        no = NoHierarquia(
            projeto=self.project,
            nivel=NoHierarquia.Nivel.NIVEL_2,
            nome="Cenário A",
        )

        with self.assertRaises(ValidationError):
            no.full_clean()

    def test_projeto_cutover_nao_aceita_no_nivel_2(self):
        cutover = Project.objects.create(
            nome="ERP Cutover",
            modo=Project.Modo.CUTOVER,
            nivel1_nome="Módulo",
            criado_por=self.usuario,
        )
        raiz = NoHierarquia.objects.create(
            projeto=cutover,
            nivel=NoHierarquia.Nivel.NIVEL_1,
            nome="Financeiro",
        )
        no = NoHierarquia(
            projeto=cutover,
            parent=raiz,
            nivel=NoHierarquia.Nivel.NIVEL_2,
            nome="Cenário A",
        )

        with self.assertRaises(ValidationError):
            no.full_clean()


class MembershipModelTests(TestCase):
    def test_usuario_pode_ter_multiplos_papeis_no_mesmo_projeto(self):
        usuario = Usuario.objects.create_user(
            username="tester",
            email="tester@fumep.edu.br",
            password="senha-local-dev",
        )
        project = Project.objects.create(
            nome="CRM Homologação Comercial",
            modo=Project.Modo.UAT,
            nivel1_nome="Área",
            nivel2_nome="Cenário",
            criado_por=usuario,
        )
        gestor = Papel.objects.get(codigo=Papel.Codigo.GESTOR)
        tester = Papel.objects.get(codigo=Papel.Codigo.TESTER)

        Membership.objects.create(usuario=usuario, projeto=project, papel=gestor)
        Membership.objects.create(usuario=usuario, projeto=project, papel=tester)

        self.assertEqual(Membership.objects.filter(usuario=usuario, projeto=project).count(), 2)
