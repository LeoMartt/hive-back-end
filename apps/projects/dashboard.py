from collections import Counter
from datetime import timedelta
from math import floor

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.utils import timezone

from apps.activities.models import Activity
from apps.issues.models import Issue
from .spi import calcular_spi


def percentage(part, total):
    return floor(part / total * 100 + 0.5) if total else None


def dashboard_do_projeto(project, today=None):
    today = today or timezone.localdate()
    activities = Activity.objects.filter(projeto=project)
    issues = Issue.objects.filter(projeto=project)
    counts = dict(activities.values_list("status").annotate(total=Count("id")))
    issue_counts = dict(issues.values_list("status").annotate(total=Count("id")))
    total = sum(counts.values())
    active_total = total - counts.get("CANCELADO", 0)
    completed = counts.get("CONCLUIDO", 0)
    activity_stats = {
        "total": total, "concluido": completed, "liberado": counts.get("LIBERADO", 0),
        "bloqueado": counts.get("BLOQUEADO", 0), "aguardando": counts.get("AGUARDANDO", 0),
        "cancelado": counts.get("CANCELADO", 0),
        "atrasado": activities.exclude(status__in=["CONCLUIDO", "CANCELADO"]).filter(data_conclusao_planejada__lt=today).count(),
    }
    duration = issues.filter(status="CONCLUIDA", resolvida_em__gte=F("criada_em")).aggregate(
        duration=Avg(ExpressionWrapper(F("resolvida_em") - F("criada_em"), output_field=DurationField())),
    )["duration"]
    issue_stats = {
        "total": sum(issue_counts.values()), "abertas": issue_counts.get("ABERTA", 0),
        "emAnalise": issue_counts.get("EM_ANALISE", 0), "solucaoProposta": issue_counts.get("SOLUCAO_PROPOSTA", 0),
        "concluidas": issue_counts.get("CONCLUIDA", 0), "canceladas": issue_counts.get("CANCELADA", 0),
        "impeditivasAbertas": issues.filter(impeditiva=True, status__in=["ABERTA", "EM_ANALISE"]).count(),
        "tempoMedioResolucaoDias": duration.total_seconds() / 86400 if duration is not None else None,
    }
    indicators = activities.filter(status="CONCLUIDO").aggregate(
        on_time=Count("id", filter=Q(data_conclusao_real__lte=F("data_conclusao_planejada"))),
        no_retest=Count("id", filter=Q(numero_retest=0)),
    )
    distribution = {
        "pace": percentage(indicators["on_time"], completed),
        "quality": percentage(indicators["no_retest"], completed),
        "backlog": percentage(counts.get("AGUARDANDO", 0) + counts.get("LIBERADO", 0), active_total),
    }
    # Two half-point deltas per activity reproduce the SPI's 0/50/100 weights.
    dates = list(activities.exclude(status="CANCELADO").values_list(
        "data_inicio_planejada", "data_conclusao_planejada", "data_inicio_real", "data_conclusao_real", "status",
    ))
    curve = {"labels": ["Hoje"], "planned": [0], "plannedCounts": [0], "realized": [0], "realizedCounts": [0], "total": 0}
    if dates:
        start = min(row[0] for row in dates)
        last_planned = max(row[1] for row in dates)
        realized_end = today
        end = max(last_planned, realized_end, start)
        planned_by_day = Counter()
        actual_by_day = Counter()
        for planned_start, planned_end, actual_start, actual_end, status in dates:
            planned_by_day[min(planned_start, planned_end)] += 0.5
            planned_by_day[planned_end] += 0.5
            if status == "CONCLUIDO":
                # Missing/invalid completion dates cannot establish a past event:
                # reflect the known completed status at the reference date only.
                completed_at = min(actual_end or today, today)
                actual_by_day[min(actual_start, completed_at) if actual_start else completed_at] += 0.5
                actual_by_day[completed_at] += 0.5
            elif actual_start is not None:
                actual_by_day[actual_start] += 0.5
        planned_count = sum(count for day, count in planned_by_day.items() if day < start)
        actual_count = sum(count for day, count in actual_by_day.items() if day < start)
        curve = {"labels": [], "planned": [], "plannedCounts": [], "realized": [], "realizedCounts": [], "total": len(dates)}
        day = start
        while day <= end:
            planned_count += planned_by_day[day]
            actual_count += actual_by_day[day]
            curve["labels"].append(day.strftime("%d/%m"))
            curve["plannedCounts"].append(planned_count)
            curve["planned"].append(percentage(planned_count, len(dates)))
            curve["realizedCounts"].append(actual_count if day <= realized_end else None)
            curve["realized"].append(percentage(actual_count, len(dates)) if day <= realized_end else None)
            day += timedelta(days=1)
    recent = []
    activity_labels = {"AGUARDANDO": "Aguardando", "LIBERADO": "Liberado", "CONCLUIDO": "Concluído", "BLOQUEADO": "Bloqueado", "CANCELADO": "Cancelado"}
    issue_labels = {"ABERTA": "Aberta", "EM_ANALISE": "Em análise", "SOLUCAO_PROPOSTA": "Solução proposta", "CONCLUIDA": "Concluída", "CANCELADA": "Cancelada"}
    for item in activities.select_related("tester").only("id", "nome", "status", "atualizado_em", "tester__first_name", "tester__username").order_by("-atualizado_em", "id")[:7]:
        recent.append({"id": f"activity-{item.codigo_visivel}", "icon": "done" if item.status == "CONCLUIDO" else "block" if item.status in ["BLOQUEADO", "CANCELADO"] else "status",
            "refId": item.codigo_visivel, "refName": item.nome,
            "text": "marcada como Concluído" if item.status == "CONCLUIDO" else f"status atual {activity_labels[item.status]}",
            "authorInitials": "", "authorName": item.tester.first_name or item.tester.username, "at": item.atualizado_em.isoformat()})
    for item in issues.select_related("tester").only("id", "titulo", "status", "impeditiva", "atualizada_em", "tester__first_name", "tester__username").order_by("-atualizada_em", "id")[:7]:
        label = issue_labels[item.status]
        text = "marcada como Concluída" if item.status == "CONCLUIDA" else f"impeditiva com status {label}" if item.impeditiva and item.status != "CANCELADA" else f"status atual {label}"
        recent.append({"id": f"issue-{item.codigo_visivel}", "icon": "block" if item.impeditiva else "issue",
            "refId": item.codigo_visivel, "refName": item.titulo, "text": text, "authorInitials": "",
            "authorName": item.tester.first_name or item.tester.username, "at": item.atualizada_em.isoformat()})
    recent.sort(key=lambda item: item["at"], reverse=True)
    return {"activities": activity_stats, "issues": issue_stats,
        "spi": calcular_spi(activities, today),
        "indicators": distribution, "curve": curve, "recent": recent[:7]}
