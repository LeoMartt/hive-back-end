from rest_framework.generics import ListAPIView

from .models import Project
from .serializers import ProjectListSerializer


class ProjectListView(ListAPIView):
    serializer_class = ProjectListSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Project.objects.prefetch_related(
            "memberships__usuario",
            "memberships__papel",
        )

        if user.is_staff or user.is_superuser:
            return queryset

        return queryset.filter(memberships__usuario=user).distinct()
