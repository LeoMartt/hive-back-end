from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

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
    def post(self, request, project_id, activity_id):
        project = self.visible_project(project_id)
        activity = self.get_activity(project, activity_id)
        exigir_gestor_ou_tester_da_activity(request.user, activity)
        serializer = ActivityCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activity = concluir_activity(
            activity=activity,
            observacao_aprovacao=serializer.validated_data.get("approvalNote") or "",
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
