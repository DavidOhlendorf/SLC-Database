from django import forms
from django.forms import formset_factory, BaseFormSet

from django.core.exceptions import ValidationError

from waves.models import Wave
from questions.models import Question
from .models import WavePage

# Form zum Anlegen einer neuen Fragebogenseite mit Zuordnung zu Survey/Befragungsgruppen
class WavePageCreateForm(forms.Form):
    pagename = forms.CharField(
        max_length=200,
        required=True,
        label="Seitenname",
        help_text="Interner Seitenname (Zofar: pn), z.B. 'dem_123'. Muss innerhalb der Befragung eindeutig sein.",
    )

    waves = forms.ModelMultipleChoiceField(
        queryset=Wave.objects.none(),
        required=True,
        label="Welche Befragtengruppen sollen diese Seite sehen?",
        help_text="Mindestens eine Gruppe auswählen. Kann später noch angepasst werden.",
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, survey=None, **kwargs):
        """
        survey: Survey-Objekt, damit wir
        - waves korrekt einschränken
        - surveyweite Uniqueness prüfen können
        """
        super().__init__(*args, **kwargs)

        self.survey = survey

        if survey is not None:
            self.fields["waves"].queryset = (
                Wave.objects
                .filter(survey=survey)
                .order_by("cycle", "instrument", "id")
            )

        # Bootstrap: pagename als form-control
        self.fields["pagename"].widget.attrs.update({
            "class": "form-control",
            "placeholder": " ",
        })

        self.fields["pagename"].error_messages.update({
            "required": "Bitte gib einen Seitennamen ein.",
        })
        self.fields["waves"].error_messages.update({
            "required": "Bitte wähle mindestens eine Befragtengruppe aus.",
        })

    def clean_pagename(self):
        name = (self.cleaned_data.get("pagename") or "").strip()
        if not name:
            return name

        if self.survey is None:
            return name

        # Surveyweite Uniqueness:
        exists = (
            WavePage.objects
            .filter(waves__survey=self.survey, pagename__iexact=name)
            .distinct()
            .exists()
        )

        if exists:
            raise forms.ValidationError(
                "Dieser Seitenname wird in dieser Befragung bereits verwendet."
            )

        return name
    
