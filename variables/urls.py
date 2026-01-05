from django.urls import path
from . import views

app_name = "variables"

urlpatterns = [
    path('<int:pk>/', views.VariableDetail.as_view(), name='variable_detail'),

    # AJAX-Endpoint für Variable-Vorschläge
    path("api/suggest/", views.VariableSuggestView.as_view(), name="variable_suggest"),
]

