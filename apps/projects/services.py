import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError

from apps.accounts.models import Usuario

from .models import Membership, NoHierarquia, Papel, Project


ROLE_BY_LABEL = {
    "Gestor de Projetos": Papel.Codigo.GESTOR,
    "Tester": Papel.Codigo.TESTER,
    "Desenvolvedor": Papel.Codigo.DEV,
}


def usuario_pode_ver_projeto(usuario: Usuario, projeto: Project) -> bool:
    if usuario.is_staff or usuario.is_superuser:
        return True
    return Membership.objects.filter(usuario=usuario, projeto=projeto).exists()


def usuario_pode_gerenciar_projeto(usuario: Usuario, projeto: Project) -> bool:
    if usuario.is_staff or usuario.is_superuser:
        return True
    return Membership.objects.filter(
        usuario=usuario,
        projeto=projeto,
        papel__codigo=Papel.Codigo.GESTOR,
    ).exists()


def exigir_gestor(usuario: Usuario, projeto: Project) -> None:
    if not usuario_pode_gerenciar_projeto(usuario, projeto):
        raise PermissionDenied("Apenas gestores do projeto podem executar esta ação.")


def resolver_codigo_papel(valor: str) -> str:
    codigo = ROLE_BY_LABEL.get(valor, valor)
    codigos_validos = {choice.value for choice in Papel.Codigo}
    if codigo not in codigos_validos:
        raise DRFValidationError({"role": "Papel inválido."})
    return codigo


def gerar_iniciais(nome: str, email: str) -> str:
    partes = nome.split()
    if len(partes) >= 2:
        return f"{partes[0][0]}{partes[-1][0]}".upper()
    if len(partes) == 1:
        return partes[0][:2].upper()
    return email.split("@")[0][:2].upper()


def obter_ou_criar_usuario_convidado(dados: dict) -> Usuario:
    raw_id = dados.get("id")
    nome = (dados.get("name") or "").strip()
    email = Usuario.objects.normalize_email((dados.get("email") or "").strip())
    iniciais = (dados.get("initials") or "").strip().upper()

    object_id = None
    if raw_id:
        try:
            object_id = uuid.UUID(str(raw_id))
        except (TypeError, ValueError) as exc:
            raise DRFValidationError({"id": "ID do usuário deve ser um UUID válido."}) from exc

        usuario = Usuario.objects.filter(entra_object_id=object_id).first()
        if usuario:
            return usuario

        usuario = Usuario.objects.filter(id=object_id).first()
        if usuario:
            return usuario

    if not email:
        raise DRFValidationError({"email": "E-mail é obrigatório para convidar usuário novo."})

    usuario = Usuario.objects.filter(email__iexact=email).first()
    if usuario:
        if object_id and usuario.entra_object_id and usuario.entra_object_id != object_id:
            raise DRFValidationError(
                {"email": "Já existe usuário com este e-mail vinculado a outra identidade."}
            )
        if object_id and not usuario.entra_object_id:
            usuario.entra_object_id = object_id
            usuario.save(update_fields=["entra_object_id"])
        return usuario

    if not object_id:
        raise DRFValidationError({"id": "ID Entra é obrigatório para convidar usuário novo."})

    usuario = Usuario(
        username=f"entra_{object_id}",
        email=email,
        first_name=nome,
        iniciais=iniciais or gerar_iniciais(nome, email),
        entra_object_id=object_id,
        is_active=True,
    )
    usuario.set_unusable_password()
    try:
        usuario.full_clean()
        usuario.save()
    except ValidationError as exc:
        raise DRFValidationError(exc.message_dict) from exc
    return usuario


def criar_membership(projeto: Project, dados: dict, convidado_por: Usuario | None) -> Membership:
    usuario = obter_ou_criar_usuario_convidado(dados)
    papel = Papel.objects.get(codigo=resolver_codigo_papel(dados.get("role", "")))

    try:
        membership, _ = Membership.objects.get_or_create(
            usuario=usuario,
            projeto=projeto,
            papel=papel,
            defaults={"convidado_por": convidado_por},
        )
    except IntegrityError as exc:
        raise DRFValidationError({"role": "Usuário já possui este papel no projeto."}) from exc

    return membership


@transaction.atomic
def criar_projeto(*, usuario: Usuario, dados: dict) -> Project:
    hierarchy_levels = dados["hierarchyLevels"]
    modo = Project.Modo(dados["mode"].upper())
    project = Project(
        nome=dados["name"].strip(),
        descricao=(dados.get("description") or "").strip(),
        modo=modo,
        nivel1_nome=hierarchy_levels[0],
        nivel2_nome=hierarchy_levels[1] if modo == Project.Modo.UAT else None,
        criado_por=usuario,
    )
    try:
        project.full_clean()
        project.save()
    except ValidationError as exc:
        raise DRFValidationError(exc.message_dict) from exc

    papel_gestor = Papel.objects.get(codigo=Papel.Codigo.GESTOR)
    Membership.objects.get_or_create(
        usuario=usuario,
        projeto=project,
        papel=papel_gestor,
        defaults={"convidado_por": usuario},
    )

    for member in dados.get("team", []):
        criar_membership(project, member, usuario)

    return project


@transaction.atomic
def atualizar_projeto(*, projeto: Project, dados: dict) -> Project:
    if "name" in dados:
        projeto.nome = dados["name"].strip()
    if "description" in dados:
        projeto.descricao = (dados.get("description") or "").strip()
    if "hierarchyLevels" in dados:
        levels = dados["hierarchyLevels"]
        projeto.nivel1_nome = levels[0]
        projeto.nivel2_nome = levels[1] if projeto.modo == Project.Modo.UAT else None

    campos_simples = {
        "agingAlertaDias": "aging_alerta_dias",
        "agingRiscoDias": "aging_risco_dias",
        "spiSaudavel": "spi_saudavel",
        "spiCritico": "spi_critico",
        "anexoMaxMb": "anexo_max_mb",
        "exigirEvidenciaAtividade": "exigir_evidencia_atividade",
        "exigirEvidenciaIssue": "exigir_evidencia_issue",
    }
    for entrada, campo in campos_simples.items():
        if entrada in dados:
            setattr(projeto, campo, dados[entrada])

    try:
        projeto.full_clean()
        projeto.save()
    except ValidationError as exc:
        raise DRFValidationError(exc.message_dict) from exc
    return projeto


def salvar_no_hierarquia(no: NoHierarquia) -> NoHierarquia:
    try:
        no.full_clean()
        no.save()
    except ValidationError as exc:
        raise DRFValidationError(exc.message_dict) from exc
    except IntegrityError as exc:
        raise DRFValidationError({"name": "Já existe nó com este nome no mesmo parent."}) from exc
    return no
