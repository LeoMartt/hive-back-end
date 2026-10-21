from django.contrib import admin

from .models import EvidenceRuleChange, Membership, NoHierarquia, Papel, Project
from .services import EVIDENCE_RULE_FIELDS, registrar_alteracao_evidencia


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("nome", "modo", "ativo", "criado_por", "criado_em", "atualizado_em")
    list_filter = ("modo", "ativo")
    search_fields = ("nome", "descricao")
    readonly_fields = ("criado_em", "atualizado_em")

    def save_model(self, request, obj, form, change):
        anteriores = None
        if change:
            anterior = Project.objects.select_for_update().get(pk=obj.pk)
            anteriores = {field: getattr(anterior, field) for field in EVIDENCE_RULE_FIELDS}
        super().save_model(request, obj, form, change)
        if anteriores is not None:
            registrar_alteracao_evidencia(projeto=obj, anteriores=anteriores, usuario=request.user)


@admin.register(EvidenceRuleChange)
class EvidenceRuleChangeAdmin(admin.ModelAdmin):
    list_display = ("projeto", "autor", "criado_em")
    list_filter = ("projeto",)
    readonly_fields = ("projeto", "usuario", "autor", "valores_anteriores", "valores_novos", "criado_em")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(NoHierarquia)
class NoHierarquiaAdmin(admin.ModelAdmin):
    list_display = ("nome", "projeto", "nivel", "parent", "ordem")
    list_filter = ("nivel", "projeto")
    search_fields = ("nome", "projeto__nome")


@admin.register(Papel)
class PapelAdmin(admin.ModelAdmin):
    list_display = ("id", "codigo", "nome_exibicao")
    search_fields = ("codigo", "nome_exibicao")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("usuario", "projeto", "papel", "convidado_por", "criado_em")
    list_filter = ("papel", "projeto")
    search_fields = ("usuario__email", "usuario__first_name", "projeto__nome", "papel__codigo")
    readonly_fields = ("criado_em",)
