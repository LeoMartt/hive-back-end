from django.conf import settings
from django.db import models

from apps.activities.models import Activity
from apps.projects.models import Project


class Issue(models.Model):
    class Status(models.TextChoices):
        ABERTA = "ABERTA", "Aberta"
        EM_ANALISE = "EM_ANALISE", "Em análise"
        SOLUCAO_PROPOSTA = "SOLUCAO_PROPOSTA", "Solução proposta"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        CANCELADA = "CANCELADA", "Cancelada"

    class Tipo(models.TextChoices):
        REQUISITO = "REQUISITO", "Requisito"
        PERFORMANCE = "PERFORMANCE", "Performance"
        DADOS = "DADOS", "Dados"
        INTEGRACAO = "INTEGRACAO", "Integração"
        INTERFACE = "INTERFACE", "Interface"
        CONFIGURACAO = "CONFIGURACAO", "Configuração"
        OUTRO = "OUTRO", "Outro"

    class Impacto(models.TextChoices):
        MUITO_ALTO = "MUITO_ALTO", "Muito alto"
        ALTO = "ALTO", "Alto"
        MEDIO = "MEDIO", "Médio"
        BAIXO = "BAIXO", "Baixo"

    projeto = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="issues",
    )
    atividade = models.ForeignKey(
        Activity,
        on_delete=models.PROTECT,
        related_name="issues",
    )
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ABERTA)
    impeditiva = models.BooleanField(default=False)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    impacto = models.CharField(max_length=20, choices=Impacto.choices)
    nota_impacto = models.CharField(max_length=255, blank=True, default="")
    tester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issues_como_tester",
    )
    desenvolvedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issues_como_desenvolvedor",
    )
    solucao_proposta = models.TextField(blank=True, default="")
    anexo_abertura = models.JSONField(null=True, blank=True)
    anexo_solucao = models.JSONField(null=True, blank=True)
    analise_iniciada_em = models.DateTimeField(null=True, blank=True)
    solucao_proposta_em = models.DateTimeField(null=True, blank=True)
    resolvida_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em", "-id"]
        verbose_name = "issue"
        verbose_name_plural = "issues"

    @property
    def codigo_visivel(self) -> str:
        if self.id is None:
            return "ISS-0000"
        return f"ISS-{self.id:04d}"

    def __str__(self) -> str:
        return f"{self.codigo_visivel} - {self.titulo}"
