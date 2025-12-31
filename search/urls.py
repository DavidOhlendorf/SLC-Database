from django.urls import path
from . import views

app_name = "search"

urlpatterns = [
    path("", views.search_landing, name="search_landing"),
    path("search/", views.search, name="search"),

    # API-Endpunkt für kleinen Frage-Picker (Verwendung im Page-Editor)
    path("api/questions/", views.search_questions_api, name="search_questions_api")

]