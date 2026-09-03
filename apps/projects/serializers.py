from rest_framework import serializers

from .models import Membership, NoHierarquia, Papel, Project
from .services import resolver_codigo_papel


class TeamMemberSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    initials = serializers.CharField(source="usuario.iniciais", read_only=True)
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="usuario.email", read_only=True)
    role = serializers.CharField(source="papel.nome_exibicao", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "initials", "name", "email", "role"]

    def get_id(self, membership: Membership) -> str:
        return str(membership.usuario.entra_object_id or membership.usuario.id)

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


class ProjectDetailSerializer(ProjectListSerializer):
    description = serializers.CharField(source="descricao", read_only=True)
    agingAlertaDias = serializers.IntegerField(source="aging_alerta_dias", read_only=True)
    agingRiscoDias = serializers.IntegerField(source="aging_risco_dias", read_only=True)
    spiSaudavel = serializers.DecimalField(
        source="spi_saudavel",
        max_digits=3,
        decimal_places=2,
        read_only=True,
    )
    spiCritico = serializers.DecimalField(
        source="spi_critico",
        max_digits=3,
        decimal_places=2,
        read_only=True,
    )
    anexoMaxMb = serializers.IntegerField(source="anexo_max_mb", read_only=True)
    exigirEvidenciaAtividade = serializers.BooleanField(
        source="exigir_evidencia_atividade",
        read_only=True,
    )
    exigirEvidenciaIssue = serializers.BooleanField(
        source="exigir_evidencia_issue",
        read_only=True,
    )

    class Meta(ProjectListSerializer.Meta):
        fields = ProjectListSerializer.Meta.fields + [
            "description",
            "agingAlertaDias",
            "agingRiscoDias",
            "spiSaudavel",
            "spiCritico",
            "anexoMaxMb",
            "exigirEvidenciaAtividade",
            "exigirEvidenciaIssue",
        ]


class TeamMemberInputSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    initials = serializers.CharField(max_length=4, required=False, allow_blank=True)
    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.CharField(max_length=40)

    def validate_role(self, value: str) -> str:
        resolver_codigo_papel(value)
        return value


class ProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True)
    mode = serializers.ChoiceField(choices=["uat", "cutover", "UAT", "CUTOVER"])
    hierarchyLevels = serializers.ListField(
        child=serializers.CharField(max_length=60, allow_blank=False),
        min_length=1,
        max_length=2,
    )
    team = TeamMemberInputSerializer(many=True, required=False)

    def validate(self, attrs: dict) -> dict:
        mode = attrs["mode"].lower()
        levels = [level.strip() for level in attrs["hierarchyLevels"] if level.strip()]

        if mode == "uat" and len(levels) != 2:
            raise serializers.ValidationError(
                {"hierarchyLevels": "Projetos UAT exigem exatamente dois níveis."}
            )
        if mode == "cutover" and len(levels) != 1:
            raise serializers.ValidationError(
                {"hierarchyLevels": "Projetos Cutover exigem exatamente um nível."}
            )

        attrs["mode"] = mode
        attrs["hierarchyLevels"] = levels
        return attrs


class ProjectUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    hierarchyLevels = serializers.ListField(
        child=serializers.CharField(max_length=60, allow_blank=False),
        min_length=1,
        max_length=2,
        required=False,
    )
    agingAlertaDias = serializers.IntegerField(min_value=0, required=False)
    agingRiscoDias = serializers.IntegerField(min_value=0, required=False)
    spiSaudavel = serializers.DecimalField(max_digits=3, decimal_places=2, required=False)
    spiCritico = serializers.DecimalField(max_digits=3, decimal_places=2, required=False)
    anexoMaxMb = serializers.IntegerField(min_value=1, required=False)
    exigirEvidenciaAtividade = serializers.BooleanField(required=False)
    exigirEvidenciaIssue = serializers.BooleanField(required=False)

    def validate(self, attrs: dict) -> dict:
        project = self.context["project"]
        if "hierarchyLevels" not in attrs:
            return attrs

        levels = [level.strip() for level in attrs["hierarchyLevels"] if level.strip()]
        if project.modo == Project.Modo.UAT and len(levels) != 2:
            raise serializers.ValidationError(
                {"hierarchyLevels": "Projetos UAT exigem exatamente dois níveis."}
            )
        if project.modo == Project.Modo.CUTOVER and len(levels) != 1:
            raise serializers.ValidationError(
                {"hierarchyLevels": "Projetos Cutover exigem exatamente um nível."}
            )

        attrs["hierarchyLevels"] = levels
        return attrs


class PapelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Papel
        fields = ["id", "codigo", "nome_exibicao"]


class NoHierarquiaSerializer(serializers.ModelSerializer):
    parentId = serializers.UUIDField(source="parent_id", read_only=True)
    level = serializers.IntegerField(source="nivel", read_only=True)
    name = serializers.CharField(source="nome", read_only=True)
    order = serializers.IntegerField(source="ordem", read_only=True)
    createdAt = serializers.DateTimeField(source="criado_em", read_only=True)

    class Meta:
        model = NoHierarquia
        fields = ["id", "parentId", "level", "name", "order", "createdAt"]


class NoHierarquiaWriteSerializer(serializers.Serializer):
    parentId = serializers.UUIDField(required=False, allow_null=True)
    level = serializers.ChoiceField(choices=[1, 2])
    name = serializers.CharField(max_length=100)
    order = serializers.IntegerField(min_value=0, required=False, allow_null=True)


class MembershipSerializer(serializers.ModelSerializer):
    membershipId = serializers.UUIDField(source="id", read_only=True)
    id = serializers.SerializerMethodField()
    initials = serializers.CharField(source="usuario.iniciais", read_only=True)
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="usuario.email", read_only=True)
    role = serializers.CharField(source="papel.nome_exibicao", read_only=True)
    roleCode = serializers.CharField(source="papel.codigo", read_only=True)
    invitedBy = serializers.UUIDField(source="convidado_por_id", read_only=True)
    createdAt = serializers.DateTimeField(source="criado_em", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "membershipId",
            "id",
            "initials",
            "name",
            "email",
            "role",
            "roleCode",
            "invitedBy",
            "createdAt",
        ]

    def get_id(self, membership: Membership) -> str:
        return str(membership.usuario.entra_object_id or membership.usuario.id)

    def get_name(self, membership: Membership) -> str:
        return membership.usuario.first_name or membership.usuario.username
