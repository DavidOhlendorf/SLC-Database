from django.shortcuts import render, redirect
from questions.models import Question

def search_landing(request):
    q = request.GET.get("q")
    if q:
        return redirect("search")
    return render(request, "search/landing.html")

def search(request):
    questions = Question.objects.all().prefetch_related('waves') 
    ctx = {"questions": questions}
    return render(request, 'search/search.html', ctx)
