from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Usuario
from apps.projects.models import Membership, NoHierarquia, Papel, Project
from apps.projects.services import salvar_no_hierarquia


DEV_SEED_MARKER = "[DEV SEED]"


@dataclass(frozen=True)
class SeedNode:
    nome: str
    filhos: tuple[str, ...] = ()


@dataclass(frozen=True)
class SeedProject:
    nome: str
    descricao: str
    modo: Project.Modo
    nivel1_nome: str
    nivel2_nome: str | None
    nos: tuple[SeedNode, ...]


SEED_PROJECTS = (
    SeedProject(
        nome="HIVE UAT Demo",
        descricao=f"{DEV_SEED_MARKER} Projeto temporario para testes locais da tela de UAT.",
        modo=Project.Modo.UAT,
        nivel1_nome="Area",
        nivel2_nome="Processo",
        nos=(
            SeedNode("Financeiro", ("Contas a Pagar", "Contas a Receber")),
            SeedNode("Compras", ("Pedido de Compra", "Aprovacao")),
            SeedNode("Fiscal", ("Nota Fiscal", "Apuracao")),
        ),
    ),
    SeedProject(
        nome="HIVE Cutover Demo",
        descricao=f"{DEV_SEED_MARKER} Projeto temporario para testes locais da tela de Cutover.",
        modo=Project.Modo.CUTOVER,
        nivel1_nome="Frente",
        nivel2_nome=None,
        nos=(
            SeedNode("Cargas"),
            SeedNode("Validacoes"),
            SeedNode("Go-live"),
        ),
    ),
)


class Command(BaseCommand):
    help = (
        "Cria dados temporarios de desenvolvimento para projects. "
        "Os registros ficam marcados com [DEV SEED] para remocao futura."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", help="E-mail do Usuario que recebera acesso aos projetos.")
        parser.add_argument("--username", help="Username do Usuario que recebera acesso aos projetos.")
        parser.add_argument(
            "--entra-object-id",
            dest="entra_object_id",
            help="Claim oid/ID do objeto Entra do Usuario que recebera acesso aos projetos.",
        )
        parser.add_argument(
            "--roles",
            choices=("gestor", "all"),
            default="all",
            help="Papeis criados para o usuario nos projetos seedados. Default: all.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove projetos seedados antes de recria-los.",
        )
        parser.add_argument(
            "--clear-only",
            action="store_true",
            help="Remove projetos seedados e nao cria novos registros.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"] or options["clear_only"]:
            deletados = self._limpar_seed()
            self.stdout.write(self.style.WARNING(f"Dados temporarios removidos: {deletados} projeto(s)."))

        if options["clear_only"]:
            return

        usuario = self._resolver_usuario(
            email=options.get("email"),
            username=options.get("username"),
            entra_object_id=options.get("entra_object_id"),
        )
        codigos_papeis = self._codigos_papeis(options["roles"])

        for seed_project in SEED_PROJECTS:
            projeto, criado = self._criar_ou_atualizar_projeto(seed_project, usuario)
            self._garantir_memberships(projeto, usuario, codigos_papeis)
            self._garantir_hierarquia(projeto, seed_project.nos)
            acao = "criado" if criado else "atualizado"
            self.stdout.write(self.style.SUCCESS(f"{projeto.nome}: {acao}."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed finalizado para {usuario.email}. "
                "Use --clear-only para remover estes dados temporarios."
            )
        )

    def _limpar_seed(self) -> int:
        queryset = Project.objects.filter(descricao__startswith=DEV_SEED_MARKER)
        total = queryset.count()
        queryset.delete()
        return total

    def _resolver_usuario(
        self,
        *,
        email: str | None,
        username: str | None,
        entra_object_id: str | None,
    ) -> Usuario:
        filtros = [bool(email), bool(username), bool(entra_object_id)]
        if sum(filtros) > 1:
            raise CommandError("Informe apenas um identificador: --email, --username ou --entra-object-id.")

        if email:
            usuario = Usuario.objects.filter(email__iexact=email).first()
            if not usuario:
                raise CommandError(f"Usuario com e-mail {email} nao encontrado.")
            return usuario

        if username:
            usuario = Usuario.objects.filter(username=username).first()
            if not usuario:
                raise CommandError(f"Usuario com username {username} nao encontrado.")
            return usuario

        if entra_object_id:
            try:
                object_id = uuid.UUID(str(entra_object_id))
            except ValueError as exc:
                raise CommandError("--entra-object-id deve ser um UUID valido.") from exc

            usuario = Usuario.objects.filter(entra_object_id=object_id).first()
            if not usuario:
                raise CommandError(f"Usuario com entra_object_id {object_id} nao encontrado.")
            return usuario

        usuarios_entra = Usuario.objects.filter(entra_object_id__isnull=False)
        if usuarios_entra.count() == 1:
            return usuarios_entra.get()

        raise CommandError(
            "Nao foi possivel escolher o usuario automaticamente. "
            "Informe --email, --username ou --entra-object-id."
        )

    def _codigos_papeis(self, roles: str) -> tuple[str, ...]:
        if roles == "gestor":
            return (Papel.Codigo.GESTOR,)
        return (Papel.Codigo.GESTOR, Papel.Codigo.TESTER, Papel.Codigo.DEV)

    def _criar_ou_atualizar_projeto(self, seed: SeedProject, usuario: Usuario) -> tuple[Project, bool]:
        projeto = Project.objects.filter(
            nome=seed.nome,
            descricao__startswith=DEV_SEED_MARKER,
        ).first()
        criado = projeto is None

        if criado:
            projeto = Project(criado_por=usuario)

        projeto.nome = seed.nome
        projeto.descricao = seed.descricao
        projeto.modo = seed.modo
        projeto.nivel1_nome = seed.nivel1_nome
        projeto.nivel2_nome = seed.nivel2_nome
        if criado:
            projeto.criado_por = usuario

        try:
            projeto.full_clean()
            projeto.save()
        except ValidationError as exc:
            raise CommandError(exc.message_dict) from exc

        return projeto, criado

    def _garantir_memberships(
        self,
        projeto: Project,
        usuario: Usuario,
        codigos_papeis: Iterable[str],
    ) -> None:
        for codigo in codigos_papeis:
            papel = Papel.objects.get(codigo=codigo)
            Membership.objects.get_or_create(
                usuario=usuario,
                projeto=projeto,
                papel=papel,
                defaults={"convidado_por": usuario},
            )

    def _garantir_hierarquia(self, projeto: Project, nos: tuple[SeedNode, ...]) -> None:
        for ordem_raiz, seed_node in enumerate(nos, start=1):
            raiz = self._garantir_no(
                projeto=projeto,
                parent=None,
                nivel=NoHierarquia.Nivel.NIVEL_1,
                nome=seed_node.nome,
                ordem=ordem_raiz,
            )
            for ordem_filho, nome_filho in enumerate(seed_node.filhos, start=1):
                self._garantir_no(
                    projeto=projeto,
                    parent=raiz,
                    nivel=NoHierarquia.Nivel.NIVEL_2,
                    nome=nome_filho,
                    ordem=ordem_filho,
                )

    def _garantir_no(
        self,
        *,
        projeto: Project,
        parent: NoHierarquia | None,
        nivel: int,
        nome: str,
        ordem: int,
    ) -> NoHierarquia:
        no, _ = NoHierarquia.objects.get_or_create(
            projeto=projeto,
            parent=parent,
            nome=nome,
            defaults={"nivel": nivel, "ordem": ordem},
        )
        no.nivel = nivel
        no.ordem = ordem
        return salvar_no_hierarquia(no)
