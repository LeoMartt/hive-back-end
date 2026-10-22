from django.db.models import Case, FloatField, Sum, Value, When
from django.utils import timezone


def spi_weights(today=None):
    today = today or timezone.localdate()
    ev = Case(
        When(status="CONCLUIDO", then=Value(1.0)),
        When(data_inicio_real__lte=today, then=Value(0.5)),
        default=Value(0.0), output_field=FloatField(),
    )
    pv = Case(
        When(data_conclusao_planejada__lte=today, then=Value(1.0)),
        When(data_inicio_planejada__lte=today, then=Value(0.5)),
        default=Value(0.0), output_field=FloatField(),
    )
    return ev, pv


def calcular_spi(queryset, today=None):
    ev, pv = spi_weights(today)
    totals = queryset.exclude(status="CANCELADO").aggregate(ev=Sum(ev), pv=Sum(pv))
    return totals["ev"] / totals["pv"] if totals["pv"] else None
