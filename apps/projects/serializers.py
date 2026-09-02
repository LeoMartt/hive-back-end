from rest_framework import serializers

from .models import Membership, Project


class TeamMemberSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="usuario.id", read_only=True)
    initials = serializers.CharField(source="usuario.iniciais", read_only=True)
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="usuario.email", read_only=True)
    role = serializers.CharField(source="papel.nome_exibicao", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "initials", "name", "email", "role"]

    def get_name(self, membership: Membership) -> str:
        return membership.usuario.first_name or membership.usuario.username


class ProjectListSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(source="nome", read_only=True)
    mode = serializers.SerializerMethodField()
    activityCount = serializers.SerializerMethodField()
    completedCount = serializers.SerializerMethodField()
    hierarchyLevels = serializers.SerializerMethodField()
    progressPercent = serializers.SerializerMethodField()
    spi = serializers.SerializerMethodField()
    team = TeamMemberSerializer(source="memberships", many=True, read_only=True)
    updatedAt = serializers.DateTimeField(source="atualizado_em", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "mode",
            "activityCount",
            "completedCount",
            "hierarchyLevels",
            "progressPercent",
            "spi",
            "team",
            "updatedAt",
        ]

    def get_mode(self, project: Project) -> str:
        return project.modo.lower()

    def get_activityCount(self, project: Project) -> int:
        return 0

    def get_completedCount(self, project: Project) -> int:
        return 0

    def get_hierarchyLevels(self, project: Project) -> list[str]:
        return project.nomes_niveis_hierarquia

    def get_progressPercent(self, project: Project) -> int:
        return 0

    def get_spi(self, project: Project):
        return None
