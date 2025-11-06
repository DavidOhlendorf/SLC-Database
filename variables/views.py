from django.views.generic import DetailView
from .models import Variable

class VariableDetail(DetailView):
    model = Variable
    template_name = "variables/detail.html"


