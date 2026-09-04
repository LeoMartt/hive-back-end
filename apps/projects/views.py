from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Membership, NoHierarquia, Papel, Project
from .serializers import (
    MembershipSerializer,
    NoHierarquiaSerializer,
    NoHierarquiaWriteSerializer,
    PapelSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    ProjectUpdateSerializer,
    TeamMemberInputSerializer,
)
from .services import (
    atualizar_projeto,
    criar_membership,
    criar_projeto,
    desativar_projeto,
    exigir_gestor,
    salvar_no_hierarquia,
)


class ProjectPagination(PageNumberPagination):
    page_size = 10


class ProjectQuerysetMixin:
    def base_queryset(self):
        return Project.objects.filter(ativo=True).prefetch_related(
            "memberships__usuario",
            "memberships__papel",
        ).order_by(
            "-criado_em",
            "nome",
        )

    def visible_queryset(self):
        user = self.request.user
        queryset = self.base_queryset()
        if user.is_staff or user.is_superuser:
            return queryset
        return queryset.filter(memberships__usuario=user).distinct()

    def get_project(self, project_id):
        return get_object_or_404(self.visible_queryset(), id=project_id)


class ProjectCollectionView(ProjectQuerysetMixin, APIView):
    def get(self, request):
        queryset = self.visible_queryset()
        if queryset.count() > ProjectPagination.page_size:
            paginator = ProjectPagination()
            page = paginator.paginate_queryset(queryset, request, view=self)
            serializer = ProjectListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ProjectListSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = criar_projeto(usuario=request.user, dados=serializer.validated_data)
        return Response(ProjectDetailSerializer(project).data, status=status.HTTP_201_CREATED)


class ProjectListView(ProjectCollectionView):
    pass


class ProjectDetailView(ProjectQuerysetMixin, APIView):
    def get(self, request, project_id):
        project = self.get_project(project_id)
        return Response(ProjectDetailSerializer(project).data)

    def patch(self, request, project_id):
        project = self.get_project(project_id)
        exigir_gestor(request.user, project)
        serializer = ProjectUpdateSerializer(
            data=request.data,
            partial=True,
            context={"project": project},
        )
        serializer.is_valid(raise_exception=True)
        project = atualizar_projeto(projeto=project, dados=serializer.validated_data)
        return Response(ProjectDetailSerializer(project).data)

    def delete(self, request, project_id):
        project = self.get_project(project_id)
        exigir_gestor(request.user, project)
        desativar_projeto(projeto=project)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PapelListView(ListAPIView):
    queryset = Papel.objects.all()
    serializer_class = PapelSerializer


class NoHierarquiaCollectionView(ProjectQuerysetMixin, APIView):
    def get(self, request, project_id):
        project = self.get_project(project_id)
        queryset = project.nos_hierarquia.select_related("parent")
        serializer = NoHierarquiaSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, project_id):
        project = self.get_project(project_id)
        exigir_gestor(request.user, project)
        serializer = NoHierarquiaWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parent_id = serializer.validated_data.get("parentId")
        parent = None
        if parent_id:
            parent = get_object_or_404(NoHierarquia, id=parent_id, projeto=project)

        no = NoHierarquia(
            projeto=project,
            parent=parent,
            nivel=serializer.validated_data["level"],
            nome=serializer.validated_data["name"].strip(),
            ordem=serializer.validated_data.get("order"),
        )
        no = salvar_no_hierarquia(no)
        return Response(NoHierarquiaSerializer(no).data, status=status.HTTP_201_CREATED)


class NoHierarquiaDetailView(ProjectQuerysetMixin, APIView):
    def get_no(self, project, node_id):
        return get_object_or_404(NoHierarquia, id=node_id, projeto=project)

    def patch(self, request, project_id, node_id):
        project = self.get_project(project_id)
        exigir_gestor(request.user, project)
        no = self.get_no(project, node_id)
        serializer = NoHierarquiaWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        parent_id = serializer.validated_data.get("parentId", no.parent_id)
        parent = no.parent
        if parent_id is None:
            parent = None
        elif parent_id != no.parent_id:
            parent = get_object_or_404(NoHierarquia, id=parent_id, projeto=project)

        if "parentId" in serializer.validated_data:
            no.parent = parent
        if "level" in serializer.validated_data:
            no.nivel = serializer.validated_data["level"]
        if "name" in serializer.validated_data:
            no.nome = serializer.validated_data["name"].strip()
        if "order" in serializer.validated_data:
            no.ordem = serializer.validated_data["order"]

        no = salvar_no_hierarquia(no)
        return Response(NoHierarquiaSerializer(no).data)

class MembershipCollectionView(ProjectQuerysetMixin, APIView):
    def get(self, request, project_id):
        project = self.get_project(project_id)
        queryset = project.memberships.select_related("usuario", "papel", "convidado_por")
        serializer = MembershipSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, project_id):
        project = self.get_project(project_id)
        exigir_gestor(request.user, project)
        serializer = TeamMemberInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = criar_membership(project, serializer.validated_data, request.user)
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class MembershipDetailView(ProjectQuerysetMixin, APIView):
    def delete(self, request, project_id, membership_id):
        project = self.get_project(project_id)
        exigir_gestor(request.user, project)
        membership = get_object_or_404(Membership, id=membership_id, projeto=project)
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
