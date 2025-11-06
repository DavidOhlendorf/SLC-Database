from django.urls import path
from .views import VariableDetail

urlpatterns = [
    path('<int:pk>/', VariableDetail.as_view(), name='variable_detail'),
]

