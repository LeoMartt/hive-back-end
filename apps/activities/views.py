import json

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .importer import importar_activities_de_arquivo
from apps.projects.models import Project
from apps.projects.services import exigir_gestor, usuario_pode_gerenciar_projeto

from .models import Activity
from .serializers import (
    ActivityBlockSerializer,
    ActivityCompleteSerializer,
    ActivityCreateSerializer,
    ActivitySerializer,
    ActivityWriteSerializer,
)
from .services import (
    atualizar_activity,
    bloquear_activity,
    cancelar_activity,
    concluir_activity,
    criar_activity,
)


def dados_request_com_json(request, json_fields: tuple[str, ...]) -> dict:
    dados = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)
    for field in json_fields:
        value = dados.get(field)
        if isinstance(value, str) and value.strip():
            try:
                dados[field] = json.loads(value)
            except json.JSONDecodeError:
                pass
    return dados


def usuario_pode_testar_activity(user, activity):
    return activity.tester_id == user.id


def exigir_gestor_ou_tester_da_activity(user, activity) -> None:
    if usuario_pode_gerenciar_projeto(user, activity.projeto):
        return
    if usuario_pode_testar_activity(user, activity):
        return
    raise PermissionDenied("Apenas gestores ou o tester da atividade podem executar esta ação.")


class ActivityQuerysetMixin:
    def get_project(self, project_id):
        return get_object_or_404(Project.objects.filter(ativo=True), id=project_id)

    def visible_project(self, project_id):
        project = self.get_project(project_id)
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return project
        if project.memberships.filter(usuario=user).exists():
            return project
        return get_object_or_404(Project.objects.none(), id=project_id)

    def activity_queryset(self, project):
        return Activity.objects.filter(projeto=project).select_related(
            "projeto",
            "no",
            "no__parent",
            "tester",
            "desenvolvedor",
        ).prefetch_related("predecessoras")

    def get_activity(self, project, activity_id):
        return get_object_or_404(self.activity_queryset(project), id=activity_id)


class ActivityCollectionView(ActivityQuerysetMixin, APIView):
    def get(self, request, project_id):
        project = self.visible_project(project_id)
        queryset = self.activity_queryset(project)
        serializer = ActivitySerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, project_id):
        project = self.visible_project(project_id)
        exigir_gestor(request.user, project)
        serializer = ActivityCreateSerializer(data=request.data, context={"project": project})
        serializer.is_valid(raise_exception=True)
        activity = criar_activity(projeto=project, dados=serializer.validated_data)
        return Response(ActivitySerializer(activity).data, status=status.HTTP_201_CREATED)


class ActivityImportView(ActivityQuerysetMixin, APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, project_id):
        project = self.visible_project(project_id)
        exigir_gestor(request.user, project)
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response({"file": "Envie o arquivo no campo file."}, status=status.HTTP_400_BAD_REQUEST)

        activities = importar_activities_de_arquivo(projeto=project, uploaded_file=uploaded_file)
        serializer = ActivitySerializer(activities, many=True)
        return Response(
            {"created": len(activities), "activities": serializer.data},
            status=status.HTTP_201_CREATED,
        )


class ActivityDetailView(ActivityQuerysetMixin, APIView):
    def get(self, request, project_id, activity_id):
        project = self.visible_project(project_id)
        activity = self.get_activity(project, activity_id)
        return Response(ActivitySerializer(activity).data)

    def patch(self, request, project_id, activity_id):
        project = self.visible_project(project_id)
        exigir_gestor(request.user, project)
        activity = self.get_activity(project, activity_id)
        serializer = ActivityWriteSerializer(
            data=request.data,
            partial=True,
            context={"project": project, "activity": activity},
        )
        serializer.is_valid(raise_exception=True)
        activity = atualizar_activity(activity=activity, dados=serializer.validated_data)
        return Response(ActivitySerializer(activity).data)


class ActivityCancelView(ActivityQuerysetMixin, APIView):
    def post(self, request, project_id, activity_id):
        project = self.visible_project(project_id)
        exigir_gestor(request.user, project)
        activity = self.get_activity(project, activity_id)
        activity = cancelar_activity(activity=activity)
        return Response(ActivitySerializer(activity).data)


class ActivityCompleteView(ActivityQuerysetMixin, APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, project_id, activity_id):
        project = self.visible_project(project_id)
        activity = self.get_activity(project, activity_id)
        exigir_gestor_ou_tester_da_activity(request.user, activity)
        evidence_file = request.FILES.get("approvalFile")
        dados = dados_request_com_json(request, ("approvalEvidence",))
        if evidence_file is not None and not dados.get("approvalEvidence"):
            dados["approvalEvidence"] = {
                "fileName": evidence_file.name,
                "sizeLabel": f"{max(1, (evidence_file.size + 1023) // 1024)} KB",
                "uploadedBy": request.user.first_name or request.user.username,
                "uploadedAt": "",
                "contentType": getattr(evidence_file, "content_type", "") or "",
            }
        serializer = ActivityCompleteSerializer(data=dados)
        serializer.is_valid(raise_exception=True)
        activity = concluir_activity(
            activity=activity,
            observacao_aprovacao=serializer.validated_data.get("approvalNote") or "",
            evidencia_aprovacao=serializer.validated_data["approvalEvidence"],
            evidencia_file=evidence_file,
            usuario=request.user,
        )
        return Response(ActivitySerializer(activity).data)


class ActivityBlockView(ActivityQuerysetMixin, APIView):
    def post(self, request, project_id, activity_id):
        project = self.visible_project(project_id)
        activity = self.get_activity(project, activity_id)
        exigir_gestor_ou_tester_da_activity(request.user, activity)
        serializer = ActivityBlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activity = bloquear_activity(
            activity=activity,
            motivo=serializer.validated_data.get("reason") or "",
        )
        return Response(ActivitySerializer(activity).data)
