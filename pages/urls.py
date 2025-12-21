from django.urls import path

from .views import WavePageDetailView, WavePageUpdateView

app_name = "pages"

urlpatterns = [
    path("<int:pk>/", WavePageDetailView.as_view(), name="page-detail"),
    path("<int:pk>/edit/", WavePageUpdateView.as_view(), name="page-edit"),
]
