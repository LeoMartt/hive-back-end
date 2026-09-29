from rest_framework import serializers

from apps.activities.services import resolver_activity_por_codigo
from common.validators.attachments import validar_anexo_evidencia

from .models import Issue


STATUS_API = {
    Issue.Status.ABERTA: "aberta",
    Issue.Status.EM_ANALISE: "em_analise",
    Issue.Status.SOLUCAO_PROPOSTA: "solucao_proposta",
    Issue.Status.CONCLUIDA: "concluida",
    Issue.Status.CANCELADA: "cancelada",
}

TIPO_API = {
    Issue.Tipo.REQUISITO: "requisito",
    Issue.Tipo.PERFORMANCE: "performance",
    Issue.Tipo.DADOS: "dados",
    Issue.Tipo.INTEGRACAO: "integracao",
    Issue.Tipo.INTERFACE: "interface",
    Issue.Tipo.CONFIGURACAO: "configuracao",
    Issue.Tipo.OUTRO: "outro",
}

IMPACTO_API = {
    Issue.Impacto.MUITO_ALTO: "muito_alto",
    Issue.Impacto.ALTO: "alto",
    Issue.Impacto.MEDIO: "medio",
    Issue.Impacto.BAIXO: "baixo",
}

TIPO_MODEL = {value: key for key, value in TIPO_API.items()}
IMPACTO_MODEL = {value: key for key, value in IMPACTO_API.items()}


def nome_usuario(usuario) -> str:
    return usuario.first_name or usuario.username or usuario.email


class IssueSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    numericId = serializers.IntegerField(source="id", read_only=True)
    projectId = serializers.UUIDField(source="projeto_id", read_only=True)
    title = serializers.CharField(source="titulo", read_only=True)
    status = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    impact = serializers.SerializerMethodField()
    area = serializers.CharField(source="atividade.area", read_only=True)
    tester = serializers.SerializerMethodField()
    testerId = serializers.SerializerMethodField()
    dev = serializers.SerializerMethodField()
    developerId = serializers.SerializerMethodField()
    relatedActivityId = serializers.SerializerMethodField()
    relatedActivityNumericId = serializers.IntegerField(source="atividade_id", read_only=True)
    cascadeActivityIds = serializers.SerializerMethodField()
    openedAt = serializers.DateTimeField(source="criada_em", read_only=True)
    resolvedAt = serializers.DateTimeField(source="resolvida_em", read_only=True)
    description = serializers.CharField(source="descricao", read_only=True)
    impactNote = serializers.CharField(source="nota_impacto", read_only=True)
    proposedSolution = serializers.SerializerMethodField()
    analysisStartedAt = serializers.DateTimeField(source="analise_iniciada_em", read_only=True)
    solutionProposedAt = serializers.DateTimeField(source="solucao_proposta_em", read_only=True)
    openingAttachment = serializers.JSONField(source="anexo_abertura", read_only=True)
    solutionAttachment = serializers.JSONField(source="anexo_solucao", read_only=True)
    createdAt = serializers.DateTimeField(source="criada_em", read_only=True)
    updatedAt = serializers.DateTimeField(source="atualizada_em", read_only=True)

    class Meta:
        model = Issue
        fields = [
            "id",
            "numericId",
            "projectId",
            "title",
            "status",
            "impeditiva",
            "type",
            "impact",
            "area",
            "tester",
            "testerId",
            "dev",
            "developerId",
            "relatedActivityId",
            "relatedActivityNumericId",
            "cascadeActivityIds",
            "openedAt",
            "resolvedAt",
            "description",
            "impactNote",
            "proposedSolution",
            "analysisStartedAt",
            "solutionProposedAt",
            "openingAttachment",
            "solutionAttachment",
            "createdAt",
            "updatedAt",
        ]

    def get_id(self, issue: Issue) -> str:
        return issue.codigo_visivel

    def get_status(self, issue: Issue) -> str:
        return STATUS_API[issue.status]

    def get_type(self, issue: Issue) -> str:
        return TIPO_API[issue.tipo]

    def get_impact(self, issue: Issue) -> str:
        return IMPACTO_API[issue.impacto]

    def get_tester(self, issue: Issue) -> str:
        return nome_usuario(issue.tester)

    def get_testerId(self, issue: Issue) -> str:
        return str(issue.tester.entra_object_id or issue.tester_id)

    def get_dev(self, issue: Issue) -> str:
        return nome_usuario(issue.desenvolvedor)

    def get_developerId(self, issue: Issue) -> str:
        return str(issue.desenvolvedor.entra_object_id or issue.desenvolvedor_id)

    def get_relatedActivityId(self, issue: Issue) -> str:
        return issue.atividade.codigo_visivel

    def get_cascadeActivityIds(self, issue: Issue) -> list[str]:
        return []

    def get_proposedSolution(self, issue: Issue) -> str | None:
        return issue.solucao_proposta or None


class IssueCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField()
    type = serializers.ChoiceField(choices=list(TIPO_MODEL))
    impeditiva = serializers.BooleanField()
    impact = serializers.ChoiceField(choices=list(IMPACTO_MODEL))
    impactNote = serializers.CharField(required=False, allow_blank=True)
    dev = serializers.CharField(required=False, allow_blank=True)
    developerId = serializers.UUIDField(required=False)
    relatedActivityId = serializers.CharField(max_length=20)
    openingAttachment = serializers.JSONField(required=False, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("dev") and not attrs.get("developerId"):
            raise serializers.ValidationError({"dev": "Desenvolvedor responsável é obrigatório."})

        project = self.context["project"]
        attrs["activity"] = resolver_activity_por_codigo(attrs.pop("relatedActivityId"), project)
        attrs["type"] = TIPO_MODEL[attrs["type"]]
        attrs["impact"] = IMPACTO_MODEL[attrs["impact"]]
        attrs["openingAttachment"] = validar_anexo_evidencia(
            attrs.get("openingAttachment"),
            field_name="openingAttachment",
        )
        if (
            attrs["impeditiva"]
            and project.exigir_evidencia_issue
            and not attrs.get("openingAttachment")
        ):
            raise serializers.ValidationError(
                {"openingAttachment": "Evidência é obrigatória para issue impeditiva."}
            )
        return attrs


class IssueProposeSolutionSerializer(serializers.Serializer):
    proposedSolution = serializers.CharField()
    solutionAttachment = serializers.JSONField(required=False, allow_null=True)

    def validate_solutionAttachment(self, value):
        return validar_anexo_evidencia(value, field_name="solutionAttachment")
