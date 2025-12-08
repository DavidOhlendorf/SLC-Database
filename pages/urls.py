
from django.urls import path
from .views import QuestionnaireWaveListView  

app_name = "pages"

urlpatterns = [
    path(
        "questionnaires/",
        QuestionnaireWaveListView.as_view(),
        name="questionnaire_list",
    ),
]
