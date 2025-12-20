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
            "placeholder": " ", 
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
    
    # Unique-Validierung hier unterdrücken, da wir das im Formset machen
    def validate_unique(self):
        return


class WaveInlineFormSet(BaseInlineFormSet):

    def clean(self):
        super().clean()

        # Falls einzelne Forms fehlerhaft sind, vermeiden wir Folgefehler
        if any(self.errors):
            return

        remaining = 0
        seen = set()
        duplicate_found = False

        for form in self.forms:
            if not getattr(form, "cleaned_data", None):
                continue

            marked_for_delete = form.cleaned_data.get("DELETE", False)
            cycle = (form.cleaned_data.get("cycle") or "").strip()
            instrument = (form.cleaned_data.get("instrument") or "").strip()

            if not marked_for_delete:
                if cycle:
                    remaining += 1

                # Duplikate prüfen (wenn beides gesetzt)
                if cycle and instrument:
                    key = (cycle.casefold(), instrument.casefold())
                    if key in seen:
                        duplicate_found = True
                    else:
                        seen.add(key)

            if marked_for_delete and form.instance and form.instance.pk:
                if not form.instance.can_be_deleted:
                    msg = (
                        form.instance.delete_block_reason
                        or "Diese Gruppe kann nicht gelöscht werden."
                    )
                    form.add_error(None, msg)
                    raise ValidationError(msg)

        if duplicate_found:
            raise ValidationError(
                "Diese Kombination aus Befragtengruppe und Erhebungsmodus ist in diesem Survey bereits vorhanden."
            )

        if remaining < 1:
            raise ValidationError("Mindestens eine Gruppe ist erforderlich.")

    # Unique-Validierung-Message von Django hier unterdrücken, da wir eigene ausgeben
    def validate_unique(self):
        return



WaveFormSet = inlineformset_factory(
    Survey, Wave,
    form=WaveInlineForm,
    formset=WaveInlineFormSet,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
