from django.urls import path
from .views import VariableDetail

app_name = "variables"

urlpatterns = [
    path('<int:pk>/', VariableDetail.as_view(), name='variable_detail'),
]

