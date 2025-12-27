# questions/forms.py
from django import forms
from .models import Question

class QuestionEditForm(forms.ModelForm):

    class Meta:
        model = Question
        fields = ["questiontext", "question_type", "instruction", "item_stem", "missing_values", "top_categories"]
        widgets = {
            "questiontext": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "question_type": forms.Select(attrs={"class": "form-select"}),
            "instruction": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "item_stem": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "missing_values": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "top_categories": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["questiontext"].required = True
        self.fields["questiontext"].error_messages.update({
            "required": "Bitte gib einen Fragetext ein.",
        })
