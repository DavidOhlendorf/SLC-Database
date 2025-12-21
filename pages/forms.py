from django import forms

from django.core.exceptions import ValidationError

from waves.models import Wave
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
    
# Form zum Bearbeiten einer bestehenden Fragebogenseite    
class WavePageForm(forms.ModelForm):
    class Meta:
        model = WavePage
        fields = [
            "pagename",
            "waves",
            "page_heading",
            "introduction",
            "transition_control",
            "transitions",
            "page_programming_notes",
        ]
        widgets = {
            "waves": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # pagename required
        self.fields["pagename"].required = True
        self.fields["pagename"].widget.attrs.update({
            "class": "form-control",
            "placeholder": " ",
        })
        self.fields["pagename"].error_messages.update({
            "required": "Bitte gib einen Seitennamen ein.",
        })

        # waves required
        self.fields["waves"].required = True
        self.fields["waves"].error_messages.update({
            "required": "Bitte wähle mindestens eine Befragtengruppe aus.",
        })

        # Zusatzfelder
        for fname in [
            "page_heading",
            "introduction",
            "transition_control",
            "transitions",
            "page_programming_notes",
        ]:
            self.fields[fname].widget.attrs.update({"class": "form-control"})

        # Survey der Page ableiten und Befragtengruppen darauf begrenzen ---
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
            # Fallback: Sollte praktisch nie vorkommen,
            # weil Pages immer mit mind. einer Wave erzeugt werden.
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
