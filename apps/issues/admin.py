from django.contrib import admin

from .models import Issue


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ["codigo_visivel", "titulo", "projeto", "atividade", "status", "impeditiva"]
    list_filter = ["status", "impeditiva", "tipo", "impacto", "projeto"]
    search_fields = ["titulo", "descricao", "atividade__nome"]
    autocomplete_fields = ["projeto", "atividade", "tester", "desenvolvedor"]
