# questions/forms.py
from django import forms
from .models import Question, Keyword, Construct

class QuestionEditForm(forms.ModelForm):

    class Meta:
        model = Question
        fields = ["questiontext", "question_type", "instruction", "item_stem", "missing_values", "top_categories", "construct", "keywords" ]
        widgets = {
            "questiontext": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "question_type": forms.Select(attrs={"class": "form-select"}),
            "instruction": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "item_stem": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "missing_values": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "top_categories": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),

            "construct": forms.Select(attrs={"class": "form-select"}),
            "keywords": forms.SelectMultiple(attrs={"class": "form-select", "id": "id_keywords"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["questiontext"].required = True
        self.fields["questiontext"].error_messages.update({
            "required": "Bitte gib einen Fragetext ein.",
        })

        # Sort the construct and keyword querysets
        self.fields["construct"].queryset = Construct.objects.order_by("level_1", "level_2")
        self.fields["keywords"].queryset = Keyword.objects.order_by("name")


        # Validierung: muss alle Keywords kennen
        self.fields["keywords"].queryset = Keyword.objects.all()

        # Rendering: nur selected options ausgeben (verhindert lokale Suche ab 1 Zeichen)
        selected = []
        if self.instance and self.instance.pk:
            selected = list(self.instance.keywords.order_by("name").values_list("pk", "name"))

        self.fields["keywords"].choices = selected