from django.db.models import Count, Prefetch, Q

from .models import Activity


def activities_com_relacoes(project):
    return Activity.objects.filter(projeto=project).select_related(
        "projeto", "no", "no__parent", "tester", "desenvolvedor",
    ).prefetch_related(Prefetch("predecessoras", queryset=Activity.objects.only("id"))).annotate(
        open_issue_count=Count("issues", filter=~Q(issues__status__in=["CONCLUIDA", "CANCELADA"])),
    )
