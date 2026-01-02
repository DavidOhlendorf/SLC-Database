from django.urls import path
from . import views

app_name = "questions"

urlpatterns = [
    path('<int:pk>/', views.QuestionDetail.as_view(), name='question_detail'),
    path('from_page/<int:page_id>/create/', views.QuestionCreateFromPageView.as_view(), name='question_create_from_page'),
    path("<int:pk>/edit/", views.QuestionUpdateView.as_view(), name="question_edit"),
    path("<int:pk>/delete/", views.QuestionDeleteView.as_view(), name="question_delete"),
    path("<int:pk>/attach-page/", views.QuestionAttachPageView.as_view(), name="question_attach_page"),

    # Keywords
    path("keywords/search/", views.KeywordSearchView.as_view(), name="keyword_search"),
    path("keywords/create/", views.KeywordCreateView.as_view(), name="keyword_create"),
    
    # AJAX-Endpoint zum schnellen Anlegen einer Frage bei der Seitenbearbeitung
    path("pages/<int:page_id>/questions/quick-create/",views.QuestionQuickCreateForPageAjaxView.as_view(),name="question-quick-create-for-page-ajax",),

    # Variablen zuweisen
    path("<int:pk>/variables/", views.QuestionVariableAssignView.as_view(), name="question_variables"),


]