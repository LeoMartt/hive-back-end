from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import Usuario
from apps.projects.models import Membership, NoHierarquia, Papel, Project

from .models import Activity, ActivityPredecessor


def formatar_codigo_activity(activity_id: int) -> str:
    return f"ATV-{activity_id:04d}"


def resolver_activity_por_codigo(codigo: str, projeto: Project | None = None) -> Activity:
    normalizado = codigo.strip().upper()
    if normalizado.startswith("ATV-"):
        normalizado = normalizado.removeprefix("ATV-")
    try:
        activity_id = int(normalizado)
    except ValueError as exc:
        raise DRFValidationError({"predecessorIds": "Código de predecessora inválido."}) from exc

    queryset = Activity.objects.all()
    if projeto is not None:
        queryset = queryset.filter(projeto=projeto)
    activity = queryset.filter(id=activity_id).first()
    if not activity:
        raise DRFValidationError({"predecessorIds": "Predecessora não encontrada."})
    return activity


def exigir_membership_com_papel(usuario: Usuario, projeto: Project, codigo_papel: str, campo: str) -> None:
    if not Membership.objects.filter(
        usuario=usuario,
        projeto=projeto,
        papel__codigo=codigo_papel,
    ).exists():
        raise DRFValidationError({campo: f"Usuário deve possuir papel {codigo_papel} no projeto."})


def resolver_usuario_por_identificador(identificador, campo: str) -> Usuario:
    usuario = Usuario.objects.filter(
        Q(id=identificador) | Q(entra_object_id=identificador),
    ).first()
    if not usuario:
        raise DRFValidationError({campo: "Usuário não encontrado."})
    return usuario


def validar_no_para_activity(projeto: Project, no: NoHierarquia) -> None:
    if no.projeto_id != projeto.id:
        raise DRFValidationError({"nodeId": "Nó de hierarquia deve pertencer ao projeto."})
    if projeto.modo == Project.Modo.UAT and no.nivel != NoHierarquia.Nivel.NIVEL_2:
        raise DRFValidationError({"nodeId": "Atividades UAT devem apontar para nó de nível 2."})
    if projeto.modo == Project.Modo.CUTOVER and no.nivel != NoHierarquia.Nivel.NIVEL_1:
        raise DRFValidationError({"nodeId": "Atividades Cutover devem apontar para nó de nível 1."})


def validar_predecessoras(projeto: Project, predecessor_ids: list[int]) -> list[Activity]:
    if not predecessor_ids:
        return []

    predecessoras = list(Activity.objects.filter(projeto=projeto, id__in=predecessor_ids))
    encontrados = {activity.id for activity in predecessoras}
    ausentes = [activity_id for activity_id in predecessor_ids if activity_id not in encontrados]
    if ausentes:
        raise DRFValidationError({"predecessorIds": "Todas as predecessoras devem existir no mesmo projeto."})
    if any(activity.status == Activity.Status.CANCELADO for activity in predecessoras):
        raise DRFValidationError({"predecessorIds": "Atividade cancelada não pode ser predecessora."})
    return predecessoras


def status_inicial(predecessoras: list[Activity]) -> str:
    return Activity.Status.AGUARDANDO if predecessoras else Activity.Status.LIBERADO


def status_liberado_por_predecessoras(predecessoras: list[Activity]) -> str:
    if not predecessoras:
        return Activity.Status.LIBERADO
    if all(activity.status == Activity.Status.CONCLUIDO for activity in predecessoras):
        return Activity.Status.LIBERADO
    return Activity.Status.AGUARDANDO


def liberar_dependentes(activity: Activity) -> None:
    for dependente in activity.dependentes.filter(status=Activity.Status.AGUARDANDO).prefetch_related(
        "predecessoras",
    ):
        if all(predecessora.status == Activity.Status.CONCLUIDO for predecessora in dependente.predecessoras.all()):
            dependente.status = Activity.Status.LIBERADO
            salvar_activity(dependente)


def salvar_activity(activity: Activity) -> Activity:
    try:
        activity.full_clean()
        activity.save()
    except ValidationError as exc:
        raise DRFValidationError(exc.message_dict) from exc
    except IntegrityError as exc:
        raise DRFValidationError({"activity": "Não foi possível salvar a atividade."}) from exc
    return activity


