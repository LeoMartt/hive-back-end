import json

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project
from .models import Issue
from .serializers import IssueCreateSerializer, IssueProposeSolutionSerializer, IssueSerializer
from .services import cancelar_issue, concluir_issue, criar_issue, iniciar_analise_issue, propor_solucao_issue


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
    parser_classes = [JSONParser, MultiPartParser, FormParser]

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
        opening_file = request.FILES.get("openingFile")
        dados = dados_request_com_json(request, ("openingAttachment",))
        if opening_file is not None and not dados.get("openingAttachment"):
            dados["openingAttachment"] = {
                "fileName": opening_file.name,
                "sizeLabel": f"{max(1, (opening_file.size + 1023) // 1024)} KB",
                "uploadedBy": request.user.first_name or request.user.username,
                "uploadedAt": "",
                "contentType": getattr(opening_file, "content_type", "") or "",
            }
        serializer = IssueCreateSerializer(data=dados, context={"project": project})
        serializer.is_valid(raise_exception=True)
        issue = criar_issue(
            projeto=project,
            usuario=request.user,
            dados=serializer.validated_data,
            opening_file=opening_file,
        )
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
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, project_id, issue_id):
        project = self.visible_project(project_id)
        issue = self.get_issue(project, issue_id)
        solution_file = request.FILES.get("solutionFile")
        dados = dados_request_com_json(request, ("solutionAttachment",))
        if solution_file is not None and not dados.get("solutionAttachment"):
            dados["solutionAttachment"] = {
                "fileName": solution_file.name,
                "sizeLabel": f"{max(1, (solution_file.size + 1023) // 1024)} KB",
                "uploadedBy": request.user.first_name or request.user.username,
                "uploadedAt": "",
                "contentType": getattr(solution_file, "content_type", "") or "",
            }
        serializer = IssueProposeSolutionSerializer(data=dados)
        serializer.is_valid(raise_exception=True)
        issue = propor_solucao_issue(
            issue=issue,
            usuario=request.user,
            dados=serializer.validated_data,
            solution_file=solution_file,
        )
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
        issue = self.get_issue(project, issue_id)
        issue = cancelar_issue(issue=issue, usuario=request.user)
        return Response(IssueSerializer(issue).data)
