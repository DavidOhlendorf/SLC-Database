from django import forms

from waves.models import Wave
from .models import WavePage

# Form zum Anlegen einer neuen Fragebogenseite mit Zuordnung zu Survey/Befragungsgruppen
class WavePageCreateForm(forms.Form):
    pagename = forms.CharField(
        max_length=200,
        required=True,
        label="Seitenname (pn)",
        help_text="Interner Seitenname, z.B. 'dem123'. Muss innerhalb der Befragung eindeutig sein.",
    )

    waves = forms.ModelMultipleChoiceField(
        queryset=Wave.objects.none(),
        required=True,
        label="Befragtengruppen",
        help_text="Mindestens eine Gruppe auswählen.",
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

        # Checkbox-Liste der Befragtengruppen
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
