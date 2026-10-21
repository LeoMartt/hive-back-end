from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.activities.models import Activity
from apps.issues.models import Issue


class Command(BaseCommand):
    help = "Revisa issues com Solucao proposta em atividades ja concluidas; sem --apply apenas conta."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--project", type=str)

    def handle(self, *args, **options):
        with transaction.atomic():
            queryset = Issue.objects.filter(atividade__status=Activity.Status.CONCLUIDO, status=Issue.Status.SOLUCAO_PROPOSTA)
            if options["project"]:
                queryset = queryset.filter(projeto_id=options["project"])
            count = queryset.count()
            self.stdout.write(f"Issues pendentes em atividades concluidas: {count}")
            if options["apply"]:
                now = timezone.now()
                changed = queryset.update(status=Issue.Status.CONCLUIDA, resolvida_em=now, atualizada_em=now)
                self.stdout.write(self.style.SUCCESS(f"Issues reconciliadas: {changed}. Encerramento registrado no momento da reconciliacao."))
            else:
                self.stdout.write("Simulacao: nenhum registro alterado. Use --apply para reconciliar.")
