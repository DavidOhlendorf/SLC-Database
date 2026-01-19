#waves/urls.py

from django.urls import path
from .views import SurveyListView, SurveyDetailView, SurveyCreateView, SurveyUpdateView  

app_name = "waves"

urlpatterns = [
    path("",SurveyListView.as_view(),name="survey_list",),
    path("create/",SurveyCreateView.as_view(),name="survey_create",),
    path("<int:pk>/edit/", SurveyUpdateView.as_view(), name="survey_edit"),
    path("<str:survey_name>/",SurveyDetailView.as_view(),name="survey_detail",),
]
