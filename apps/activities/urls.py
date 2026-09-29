from django.urls import path

from .views import (
    ActivityBlockView,
    ActivityCancelView,
    ActivityCollectionView,
    ActivityCompleteView,
    ActivityDetailView,
    ActivityImportView,
)

app_name = "activities"

urlpatterns = [
    path("", ActivityCollectionView.as_view(), name="list"),
    path("import/", ActivityImportView.as_view(), name="import"),
    path("<int:activity_id>/", ActivityDetailView.as_view(), name="detail"),
    path("<int:activity_id>/complete/", ActivityCompleteView.as_view(), name="complete"),
    path("<int:activity_id>/block/", ActivityBlockView.as_view(), name="block"),
    path("<int:activity_id>/cancel/", ActivityCancelView.as_view(), name="cancel"),
]
