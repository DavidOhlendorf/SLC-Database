from django.urls import path
from .views import QuestionDetail

app_name = "questions"

urlpatterns = [
    path('<int:pk>/', QuestionDetail.as_view(), name='question_detail'),
]