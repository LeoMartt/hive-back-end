from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("HIVE", {"fields": ("iniciais", "entra_object_id")}),
    )
    list_display = (
        "username",
        "email",
        "first_name",
        "iniciais",
        "entra_object_id",
        "is_staff",
    )
    search_fields = ("username", "email", "first_name")
