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

    # Ein POST-Endpunkt zum Hinzufügen einer neuen Frage zu einer Seite
    path("<int:pk>/questions/quick-create/", views.WavePageQuestionQuickCreateView.as_view(), name="page-question-quick-create"),

]
