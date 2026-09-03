from django.urls import path

from .views import (
    MembershipCollectionView,
    MembershipDetailView,
    NoHierarquiaCollectionView,
    NoHierarquiaDetailView,
    PapelListView,
    ProjectCollectionView,
    ProjectDetailView,
)

app_name = "projects"

urlpatterns = [
    path("", ProjectCollectionView.as_view(), name="list"),
    path("roles/", PapelListView.as_view(), name="roles-list"),
    path("<uuid:project_id>/", ProjectDetailView.as_view(), name="detail"),
    path("<uuid:project_id>/hierarchy/", NoHierarquiaCollectionView.as_view(), name="hierarchy-list"),
    path(
        "<uuid:project_id>/hierarchy/<uuid:node_id>/",
        NoHierarquiaDetailView.as_view(),
        name="hierarchy-detail",
    ),
    path("<uuid:project_id>/memberships/", MembershipCollectionView.as_view(), name="memberships-list"),
    path(
        "<uuid:project_id>/memberships/<uuid:membership_id>/",
        MembershipDetailView.as_view(),
        name="memberships-detail",
    ),
]
