from rest_framework import serializers

from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="first_name", read_only=True)

    class Meta:
        model = Usuario
        fields = ["id", "nome", "email", "entra_object_id"]
        read_only_fields = fields
