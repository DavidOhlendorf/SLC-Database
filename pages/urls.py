from django.urls import path

from .views import WavePageDetailView, WavePageUpdateView, WavePageBaseUpdateView, WavePageContentUpdateView

app_name = "pages"


urlpatterns = [
    path("<int:pk>/", WavePageDetailView.as_view(), name="page-detail"),
    path("<int:pk>/edit/", WavePageUpdateView.as_view(), name="page-edit"),

 # 2 POST-Endpunkte für die Bearbeitung von Basis- und Inhaltsdaten einer Seite
    path("<int:pk>/edit/base/", WavePageBaseUpdateView.as_view(), name="page-edit-base"),
    path("<int:pk>/edit/content/", WavePageContentUpdateView.as_view(), name="page-edit-content"),
]
