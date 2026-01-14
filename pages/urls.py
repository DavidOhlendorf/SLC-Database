from django.urls import path
from . import views

app_name = "pages"


urlpatterns = [
    path("<int:pk>/", views.WavePageDetailView.as_view(), name="page-detail"),
    path("<int:pk>/edit/", views.WavePageUpdateView.as_view(), name="page-edit"),

    #  Page zur Überprüfung verwaister Fragen    
    path("orphans/review/", views.OrphanQuestionsReviewView.as_view(), name="orphan_questions_review"),


    # 2 POST-Endpunkte für die Bearbeitung von Basis- und Inhaltsdaten einer Seite
    path("<int:pk>/edit/base/", views.WavePageBaseUpdateView.as_view(), name="page-edit-base"),
    path("<int:pk>/edit/content/", views.WavePageContentUpdateView.as_view(), name="page-edit-content"),

    # Ein POST-Endpunkt zum Löschen einer Seite
    path("<int:pk>/delete/", views.WavePageDeleteView.as_view(), name="page-delete"),

    # Programmiervorlage (PV) einer Seite anzeigen
    path("<int:pk>/pv/", views.WavePagePVView.as_view(), name="pv"),

    # API für Modal zum Duplizieren von Seiten
    path("api/surveys/", views.SurveyListApiView.as_view(), name="api-surveys"),
    path("api/surveys/<int:survey_id>/waves/", views.WavesBySurveyApiView.as_view(), name="api-waves-by-survey"),
    path("api/pages/check-name/", views.CheckPageNameApiView.as_view(), name="api-check-page-name"),

    # Seite duplizieren
    path("<int:pk>/copy/", views.WavePageCopyView.as_view(), name="page-copy"),

]
 