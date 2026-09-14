import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Usuario
from apps.activities.models import Activity
from apps.activities.services import salvar_activity, status_liberado_por_predecessoras
from apps.projects.models import Membership, Papel, Project
from apps.projects.services import usuario_pode_gerenciar_projeto

from .models import Issue


STATUS_ABERTOS = [
    Issue.Status.ABERTA,
    Issue.Status.EM_ANALISE,
    Issue.Status.SOLUCAO_PROPOSTA,
]


def usuario_pode_testar_activity(user: Usuario, activity: Activity) -> bool:
    return activity.tester_id == user.id


def usuario_pode_desenvolver_issue(user: Usuario, issue: Issue) -> bool:
    return issue.desenvolvedor_id == user.id


def exigir_tester_da_activity_ou_gestor(user: Usuario, activity: Activity) -> None:
    if usuario_pode_gerenciar_projeto(user, activity.projeto):
        return
    if usuario_pode_testar_activity(user, activity):
        return
    raise PermissionDenied("Apenas gestores ou o tester da atividade podem executar esta ação.")


def exigir_tester_da_activity(user: Usuario, activity: Activity) -> None:
    if usuario_pode_testar_activity(user, activity):
        return
    raise PermissionDenied("Apenas o tester da atividade pode criar issue.")


def exigir_dev_da_issue(user: Usuario, issue: Issue) -> None:
    if usuario_pode_desenvolver_issue(user, issue):
        return
    raise PermissionDenied("Apenas o desenvolvedor responsável pode executar esta ação.")


def resolver_desenvolvedor(projeto: Project, dados: dict) -> Usuario:
    developer_id = dados.get("developerId")
    dev = (dados.get("dev") or "").strip()

    query = Q()
    if developer_id:
        query |= Q(id=developer_id) | Q(entra_object_id=developer_id)
    if dev:
        query |= Q(first_name=dev) | Q(username=dev) | Q(email__iexact=dev)
        try:
            dev_uuid = uuid.UUID(dev)
        except ValueError:
            dev_uuid = None
        if dev_uuid:
            query |= Q(id=dev_uuid) | Q(entra_object_id=dev_uuid)

    usuario = Usuario.objects.filter(query).first()
    if not usuario:
        raise ValidationError({"dev": "Desenvolvedor responsável não encontrado."})

    if not Membership.objects.filter(
        usuario=usuario,
        projeto=projeto,
        papel__codigo=Papel.Codigo.DEV,
    ).exists():
        raise ValidationError({"dev": "Usuário deve possuir papel DEV no projeto."})
    return usuario


def bloquear_activity_por_issue_impeditiva(activity: Activity) -> None:
    if activity.status == Activity.Status.BLOQUEADO:
        return
    if activity.status in [Activity.Status.CONCLUIDO, Activity.Status.CANCELADO]:
        raise ValidationError({"relatedActivityId": "Atividade concluída ou cancelada não pode ser bloqueada por issue."})
    activity.status = Activity.Status.BLOQUEADO
    activity.numero_retest += 1
    salvar_activity(activity)


@transaction.atomic
def criar_issue(*, projeto: Project, usuario: Usuario, dados: dict) -> Issue:
    activity = dados["activity"]
    if activity.projeto_id != projeto.id:
        raise ValidationError({"relatedActivityId": "Atividade deve pertencer ao projeto."})
    if activity.status in [Activity.Status.CANCELADO, Activity.Status.CONCLUIDO]:
        raise ValidationError({"relatedActivityId": "Atividade concluída ou cancelada não pode receber issue."})

    exigir_tester_da_activity(usuario, activity)
    desenvolvedor = resolver_desenvolvedor(projeto, dados)

    issue = Issue.objects.create(
        projeto=projeto,
        atividade=activity,
        titulo=dados["title"].strip(),
        descricao=dados["description"].strip(),
        tipo=dados["type"],
        impeditiva=dados["impeditiva"],
        impacto=dados["impact"],
        nota_impacto=(dados.get("impactNote") or "").strip(),
        tester=usuario,
        desenvolvedor=desenvolvedor,
        anexo_abertura=dados.get("openingAttachment"),
    )
    if issue.impeditiva:
        bloquear_activity_por_issue_impeditiva(activity)
    return issue


@transaction.atomic
def iniciar_analise_issue(*, issue: Issue, usuario: Usuario) -> Issue:
    exigir_dev_da_issue(usuario, issue)
    if issue.status != Issue.Status.ABERTA:
        raise ValidationError({"status": "Somente issue aberta pode iniciar análise."})
    issue.status = Issue.Status.EM_ANALISE
    issue.analise_iniciada_em = timezone.now()
    issue.save(update_fields=["status", "analise_iniciada_em", "atualizada_em"])
    return issue


@transaction.atomic
def propor_solucao_issue(*, issue: Issue, usuario: Usuario, dados: dict) -> Issue:
    exigir_dev_da_issue(usuario, issue)
    if issue.status != Issue.Status.EM_ANALISE:
        raise ValidationError({"status": "Somente issue em análise pode receber solução proposta."})
    issue.status = Issue.Status.SOLUCAO_PROPOSTA
    issue.solucao_proposta = dados["proposedSolution"].strip()
    issue.anexo_solucao = dados.get("solutionAttachment")
    issue.solucao_proposta_em = timezone.now()
    issue.save(
        update_fields=[
            "status",
            "solucao_proposta",
            "anexo_solucao",
            "solucao_proposta_em",
            "atualizada_em",
        ]
    )
    return issue


def atividade_tem_issues_abertas(activity: Activity) -> bool:
    return activity.issues.filter(status__in=STATUS_ABERTOS).exists()


@transaction.atomic
def concluir_issue(*, issue: Issue, usuario: Usuario) -> Issue:
    exigir_tester_da_activity_ou_gestor(usuario, issue.atividade)
    if issue.status != Issue.Status.SOLUCAO_PROPOSTA:
        raise ValidationError({"status": "Somente issue com solução proposta pode ser concluída."})

    issue.status = Issue.Status.CONCLUIDA
    issue.resolvida_em = timezone.now()
    issue.save(update_fields=["status", "resolvida_em", "atualizada_em"])

    activity = issue.atividade
    if activity.status == Activity.Status.BLOQUEADO and not atividade_tem_issues_abertas(activity):
        activity.status = status_liberado_por_predecessoras(list(activity.predecessoras.all()))
        salvar_activity(activity)

    return issue


@transaction.atomic
def cancelar_issue(*, issue: Issue) -> Issue:
    if issue.status in [Issue.Status.CONCLUIDA, Issue.Status.CANCELADA]:
        return issue
    issue.status = Issue.Status.CANCELADA
    issue.resolvida_em = timezone.now()
    issue.save(update_fields=["status", "resolvida_em", "atualizada_em"])
    return issue


@transaction.atomic
def cancelar_issues_da_activity(activity: Activity) -> None:
    now = timezone.now()
    activity.issues.filter(status__in=STATUS_ABERTOS).update(
        status=Issue.Status.CANCELADA,
        resolvida_em=now,
        atualizada_em=now,
    )
