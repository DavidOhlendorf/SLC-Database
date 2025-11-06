from django.urls import path
from .views import QuestionDetail

urlpatterns = [
    path('<int:pk>/', QuestionDetail.as_view(), name='question_detail'),
]