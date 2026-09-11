from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.projects.models import NoHierarquia, Project


class Activity(models.Model):
    class Status(models.TextChoices):
        AGUARDANDO = "AGUARDANDO", "Aguardando"
        LIBERADO = "LIBERADO", "Liberado"
        BLOQUEADO = "BLOQUEADO", "Bloqueado"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        CANCELADO = "CANCELADO", "Cancelado"

    projeto = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="activities",
    )
    no = models.ForeignKey(
        NoHierarquia,
        on_delete=models.PROTECT,
        related_name="activities",
    )
    nome = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LIBERADO,
    )
    tester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="activities_como_tester",
    )
    desenvolvedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="activities_como_desenvolvedor",
    )
    data_inicio_planejada = models.DateField()
    data_conclusao_planejada = models.DateField()
    data_inicio_real = models.DateField(null=True, blank=True)
    data_conclusao_real = models.DateField(null=True, blank=True)
    numero_retest = models.IntegerField(default=0)
    area = models.CharField(max_length=100, blank=True, default="")
    sistema = models.CharField(max_length=100, blank=True, default="")
    transacao = models.CharField(max_length=50, blank=True, default="")
    wbs = models.CharField(max_length=50, blank=True, default="")
    resultado_esperado = models.TextField(blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    observacao_aprovacao = models.TextField(blank=True, default="")
    predecessoras = models.ManyToManyField(
        "self",
        through="ActivityPredecessor",
        through_fields=("atividade", "predecessora"),
        symmetrical=False,
        related_name="dependentes",
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "atividade"
        verbose_name_plural = "atividades"
        constraints = [
            models.CheckConstraint(
                condition=Q(data_inicio_planejada__lte=F("data_conclusao_planejada")),
                name="activity_datas_planejadas_ordem",
            ),
            models.CheckConstraint(
                condition=Q(numero_retest__gte=0),
                name="activity_numero_retest_nao_negativo",
            ),
        ]

    @property
    def codigo_visivel(self) -> str:
        if self.id is None:
            return "ATV-0000"
        return f"ATV-{self.id:04d}"

    def clean(self):
        super().clean()
        if self.data_inicio_planejada and self.data_conclusao_planejada:
            if self.data_inicio_planejada > self.data_conclusao_planejada:
                raise ValidationError(
                    {"data_conclusao_planejada": "Conclusão planejada deve ser maior ou igual ao início."}
                )

        if self.no_id and self.projeto_id and self.no.projeto_id != self.projeto_id:
            raise ValidationError({"no": "Nó de hierarquia deve pertencer ao mesmo projeto."})

        if self.no_id and self.projeto_id:
            if self.projeto.modo == Project.Modo.UAT and self.no.nivel != NoHierarquia.Nivel.NIVEL_2:
                raise ValidationError({"no": "Atividades UAT devem apontar para nó de nível 2."})
            if self.projeto.modo == Project.Modo.CUTOVER and self.no.nivel != NoHierarquia.Nivel.NIVEL_1:
                raise ValidationError({"no": "Atividades Cutover devem apontar para nó de nível 1."})

    def __str__(self) -> str:
        return f"{self.codigo_visivel} - {self.nome}"


class ActivityPredecessor(models.Model):
    atividade = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="predecessor_edges",
    )
    predecessora = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="dependent_edges",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "predecessora de atividade"
        verbose_name_plural = "predecessoras de atividades"
        constraints = [
            models.UniqueConstraint(
                fields=["atividade", "predecessora"],
                name="activity_predecessor_unica",
            ),
            models.CheckConstraint(
                condition=~Q(atividade=F("predecessora")),
                name="activity_predecessor_nao_self",
            ),
        ]

    def clean(self):
        super().clean()
        if self.atividade_id and self.predecessora_id:
            if self.atividade_id == self.predecessora_id:
                raise ValidationError({"predecessora": "Atividade não pode depender dela mesma."})
            if self.atividade.projeto_id != self.predecessora.projeto_id:
                raise ValidationError({"predecessora": "Predecessora deve pertencer ao mesmo projeto."})

    def __str__(self) -> str:
        return f"{self.atividade} depende de {self.predecessora}"
