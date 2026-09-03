from io import StringIO
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.projects.management.commands.seed_dev_projects import DEV_SEED_MARKER

from ..models import Membership, NoHierarquia, Papel, Project


class SeedDevProjectsCommandTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="entra_usuario",
            email="47693@eep.br",
            password="senha-local-dev",
            entra_object_id=uuid4(),
            iniciais="LS",
        )

    def test_cria_projetos_memberships_e_hierarquia_para_usuario_entra(self):
        output = StringIO()

        call_command("seed_dev_projects", email=self.usuario.email, stdout=output)

        projetos = Project.objects.filter(descricao__startswith=DEV_SEED_MARKER)
        self.assertEqual(projetos.count(), 2)
        self.assertTrue(projetos.filter(nome="HIVE UAT Demo", modo=Project.Modo.UAT).exists())
        self.assertTrue(projetos.filter(nome="HIVE Cutover Demo", modo=Project.Modo.CUTOVER).exists())
        self.assertEqual(
            Membership.objects.filter(usuario=self.usuario, projeto__in=projetos).count(),
            projetos.count() * 3,
        )
        self.assertTrue(
            Membership.objects.filter(
                usuario=self.usuario,
                projeto__nome="HIVE UAT Demo",
                papel__codigo=Papel.Codigo.GESTOR,
            ).exists()
        )
        self.assertEqual(
            NoHierarquia.objects.filter(projeto__nome="HIVE UAT Demo", nivel=NoHierarquia.Nivel.NIVEL_1).count(),
            3,
        )
        self.assertEqual(
            NoHierarquia.objects.filter(projeto__nome="HIVE UAT Demo", nivel=NoHierarquia.Nivel.NIVEL_2).count(),
            6,
        )
        self.assertEqual(
            NoHierarquia.objects.filter(projeto__nome="HIVE Cutover Demo", nivel=NoHierarquia.Nivel.NIVEL_1).count(),
            3,
        )

    def test_comando_e_idempotente(self):
        call_command("seed_dev_projects", email=self.usuario.email, stdout=StringIO())
        call_command("seed_dev_projects", email=self.usuario.email, stdout=StringIO())

        projetos = Project.objects.filter(descricao__startswith=DEV_SEED_MARKER)
        self.assertEqual(projetos.count(), 2)
        self.assertEqual(Membership.objects.filter(usuario=self.usuario, projeto__in=projetos).count(), 6)
        self.assertEqual(NoHierarquia.objects.filter(projeto__in=projetos).count(), 12)

    def test_clear_only_remove_apenas_projetos_seedados(self):
        projeto_manual = Project.objects.create(
            nome="Projeto Manual",
            descricao="Criado fora do seed.",
            modo=Project.Modo.UAT,
            nivel1_nome="Area",
            nivel2_nome="Processo",
            criado_por=self.usuario,
        )
        call_command("seed_dev_projects", email=self.usuario.email, stdout=StringIO())

        call_command("seed_dev_projects", clear_only=True, stdout=StringIO())

        self.assertTrue(Project.objects.filter(id=projeto_manual.id).exists())
        self.assertFalse(Project.objects.filter(descricao__startswith=DEV_SEED_MARKER).exists())

    def test_sem_parametro_usa_unico_usuario_com_entra_object_id(self):
        call_command("seed_dev_projects", stdout=StringIO())

        self.assertEqual(Project.objects.filter(descricao__startswith=DEV_SEED_MARKER).count(), 2)
