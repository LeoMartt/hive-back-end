from django.contrib import admin

from .models import Activity, ActivityPredecessor, ActivityStatusEvent
from .services import salvar_activity


class ActivityPredecessorInline(admin.TabularInline):
    model = ActivityPredecessor
    fk_name = "atividade"
    extra = 0


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("codigo_visivel", "nome", "projeto", "status", "tester", "desenvolvedor")
    list_filter = ("status", "projeto")
    search_fields = ("nome", "area", "sistema", "transacao")
    readonly_fields = ("criado_em", "atualizado_em", "codigo_visivel", "evidencia_aprovacao", "historico_status", "numero_retest")
    inlines = [ActivityPredecessorInline]

    def save_model(self, request, obj, form, change):
        salvar_activity(obj, usuario=request.user, origem="admin")


@admin.register(ActivityStatusEvent)
class ActivityStatusEventAdmin(admin.ModelAdmin):
    list_display = ("atividade", "ocorrido_em", "texto", "autor_nome", "origem")
    readonly_fields = tuple(field.name for field in ActivityStatusEvent._meta.fields)
    list_filter = ("origem",)
    search_fields = ("atividade_nome", "autor_nome", "texto")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityPredecessor)
class ActivityPredecessorAdmin(admin.ModelAdmin):
    list_display = ("atividade", "predecessora", "criado_em")
    search_fields = ("atividade__nome", "predecessora__nome")
    readonly_fields = ("criado_em",)
