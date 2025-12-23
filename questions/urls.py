from django.urls import path
from .views import QuestionDetail, QuestionCreateFromPageView, QuestionUpdateView

app_name = "questions"

urlpatterns = [
    path('<int:pk>/', QuestionDetail.as_view(), name='question_detail'),
    path('from_page/<int:page_id>/create/', QuestionCreateFromPageView.as_view(), name='question_create_from_page'),
    path("<int:pk>/edit/", QuestionUpdateView.as_view(), name="question_edit"),

]