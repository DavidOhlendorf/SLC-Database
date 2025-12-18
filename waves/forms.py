from django import forms
from django.forms import inlineformset_factory
from .models import Survey, Wave
import datetime


class WaveInlineForm(forms.ModelForm):
    class Meta:
        model = Wave
        fields = ["cycle", "instrument", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }



WaveFormSet = inlineformset_factory(
    Survey, Wave,
    form=WaveInlineForm,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)

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

        years = [("", "—")] + [
            (y, str(y)) for y in range(current_year-5, current_year+20, 1)
        ]

        self.fields["year"].choices = years

        if not self.instance.pk:
            self.initial["year"] = current_year