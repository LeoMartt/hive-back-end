from django.urls import path

from .views import ActivityCancelView, ActivityCollectionView, ActivityDetailView

app_name = "activities"

urlpatterns = [
    path("", ActivityCollectionView.as_view(), name="list"),
    path("<int:activity_id>/", ActivityDetailView.as_view(), name="detail"),
    path("<int:activity_id>/cancel/", ActivityCancelView.as_view(), name="cancel"),
]
