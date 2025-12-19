from django import forms
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError
from .models import Survey, Wave
import datetime

class SurveyCreateForm(forms.ModelForm):
    year = forms.TypedChoiceField(
        coerce=int,
        required=False,
        choices=[],
        label="Jahr der Befragung",
    )

    class Meta:
        model = Survey
        fields = ["name", "year"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_year = datetime.date.today().year
        years = [("", "—")] + [(y, str(y)) for y in range(current_year-5, current_year+20)]
        self.fields["year"].choices = years
        if not self.instance.pk:
            self.initial["year"] = current_year

        # Bootstrap
        self.fields["name"].widget.attrs.update({
            "class": "form-control",
            "placeholder": " " 
        })
        self.fields["year"].widget.attrs.update({
            "class": "form-select",
        })

        self.fields["name"].error_messages.update({
            "unique": "Dieser Name existiert bereits.",
            "required": "Bitte gib einen Namen für die Befragung ein.",
})


class WaveInlineForm(forms.ModelForm):
    class Meta:
        model = Wave
        fields = ["cycle", "instrument", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["cycle"].widget.attrs.update({
            "class": "form-control",
            "placeholder": " ",  # floating label
        })

        self.fields["cycle"].error_messages.update({
            "required": "Bitte gib eine Befragtengruppe ein.",
        })

        self.fields["instrument"].widget.attrs.update({
            "class": "form-select",
        })

        self.fields["instrument"].error_messages.update({
            "required": "Bitte wähle einen Modus aus.",
        })

        self.fields["start_date"].widget.attrs.update({
            "class": "form-control",
        })
        self.fields["end_date"].widget.attrs.update({
            "class": "form-control",
        })

    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date:
            if end_date < start_date:
                self.add_error(
                    "end_date",
                    "Feldende darf nicht vor dem Feldstart liegen."
                )

        return cleaned_data

class WaveInlineFormSet(BaseInlineFormSet):

    def validate_unique(self):
        return

    def clean(self):
        super().clean()

        # Falls einzelne Forms fehlerhaft sind, vermeiden wir Folgefehler
        if any(self.errors):
            return

        # 1) Mindestens eine Gruppe muss übrig bleiben
        remaining = 0

        # 2) Doppelte Kombinationen aus cycle+instrument vermeiden
        seen = {}

        for form in self.forms:
            # gelöschte / leere extra-Forms überspringen
            if not form.cleaned_data:
                continue

            marked_for_delete = form.cleaned_data.get("DELETE", False)
            cycle = (form.cleaned_data.get("cycle") or "").strip()
            instrument = (form.cleaned_data.get("instrument") or "").strip()

            if not marked_for_delete:
                remaining += 1

                key = (cycle.casefold(), instrument.casefold())
                if cycle and instrument:
                    if key in seen:
                        msg = "Diese Kombination aus Befragtengruppe und Erhebungsmodus ist in diesem Survey bereits vorhanden."
                        form.add_error("cycle", msg)
                        seen[key].add_error("cycle", msg)
                    else:
                        seen[key] = form
                

            # 2) Wenn gelöscht werden soll: nur erlauben, wenn Wave löschbar ist
            # Nur relevant im Edit-Fall (bestehende Instanzen)
            if marked_for_delete and form.instance and form.instance.pk:
                if not form.instance.can_be_deleted:
                    form.add_error(
                        None,
                        form.instance.delete_block_reason or
                        "Diese Gruppe kann nicht gelöscht werden."
                    )

        if remaining < 1:
            raise ValidationError("Mindestens eine Gruppe ist erforderlich.")


WaveFormSet = inlineformset_factory(
    Survey, Wave,
    form=WaveInlineForm,
    formset=WaveInlineFormSet,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
