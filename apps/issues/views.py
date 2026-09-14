from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project
from apps.projects.services import exigir_gestor

from .models import Issue
from .serializers import IssueCreateSerializer, IssueProposeSolutionSerializer, IssueSerializer
from .services import cancelar_issue, concluir_issue, criar_issue, iniciar_analise_issue, propor_solucao_issue


class IssueQuerysetMixin:
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

    def issue_queryset(self, project):
        return Issue.objects.filter(projeto=project).select_related(
            "projeto",
            "atividade",
            "tester",
            "desenvolvedor",
        )

    def get_issue(self, project, issue_id):
        return get_object_or_404(self.issue_queryset(project), id=issue_id)


class IssueCollectionView(IssueQuerysetMixin, APIView):
    def get(self, request, project_id):
        project = self.visible_project(project_id)
        queryset = self.issue_queryset(project)
        activity_id = request.query_params.get("activityId")
        if activity_id:
            queryset = queryset.filter(atividade_id=activity_id)
        serializer = IssueSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, project_id):
        project = self.visible_project(project_id)
        serializer = IssueCreateSerializer(data=request.data, context={"project": project})
        serializer.is_valid(raise_exception=True)
        issue = criar_issue(projeto=project, usuario=request.user, dados=serializer.validated_data)
        return Response(IssueSerializer(issue).data, status=status.HTTP_201_CREATED)


class IssueDetailView(IssueQuerysetMixin, APIView):
    def get(self, request, project_id, issue_id):
        project = self.visible_project(project_id)
        issue = self.get_issue(project, issue_id)
        return Response(IssueSerializer(issue).data)


class IssueStartAnalysisView(IssueQuerysetMixin, APIView):
    def post(self, request, project_id, issue_id):
        project = self.visible_project(project_id)
        issue = self.get_issue(project, issue_id)
        issue = iniciar_analise_issue(issue=issue, usuario=request.user)
        return Response(IssueSerializer(issue).data)


class IssueProposeSolutionView(IssueQuerysetMixin, APIView):
    def post(self, request, project_id, issue_id):
        project = self.visible_project(project_id)
        issue = self.get_issue(project, issue_id)
        serializer = IssueProposeSolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        issue = propor_solucao_issue(issue=issue, usuario=request.user, dados=serializer.validated_data)
        return Response(IssueSerializer(issue).data)


class IssueResolveView(IssueQuerysetMixin, APIView):
    def post(self, request, project_id, issue_id):
        project = self.visible_project(project_id)
        issue = self.get_issue(project, issue_id)
        issue = concluir_issue(issue=issue, usuario=request.user)
        return Response(IssueSerializer(issue).data)


class IssueCancelView(IssueQuerysetMixin, APIView):
    def post(self, request, project_id, issue_id):
        project = self.visible_project(project_id)
        exigir_gestor(request.user, project)
        issue = self.get_issue(project, issue_id)
        issue = cancelar_issue(issue=issue)
        return Response(IssueSerializer(issue).data)
