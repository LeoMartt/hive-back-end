from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Membership, Papel


# Gestores mantem controle do projeto; demais papeis sao configurados por projeto.
DEFAULT_PERMISSIONS = {
    "hierarchy_manage": [], "activities_import": [], "activities_create": [],
    "activities_cancel": [], "activities_edit": [], "activities_assign": [],
    "project_edit": [], "config_thresholds": [], "config_evidence": [],
    "activities_complete": ["TESTER"], "activities_block": ["TESTER"],
    "issues_create": ["TESTER"], "issues_analyze": ["DEV"],
    "issues_cancel": ["DEV"], "issues_resolve": ["TESTER"],
    "data_view": ["TESTER", "DEV"], "dashboard_view": ["TESTER", "DEV"],
    "data_export": ["TESTER", "DEV"],
}


def matriz_efetiva(projeto):
    overrides = projeto.matriz_permissoes or {}
    return {
        action: {role: True if role == "GESTOR" else overrides.get(action, {}).get(role, role in defaults)
                 for role in ("GESTOR", "TESTER", "DEV")}
        for action, defaults in DEFAULT_PERMISSIONS.items()
    }


def validar_matriz(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_PERMISSIONS):
        raise ValidationError("Matriz de permissões inválida.")
    for action, roles in value.items():
        if not isinstance(roles, dict) or set(roles) - {"GESTOR", "TESTER", "DEV"}:
            raise ValidationError("Papéis inválidos na matriz.")
        if any(type(allowed) is not bool for allowed in roles.values()):
            raise ValidationError("Permissões devem ser verdadeiras ou falsas.")
        if roles.get("GESTOR", True) is not True:
            raise ValidationError("Gestor deve manter todas as permissões de gestão do projeto.")
    for role in ("TESTER", "DEV"):
        view = value.get("data_view", {}).get(role, role in DEFAULT_PERMISSIONS["data_view"])
        dashboard = value.get("dashboard_view", {}).get(role, role in DEFAULT_PERMISSIONS["dashboard_view"])
        if dashboard and not view:
            raise ValidationError("Visualizar painéis exige permissão para visualizar atividades e issues.")
    return value


def pode_executar(usuario, projeto, action, *, activity=None, issue=None):
    if not projeto.ativo:
        return False
    if usuario.is_staff or usuario.is_superuser:
        return True
    roles = set(Membership.objects.filter(usuario=usuario, projeto=projeto).values_list("papel__codigo", flat=True))
    if Papel.Codigo.GESTOR in roles:
        return True
    permitted = matriz_efetiva(projeto).get(action, {})
    for role in roles:
        if not permitted.get(role, False):
            continue
        if issue is not None:
            assigned = issue.atividade.tester_id if role == "TESTER" else issue.desenvolvedor_id
            if assigned != usuario.id:
                continue
        elif activity is not None:
            assigned = activity.tester_id if role == "TESTER" else activity.desenvolvedor_id
            if assigned != usuario.id:
                continue
        return True
    return False


def exigir_acao(usuario, projeto, action, **scope):
    if not pode_executar(usuario, projeto, action, **scope):
        raise PermissionDenied("Seu papel não possui permissão para esta ação neste projeto.")
