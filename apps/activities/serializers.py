from rest_framework import serializers

from .models import Activity
from .services import formatar_codigo_activity, resolver_activity_por_codigo


STATUS_API = {
    Activity.Status.AGUARDANDO: "aguardando",
    Activity.Status.LIBERADO: "liberado",
    Activity.Status.BLOQUEADO: "bloqueado",
    Activity.Status.CONCLUIDO: "concluido",
    Activity.Status.CANCELADO: "cancelado",
}


class ActivitySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    numericId = serializers.IntegerField(source="id", read_only=True)
    projectId = serializers.UUIDField(source="projeto_id", read_only=True)
    nodeId = serializers.UUIDField(source="no_id", read_only=True)
    name = serializers.CharField(source="nome", read_only=True)
    status = serializers.SerializerMethodField()
    module = serializers.SerializerMethodField()
    process = serializers.SerializerMethodField()
    tester = serializers.SerializerMethodField()
    testerId = serializers.SerializerMethodField()
    dev = serializers.SerializerMethodField()
    developerId = serializers.SerializerMethodField()
    plannedStart = serializers.DateField(source="data_inicio_planejada", read_only=True)
    plannedEnd = serializers.DateField(source="data_conclusao_planejada", read_only=True)
    actualStart = serializers.DateField(source="data_inicio_real", read_only=True)
    actualEnd = serializers.DateField(source="data_conclusao_real", read_only=True)
    predecessors = serializers.SerializerMethodField()
    predecessorIds = serializers.SerializerMethodField()
    retestCount = serializers.IntegerField(source="numero_retest", read_only=True)
    issueCount = serializers.SerializerMethodField()
    wbs = serializers.CharField(read_only=True)
    area = serializers.CharField(read_only=True)
    system = serializers.CharField(source="sistema", read_only=True)
    transaction = serializers.CharField(source="transacao", read_only=True)
    expectedResult = serializers.CharField(source="resultado_esperado", read_only=True)
    notes = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    approvalEvidence = serializers.SerializerMethodField()
    approvalNote = serializers.CharField(source="observacao_aprovacao", read_only=True)
    rejectedAt = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="criado_em", read_only=True)
    updatedAt = serializers.DateTimeField(source="atualizado_em", read_only=True)

    class Meta:
        model = Activity
        fields = [
            "id",
            "numericId",
            "projectId",
            "nodeId",
            "name",
            "status",
            "module",
            "process",
            "tester",
            "testerId",
            "dev",
            "developerId",
            "plannedStart",
            "plannedEnd",
            "actualStart",
            "actualEnd",
            "predecessors",
            "predecessorIds",
            "retestCount",
            "issueCount",
            "wbs",
            "area",
            "system",
            "transaction",
            "expectedResult",
            "notes",
            "attachments",
            "approvalEvidence",
            "approvalNote",
            "rejectedAt",
            "createdAt",
            "updatedAt",
        ]

    def get_id(self, activity: Activity) -> str:
        return activity.codigo_visivel

    def get_status(self, activity: Activity) -> str:
        return STATUS_API[activity.status]

    def get_module(self, activity: Activity) -> str:
        if activity.no.nivel == 1:
            return activity.no.nome
        return activity.no.parent.nome if activity.no.parent else ""

    def get_process(self, activity: Activity) -> str:
        if activity.no.nivel == 1:
            return ""
        return activity.no.nome

    def get_tester(self, activity: Activity) -> str:
        return activity.tester.first_name or activity.tester.username

    def get_testerId(self, activity: Activity) -> str:
        return str(activity.tester.entra_object_id or activity.tester_id)

    def get_dev(self, activity: Activity) -> str:
        return activity.desenvolvedor.first_name or activity.desenvolvedor.username

    def get_developerId(self, activity: Activity) -> str:
        return str(activity.desenvolvedor.entra_object_id or activity.desenvolvedor_id)

    def get_predecessors(self, activity: Activity) -> list[str]:
        return [predecessora.codigo_visivel for predecessora in activity.predecessoras.all()]

    def get_predecessorIds(self, activity: Activity) -> list[int]:
        return [predecessora.id for predecessora in activity.predecessoras.all()]

    def get_issueCount(self, activity: Activity) -> int:
        return 0

    def get_notes(self, activity: Activity) -> str | None:
        return activity.observacoes or None

    def get_attachments(self, activity: Activity) -> list:
        return []

    def get_approvalEvidence(self, activity: Activity):
        return None

    def get_rejectedAt(self, activity: Activity):
        return None


class ActivityWriteSerializer(serializers.Serializer):
    nodeId = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=200, required=False)
    testerId = serializers.UUIDField(required=False)
    developerId = serializers.UUIDField(required=False)
    plannedStart = serializers.DateField(required=False)
    plannedEnd = serializers.DateField(required=False)
    predecessorIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    predecessors = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    area = serializers.CharField(max_length=100, required=False, allow_blank=True)
    system = serializers.CharField(max_length=100, required=False, allow_blank=True)
    transaction = serializers.CharField(max_length=50, required=False, allow_blank=True)
    wbs = serializers.CharField(max_length=50, required=False, allow_blank=True)
    expectedResult = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        if "predecessors" in attrs and "predecessorIds" in attrs:
            raise serializers.ValidationError(
                {"predecessors": "Use predecessorIds ou predecessors, não ambos."}
            )

        if "predecessors" in attrs:
            project = self.context["project"]
            attrs["predecessorIds"] = [
                resolver_activity_por_codigo(codigo, project).id for codigo in attrs.pop("predecessors")
            ]

        planned_start = attrs.get("plannedStart")
        planned_end = attrs.get("plannedEnd")
        instance = self.context.get("activity")
        if instance is not None:
            planned_start = planned_start or instance.data_inicio_planejada
            planned_end = planned_end or instance.data_conclusao_planejada
        if planned_start and planned_end and planned_start > planned_end:
            raise serializers.ValidationError(
                {"plannedEnd": "Conclusão planejada deve ser maior ou igual ao início."}
            )
        return attrs


class ActivityCreateSerializer(ActivityWriteSerializer):
    nodeId = serializers.UUIDField()
    name = serializers.CharField(max_length=200)
    testerId = serializers.UUIDField()
    developerId = serializers.UUIDField()
    plannedStart = serializers.DateField()
    plannedEnd = serializers.DateField()


class ActivityCompleteSerializer(serializers.Serializer):
    approvalNote = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ActivityBlockSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)
