
from django.urls import path
from .views import SurveyListView, SurveyDetailView  

app_name = "waves"

urlpatterns = [
    path("",SurveyListView.as_view(),name="survey_list",),
    path("<str:surveyyear>/",SurveyDetailView.as_view(),name="survey_detail",),
]
