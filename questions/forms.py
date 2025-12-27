# questions/forms.py
from django import forms
from django.forms import formset_factory, BaseFormSet

from .models import Question, Keyword, Construct



# Formular zur Bearbeitung von Fragen
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


# Formular für einzelne Antwortoptionen
class AnswerOptionForm(forms.Form):
    uid = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    )
    variable = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    )
    value = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    )
    label = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    )

# Formset für Antwortoptionen mit Validierung
class BaseAnswerOptionFormSet(BaseFormSet):
    """
    Validierung:
    - komplett leere Zeilen ignorieren
    - wenn Zeile nicht leer: uid + label Pflicht
    - uid muss innerhalb des Formsets eindeutig sein
    """
    def clean(self):
        super().clean()

        seen_uids = set()

        for form in self.forms:
            # wenn das einzelne Form schon field errors hat, kann cleaned_data fehlen
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            uid = (form.cleaned_data.get("uid") or "").strip()
            variable = (form.cleaned_data.get("variable") or "").strip()
            value = (form.cleaned_data.get("value") or "").strip()
            label = (form.cleaned_data.get("label") or "").strip()

            # komplett leere Zeile → ignorieren
            if not uid and not variable and not value and not label:
                continue

            # Pflichtfelder (nur wenn Zeile nicht leer)
            if not uid:
                form.add_error("uid", "UID ist ein Pflichtfeld.")
            if not label:
                form.add_error("label", "Label ist ein Pflichtfeld.")

            # UID-Duplizierung prüfen (nur wenn uid vorhanden)
            if uid:
                key = uid.lower()  # case-insensitive Duplikate verhindern
                if key in seen_uids:
                    form.add_error("uid", "Diese UID kommt mehrfach vor.")
                else:
                    seen_uids.add(key)


AnswerOptionFormSet = formset_factory(
    AnswerOptionForm,
    formset=BaseAnswerOptionFormSet,
    can_delete=True,
    extra=0,
)