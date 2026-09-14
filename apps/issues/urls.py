from django.urls import path

from .views import (
    IssueCancelView,
    IssueCollectionView,
    IssueDetailView,
    IssueProposeSolutionView,
    IssueResolveView,
    IssueStartAnalysisView,
)

app_name = "issues"

urlpatterns = [
    path("", IssueCollectionView.as_view(), name="list"),
    path("<int:issue_id>/", IssueDetailView.as_view(), name="detail"),
    path("<int:issue_id>/start-analysis/", IssueStartAnalysisView.as_view(), name="start-analysis"),
    path("<int:issue_id>/propose-solution/", IssueProposeSolutionView.as_view(), name="propose-solution"),
    path("<int:issue_id>/resolve/", IssueResolveView.as_view(), name="resolve"),
    path("<int:issue_id>/cancel/", IssueCancelView.as_view(), name="cancel"),
]
