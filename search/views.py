from django.shortcuts import render
from questions.models import Question

def search(request):
    questions = Question.objects.all().prefetch_related('waves') 
    ctx = {"questions": questions}
    return render(request, 'search/search.html', ctx)