# Form für die Basisdaten einer Fragebogenseite ---
class WavePageBaseForm(forms.ModelForm):

    class Meta:
        model = WavePage
        fields = ["pagename", "waves"]
        widgets = {
            "waves": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["pagename"].required = True
        self.fields["pagename"].widget.attrs.update({
            "class": "form-control",
            "placeholder": " ",
        })
        self.fields["pagename"].error_messages.update({
            "required": "Bitte gib einen Seitennamen ein.",
        })

        self.fields["waves"].required = True
        self.fields["waves"].error_messages.update({
            "required": "Bitte wähle mindestens eine Befragtengruppe aus.",
        })

        # Survey der Page ableiten und Befragtengruppen darauf begrenzen
        survey = None
        if self.instance and self.instance.pk:
            first_wave = self.instance.waves.select_related("survey").first()
            if first_wave:
                survey = first_wave.survey

        self._page_survey = survey

        if survey is not None:
            self.fields["waves"].queryset = (
                Wave.objects
                .filter(survey=survey)
                .order_by("cycle", "instrument", "id")
            )
        else:
            self.fields["waves"].queryset = Wave.objects.none()

    def clean(self):
        cleaned = super().clean()

        name = (cleaned.get("pagename") or "").strip()
        waves = cleaned.get("waves")

        if not name or not waves:
            return cleaned  # required-Fehler

        survey = getattr(self, "_page_survey", None)
        if survey is None:
            raise ValidationError(
                "Diese Seite ist keiner Befragung zugeordnet. Bitte wähle zuerst eine Befragtengruppe."
            )

        # Guardrail: nur Waves aus genau diesem Survey
        wrong = [w for w in waves if w.survey_id != survey.id]
        if wrong:
            raise ValidationError(
                "Bitte wähle nur Befragtengruppen aus dieser Befragung aus."
            )

        # Surveyweite Uniqueness
        exists = (
            WavePage.objects
            .filter(waves__survey_id=survey.id, pagename__iexact=name)
            .exclude(pk=self.instance.pk)
            .distinct()
            .exists()
        )
        if exists:
            self.add_error(
                "pagename",
                "Dieser Seitenname wird in dieser Befragung bereits verwendet."
            )

        return cleaned


# Form für die Inhaltsdaten einer Fragebogenseite ---
class WavePageContentForm(forms.ModelForm):

    class Meta:
        model = WavePage
        fields = [
            "page_heading",
            "introduction",
            "transition_control",
            "transitions",
            "visibility_conditions",
            "answer_validations",
            "correction_notes",
            "forcing_variables",
            "helper_variables",
            "control_variables",
            "formatting",
            "page_programming_notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Größe der Textfelder anpassen
        row_map = {
            "page_heading": 3,
            "introduction": 3,
            "transition_control": 3,
            "transitions": 5,
            "visibility_conditions": 3,
            "answer_validations": 3,
            "correction_notes": 3,
            "forcing_variables": 3,
            "helper_variables": 3,
            "control_variables": 3,
            "formatting": 3,
            "page_programming_notes": 3,
        }


        for fname, rows in row_map.items():
            self.fields[fname].widget.attrs.update({
                "class": "form-control",
                "rows": rows,
            })




# Formset zum Verknüpfen von Fragen mit der Seite und den Befragtengruppen
class PageQuestionLinkForm(forms.Form):

    question = forms.ModelChoiceField(
        queryset=Question.objects.none(),
        required=True,
        label="Frage",
        widget=forms.Select(attrs={"class": "form-select qc-passive"}),
        error_messages={"required": "Bitte wähle eine Frage aus."},
    )

    waves = forms.ModelMultipleChoiceField(
        queryset=Wave.objects.none(),
        required=True,
        label="Befragtengruppe(n)",
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        error_messages={
            "required": "Bitte wähle mindestens eine Befragtengruppe aus.",
            "invalid_choice": "Ungültige Auswahl."
        },
    )

    def __init__(self, *args, allowed_waves=None,  allowed_questions=None,**kwargs):
        """
        allowed_waves: QuerySet[Wave] – Befragtengruppen, die für diese Page auswählbar sind.
        """
        super().__init__(*args, **kwargs)

        if allowed_waves is not None:
            allowed_waves = allowed_waves
        else:
            allowed_waves = Wave.objects.none()

        self.fields["waves"].queryset = allowed_waves
        self._allowed_wave_ids = set(allowed_waves.values_list("id", flat=True))

        if allowed_questions is None:
            allowed_questions = Question.objects.none()

        self.fields["question"].queryset = allowed_questions.order_by("id")

    def clean(self):
        cleaned = super().clean()

        q = cleaned.get("question")
        ws = cleaned.get("waves") 

        # Leere Extra-Zeile erlauben
        # (Django-Formsets setzen empty_permitted; wir schützen aber zusätzlich vor "halb leer")
        if not q and (not ws or len(ws) == 0):
            return cleaned

        # Fall: Waves ausgewählt, aber keine Frage -> explizite Meldung
        if not q and ws and len(ws) > 0:
            raise ValidationError("Bitte wähle eine Frage aus, wenn du Befragtengruppen angibst.")

        # Fall: Frage ausgewählt, aber keine Waves -> kommt i.d.R. schon über required=True,
        # aber wir lassen es konsistent.
        if q and (not ws or len(ws) == 0):
            raise ValidationError("Bitte wähle mindestens eine Befragtengruppe für diese Frage aus.")

        # Defensive Prüfung: Waves müssen Teil der erlaubten Page-Waves sein
        # (falls jemand am POST rumspielt oder QuerySets mal nicht passen)
        bad = [w for w in ws if w.id not in self._allowed_wave_ids]
        if bad:
            raise ValidationError("Ungültige Befragtengruppe ausgewählt (nicht Teil der Seite).")

        return cleaned
    


class BasePageQuestionLinkFormSet(BaseFormSet):
    """
    Formset-weite Regeln:
    - gleiche Frage darf nicht mehrfach vorkommen (außer gelöschte Zeilen)
    """
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        seen = set()
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue

            q = form.cleaned_data.get("question")
            if not q:
                continue

            if q.pk in seen:
                raise ValidationError("Jede Frage darf nur einmal auf dieser Seite vorkommen.")
            seen.add(q.pk)


PageQuestionLinkFormSet = formset_factory(
    PageQuestionLinkForm,
    formset=BasePageQuestionLinkFormSet,
    extra=1,
    can_delete=True,
)

