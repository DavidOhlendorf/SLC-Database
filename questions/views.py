from django.views.generic import DetailView
from .models import Question

class QuestionDetail(DetailView):
    model = Question
    template_name = "questions/detail.html"
