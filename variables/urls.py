from django.urls import path
from . import views

app_name = "variables"

urlpatterns = [
    path('<int:pk>/', views.VariableDetail.as_view(), name='variable_detail'),
    path("<int:pk>/edit/", views.VariableUpdateView.as_view(), name="variable_edit"),
    path("<int:pk>/delete/", views.VariableDeleteView.as_view(), name="variable_delete"),

    # AJAX-Endpoint für Variable-Vorschläge
    path("suggest/", views.VariableSuggestView.as_view(), name="variable_suggest"),

    # AJAX-Endpoint für Variablenname-Prüfung
    path("varname-check/", views.VariableVarnameCheckView.as_view(), name="variable_varname_check"),

    # AJAX-Endpoint für Variable-Schnellerstellung
    path("quickcreate/", views.VariableQuickCreateView.as_view(), name="variable_quickcreate"),

    # AJAX-Endpoint für Variable-Schnellerstellung aus Question-Detail
    path("quickcreate/question/", views.VariableQuickCreateForQuestionView.as_view(), name="variable_quickcreate_question"),

]

