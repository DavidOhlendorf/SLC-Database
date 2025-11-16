from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import loginpage

urlpatterns = [
    path("logout/", LogoutView.as_view(), name="logout"),
]