@transaction.atomic
def criar_activity(*, projeto: Project, dados: dict) -> Activity:
    no = NoHierarquia.objects.filter(id=dados["nodeId"], projeto=projeto).first()
    if not no:
        raise DRFValidationError({"nodeId": "Nó de hierarquia não encontrado."})
    validar_no_para_activity(projeto, no)

    tester = resolver_usuario_por_identificador(dados["testerId"], "testerId")
    exigir_membership_com_papel(tester, projeto, Papel.Codigo.TESTER, "testerId")

    desenvolvedor = resolver_usuario_por_identificador(dados["developerId"], "developerId")
    exigir_membership_com_papel(desenvolvedor, projeto, Papel.Codigo.DEV, "developerId")

    predecessoras = validar_predecessoras(projeto, dados.get("predecessorIds", []))

    activity = Activity(
        projeto=projeto,
        no=no,
        nome=dados["name"].strip(),
        status=status_inicial(predecessoras),
        tester=tester,
        desenvolvedor=desenvolvedor,
        data_inicio_planejada=dados["plannedStart"],
        data_conclusao_planejada=dados["plannedEnd"],
        area=(dados.get("area") or "").strip(),
        sistema=(dados.get("system") or "").strip(),
        transacao=(dados.get("transaction") or "").strip(),
        wbs=(dados.get("wbs") or "").strip(),
        resultado_esperado=(dados.get("expectedResult") or "").strip(),
        observacoes=(dados.get("notes") or "").strip(),
    )
    salvar_activity(activity)

    for predecessora in predecessoras:
        ActivityPredecessor.objects.create(atividade=activity, predecessora=predecessora)

    return activity


@transaction.atomic
def atualizar_activity(*, activity: Activity, dados: dict) -> Activity:
    if activity.status == Activity.Status.CANCELADO:
        raise DRFValidationError({"status": "Atividade cancelada não pode ser alterada."})
    if activity.status == Activity.Status.CONCLUIDO:
        raise DRFValidationError({"status": "Atividade concluída não pode ser alterada."})

    if "nodeId" in dados:
        raise DRFValidationError({"nodeId": "Nó de hierarquia da atividade não pode ser alterado."})

    if "testerId" in dados:
        tester = resolver_usuario_por_identificador(dados["testerId"], "testerId")
        exigir_membership_com_papel(tester, activity.projeto, Papel.Codigo.TESTER, "testerId")
        activity.tester = tester

    if "developerId" in dados:
        desenvolvedor = resolver_usuario_por_identificador(dados["developerId"], "developerId")
        exigir_membership_com_papel(desenvolvedor, activity.projeto, Papel.Codigo.DEV, "developerId")
        activity.desenvolvedor = desenvolvedor

    campos_simples = {
        "name": "nome",
        "plannedStart": "data_inicio_planejada",
        "plannedEnd": "data_conclusao_planejada",
        "area": "area",
        "system": "sistema",
        "transaction": "transacao",
        "wbs": "wbs",
        "expectedResult": "resultado_esperado",
        "notes": "observacoes",
    }
    for entrada, campo in campos_simples.items():
        if entrada in dados:
            valor = dados[entrada]
            if isinstance(valor, str):
                valor = valor.strip()
            setattr(activity, campo, valor or "")

    if "predecessorIds" in dados:
        predecessor_ids = dados.get("predecessorIds") or []
        if activity.id in predecessor_ids:
            raise DRFValidationError({"predecessorIds": "Atividade não pode depender dela mesma."})
        predecessoras = validar_predecessoras(activity.projeto, predecessor_ids)
        if activity.status in [Activity.Status.AGUARDANDO, Activity.Status.LIBERADO]:
            activity.status = status_liberado_por_predecessoras(predecessoras)
        activity.predecessor_edges.all().delete()
        for predecessora in predecessoras:
            ActivityPredecessor.objects.create(atividade=activity, predecessora=predecessora)

    return salvar_activity(activity)


@transaction.atomic
def cancelar_activity(*, activity: Activity) -> Activity:
    if activity.status == Activity.Status.CANCELADO:
        return activity
    if activity.status == Activity.Status.CONCLUIDO:
        raise DRFValidationError({"status": "Atividade concluída não pode ser cancelada."})
    activity.status = Activity.Status.CANCELADO
    activity = salvar_activity(activity)

    from apps.issues.services import cancelar_issues_da_activity

    cancelar_issues_da_activity(activity)
    return activity


@transaction.atomic
def concluir_activity(*, activity: Activity, observacao_aprovacao: str = "") -> Activity:
    if activity.status != Activity.Status.LIBERADO:
        raise DRFValidationError({"status": "Somente atividade liberada pode ser concluída."})
    activity.status = Activity.Status.CONCLUIDO
    if not activity.data_inicio_real:
        activity.data_inicio_real = timezone.localdate()
    activity.data_conclusao_real = timezone.localdate()
    activity.observacao_aprovacao = observacao_aprovacao.strip()
    activity = salvar_activity(activity)
    liberar_dependentes(activity)
    return activity


@transaction.atomic
def bloquear_activity(*, activity: Activity, motivo: str = "") -> Activity:
    if activity.status != Activity.Status.LIBERADO:
        raise DRFValidationError({"status": "Somente atividade liberada pode ser bloqueada."})
    activity.status = Activity.Status.BLOQUEADO
    activity.numero_retest += 1
    if motivo:
        activity.observacoes = motivo.strip()
    return salvar_activity(activity)
