from django.urls import path
from .views import QuestionDetail, QuestionCreateFromPageView, QuestionUpdateView
from . import views

app_name = "questions"

urlpatterns = [
    path('<int:pk>/', QuestionDetail.as_view(), name='question_detail'),
    path('from_page/<int:page_id>/create/', QuestionCreateFromPageView.as_view(), name='question_create_from_page'),
    path("<int:pk>/edit/", QuestionUpdateView.as_view(), name="question_edit"),

    # Keywords
    path("keywords/search/", views.KeywordSearchView.as_view(), name="keyword_search"),
    path("keywords/create/", views.KeywordCreateView.as_view(), name="keyword_create"),

]