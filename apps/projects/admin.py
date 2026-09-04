from django.contrib import admin

from .models import Membership, NoHierarquia, Papel, Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("nome", "modo", "ativo", "criado_por", "criado_em", "atualizado_em")
    list_filter = ("modo", "ativo")
    search_fields = ("nome", "descricao")
    readonly_fields = ("criado_em", "atualizado_em")


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
