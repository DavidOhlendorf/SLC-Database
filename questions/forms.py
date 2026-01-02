# questions/forms.py
from django import forms
from django.forms import formset_factory, BaseFormSet

from .models import Question, Keyword, Construct
from pages.models import WavePage
from waves.models import Wave
from variables.models import Variable


# Formular zur Bearbeitung von Fragen
class QuestionEditForm(forms.ModelForm):

    class Meta:
        model = Question
        fields = ["questiontext", "question_type", "question_type_other", "instruction", "item_stem", "missing_values", "top_categories", "construct", "keywords" ]
        widgets = {
            "questiontext": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "question_type": forms.Select(attrs={"class": "form-select"}),
            "question_type_other": forms.TextInput(attrs={"class": "form-control"}),
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


        # Rendering: nur selected options ausgeben (verhindert lokale Suche ab 1 Zeichen)
        selected = []
        if self.instance and self.instance.pk:
            selected = list(self.instance.keywords.order_by("name").values_list("pk", "name"))

        self.fields["keywords"].choices = selected


    def clean(self):
        cleaned = super().clean()

        qt = cleaned.get("question_type")
        other = (cleaned.get("question_type_other") or "").strip()

        # Validierung: wenn OTHER, dann muss question_type_other ausgefüllt sein
        if qt == Question.QuestionType.OTHER and not other:
            self.add_error("question_type_other", "Bitte gib einen sonstigen Fragetyp an.")

        # Feld leeren, wenn nicht OTHER
        if qt != Question.QuestionType.OTHER:
            cleaned["question_type_other"] = ""

        return cleaned


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


# Formular für einzelne Items
class ItemForm(forms.Form):
    uid = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    )
    variable = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    )
    label = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    )


class BaseItemFormSet(BaseFormSet):
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
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            uid = (form.cleaned_data.get("uid") or "").strip()
            variable = (form.cleaned_data.get("variable") or "").strip()
            label = (form.cleaned_data.get("label") or "").strip()

            if not uid and not variable and not label:
                continue

            if not uid:
                form.add_error("uid", "UID ist ein Pflichtfeld.")
            if not label:
                form.add_error("label", "Label ist ein Pflichtfeld.")

            if uid:
                key = uid.lower()
                if key in seen_uids:
                    form.add_error("uid", "Diese UID kommt mehrfach vor.")
                else:
                    seen_uids.add(key)


ItemFormSet = formset_factory(
    ItemForm,
    formset=BaseItemFormSet,
    can_delete=True,
    extra=0,
)

# Formular zum Anhängen einer Frage an eine Seite
class AttachWavePageForm(forms.Form):
    wave = forms.ModelChoiceField(
        label="Befragung",
        queryset=Wave.objects.filter(is_locked=False).order_by("cycle", "instrument", "id"),
        widget=forms.Select(attrs={"class": "form-select", "onchange": "this.form.submit();"}),
        empty_label="Bitte auswählen …",
        required=True,
    )

    wave_page = forms.ModelChoiceField(
        label="Seite",
        queryset=WavePage.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="Bitte zuerst eine Befragung wählen …",
        required=True,
    )

    def __init__(self, *args, **kwargs):
        selected_wave = kwargs.pop("selected_wave", None)
        super().__init__(*args, **kwargs)

        if selected_wave:
            # Seiten der ausgewählten Gruppe, aber harte Sperre: sobald Page irgendwo locked ist → raus
            self.fields["wave_page"].queryset = (
                WavePage.objects
                .filter(waves=selected_wave)
                .exclude(waves__is_locked=True)
                .order_by("pagename")
                .distinct()
            )

# Formular für einzelne Variable-Verknüpfungen
class QuestionVariableLinkForm(forms.Form):
    variable = forms.ModelChoiceField(
        queryset=Variable.objects.all().order_by("varname"),
        required=True,
        label="Variable",
        widget=forms.Select(attrs={"class": "form-select"}),
        error_messages={"required": "Bitte wähle eine Variable aus."},
    )

    waves = forms.ModelMultipleChoiceField(
        queryset=Wave.objects.none(),
        required=False,
        label="Befragungen",
        widget=forms.CheckboxSelectMultiple,
    )

    DELETE = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        allowed_waves = kwargs.pop("allowed_waves", Wave.objects.none())
        super().__init__(*args, **kwargs)

        allowed_waves = allowed_waves.order_by("cycle", "instrument", "id")
        self.fields["waves"].queryset = allowed_waves

        self.fields["waves"].widget.attrs.update({"class": "d-flex flex-wrap gap-2"})


QuestionVariableLinkFormSet = formset_factory(
    QuestionVariableLinkForm,
    extra=1,
    can_delete=True,
)