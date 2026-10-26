from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.activities.models import Activity
from apps.activities.services import salvar_activity


class Command(BaseCommand):
    help = "Recupera inicio real ausente por datas comprovadas de issue, bloqueio ou conclusao. Simula por padrao."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        candidates = Activity.objects.filter(data_inicio_real__isnull=True).filter(
            Q(issues__isnull=False) | Q(eventos_status__status_novo="BLOQUEADO") |
            Q(eventos_status__texto__endswith="→ Bloqueado") |
            Q(status="CONCLUIDO", data_conclusao_real__isnull=False),
        ).values_list("pk", flat=True).distinct()
        recovered = 0
        skipped = 0
        for pk in list(candidates):
            with transaction.atomic():
                activity = Activity.objects.select_for_update().get(pk=pk)
                if activity.data_inicio_real is not None:
                    continue
                proof = []
                issue = activity.issues.order_by("criada_em", "pk").first()
                if issue:
                    proof.append((timezone.localdate(issue.criada_em), f"primeira issue {issue.codigo_visivel}"))
                event = activity.eventos_status.filter(Q(status_novo="BLOQUEADO") | Q(texto__endswith="→ Bloqueado")).order_by("ocorrido_em", "pk").first()
                if event:
                    proof.append((timezone.localdate(event.ocorrido_em), "primeiro bloqueio registrado"))
                if activity.status == "CONCLUIDO" and activity.data_conclusao_real:
                    proof.append((activity.data_conclusao_real, "conclusão real"))
                if not proof:
                    skipped += 1
                    continue
                day, source = min(proof, key=lambda item: item[0])
                if activity.data_conclusao_real and day > activity.data_conclusao_real:
                    skipped += 1
                    continue
                recovered += 1
                if options["apply"]:
                    activity.data_inicio_real = day
                    salvar_activity(activity, origem="reconciliacao_inicio", motivo=f"Data recuperada de {source}; histórico anterior preservado")
        self.stdout.write(f"Inicios reais {'recuperados' if options['apply'] else 'recuperaveis'}: {recovered}. Sem prova consistente: {skipped}.")
        if not options["apply"]:
            self.stdout.write("Simulacao: nenhum registro alterado. Use --apply para corrigir.")
