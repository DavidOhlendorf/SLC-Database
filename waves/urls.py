
from django.urls import path
from .views import SurveyListView, SurveyDetailView  

app_name = "waves"

urlpatterns = [
    path("",SurveyListView.as_view(),name="survey_list",),
    path("<str:survey_name>/",SurveyDetailView.as_view(),name="survey_detail",),
]
