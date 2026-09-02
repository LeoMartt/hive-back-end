import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Project(models.Model):
    class Modo(models.TextChoices):
        UAT = "UAT", "UAT"
        CUTOVER = "CUTOVER", "Cutover"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150)
    descricao = models.TextField(blank=True, default="")
    modo = models.CharField(max_length=10, choices=Modo.choices)
    nivel1_nome = models.CharField(max_length=60)
    nivel2_nome = models.CharField(max_length=60, null=True, blank=True)
    aging_alerta_dias = models.IntegerField(default=2)
    aging_risco_dias = models.IntegerField(default=6)
    spi_saudavel = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.90"))
    spi_critico = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.75"))
    anexo_max_mb = models.IntegerField(default=10)
    exigir_evidencia_atividade = models.BooleanField(default=True)
    exigir_evidencia_issue = models.BooleanField(default=True)
    proximo_codigo_atividade = models.IntegerField(default=1)
    proximo_codigo_issue = models.IntegerField(default=1)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="projetos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-atualizado_em", "nome"]
        constraints = [
            models.CheckConstraint(
                condition=Q(modo="UAT") | Q(modo="CUTOVER"),
                name="project_modo_valido",
            ),
            models.CheckConstraint(
                condition=Q(modo="UAT", nivel2_nome__isnull=False)
                | Q(modo="CUTOVER", nivel2_nome__isnull=True),
                name="project_niveis_por_modo",
            ),
            models.CheckConstraint(
                condition=Q(aging_alerta_dias__gte=0),
                name="project_aging_alerta_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(aging_risco_dias__gte=0),
                name="project_aging_risco_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(anexo_max_mb__gt=0),
                name="project_anexo_max_mb_positivo",
            ),
            models.CheckConstraint(
                condition=Q(proximo_codigo_atividade__gt=0),
                name="project_proximo_codigo_atividade_positivo",
            ),
            models.CheckConstraint(
                condition=Q(proximo_codigo_issue__gt=0),
                name="project_proximo_codigo_issue_positivo",
            ),
        ]

    def clean(self):
        super().clean()
        if self.modo == self.Modo.UAT and not self.nivel2_nome:
            raise ValidationError({"nivel2_nome": "Projetos UAT exigem o segundo nível."})
        if self.modo == self.Modo.CUTOVER and self.nivel2_nome:
            raise ValidationError({"nivel2_nome": "Projetos Cutover não usam segundo nível."})

    @property
    def nomes_niveis_hierarquia(self) -> list[str]:
        return [nome for nome in [self.nivel1_nome, self.nivel2_nome] if nome]

    def __str__(self) -> str:
        return self.nome


class NoHierarquia(models.Model):
    class Nivel(models.IntegerChoices):
        NIVEL_1 = 1, "Nível 1"
        NIVEL_2 = 2, "Nível 2"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projeto = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="nos_hierarquia",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="filhos",
        null=True,
        blank=True,
    )
    nivel = models.PositiveSmallIntegerField(choices=Nivel.choices)
    nome = models.CharField(max_length=100)
    ordem = models.PositiveSmallIntegerField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["projeto", "nivel", "ordem", "nome"]
        verbose_name = "nó de hierarquia"
        verbose_name_plural = "nós de hierarquia"
        constraints = [
            models.CheckConstraint(
                condition=Q(nivel=1, parent__isnull=True) | Q(nivel=2, parent__isnull=False),
                name="no_hierarquia_parent_por_nivel",
            ),
            models.UniqueConstraint(
                fields=["projeto", "parent", "nome"],
                name="no_hierarquia_nome_unico_por_parent",
                nulls_distinct=False,
            ),
        ]

    def clean(self):
        super().clean()
        if self.nivel == self.Nivel.NIVEL_1 and self.parent_id:
            raise ValidationError({"parent": "Nível 1 não deve possuir parent."})

        if self.nivel == self.Nivel.NIVEL_2:
            if not self.parent_id:
                raise ValidationError({"parent": "Nível 2 exige parent de nível 1."})
            if self.projeto and self.projeto.modo == Project.Modo.CUTOVER:
                raise ValidationError({"nivel": "Projetos Cutover não usam nível 2."})
            if self.parent and self.parent.nivel != self.Nivel.NIVEL_1:
                raise ValidationError({"parent": "O parent de nível 2 deve ser um nó de nível 1."})
            if self.parent and self.parent.projeto_id != self.projeto_id:
                raise ValidationError({"parent": "Parent e filho devem pertencer ao mesmo projeto."})

    def __str__(self) -> str:
        return self.nome


class Papel(models.Model):
    class Codigo(models.TextChoices):
        GESTOR = "GESTOR", "Gestor de Projetos"
        TESTER = "TESTER", "Tester"
        DEV = "DEV", "Desenvolvedor"

    id = models.PositiveSmallIntegerField(primary_key=True)
    codigo = models.CharField(max_length=20, choices=Codigo.choices, unique=True)
    nome_exibicao = models.CharField(max_length=40)

    class Meta:
        ordering = ["id"]
        verbose_name_plural = "papéis"

    def __str__(self) -> str:
        return self.nome_exibicao


class Membership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membros_projeto",
    )
    projeto = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    papel = models.ForeignKey(
        Papel,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    convidado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="convites_projeto",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["projeto", "usuario", "papel"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "projeto", "papel"],
                name="membership_usuario_projeto_papel_unico",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.usuario} - {self.projeto} - {self.papel}"
