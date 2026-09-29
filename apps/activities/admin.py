from django.contrib import admin

from .models import Activity, ActivityPredecessor


class ActivityPredecessorInline(admin.TabularInline):
    model = ActivityPredecessor
    fk_name = "atividade"
    extra = 0


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("codigo_visivel", "nome", "projeto", "status", "tester", "desenvolvedor")
    list_filter = ("status", "projeto")
    search_fields = ("nome", "area", "sistema", "transacao")
    readonly_fields = ("criado_em", "atualizado_em", "codigo_visivel", "evidencia_aprovacao")
    inlines = [ActivityPredecessorInline]


@admin.register(ActivityPredecessor)
class ActivityPredecessorAdmin(admin.ModelAdmin):
    list_display = ("atividade", "predecessora", "criado_em")
    search_fields = ("atividade__nome", "predecessora__nome")
    readonly_fields = ("criado_em",)
