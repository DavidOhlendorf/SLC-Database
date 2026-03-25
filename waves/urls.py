#waves/urls.py

from django.urls import path
from .views import SurveyListView, SurveyDetailView, SurveyCreateView, SurveyUpdateView, WaveDocumentPdfView, WavePagesReorderApiView, WaveModulesManageView  

app_name = "waves"

urlpatterns = [
    path("",SurveyListView.as_view(),name="survey_list",),
    path("create/",SurveyCreateView.as_view(),name="survey_create",),
    path("<int:pk>/edit/", SurveyUpdateView.as_view(), name="survey_edit"),

    path("documents/<int:pk>/pdf/", WaveDocumentPdfView.as_view(), name="wave_document_pdf"),
    path("<str:survey_name>/",SurveyDetailView.as_view(),name="survey_detail",),


    # API endpoints
    path("api/waves/<int:wave_id>/modules/manage/", WaveModulesManageView.as_view(), name="wave_modules_manage"),
    path("api/waves/<int:wave_id>/pages/reorder/", WavePagesReorderApiView.as_view(), name="wave_pages_reorder"),
]