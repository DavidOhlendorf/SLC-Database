from django import forms
from django.forms import inlineformset_factory
from .models import Survey, Wave
import datetime


WaveFormSet = inlineformset_factory(
    Survey, Wave,
    fields=["cycle", "instrument", "start_date", "end_date"],
    extra=0,
    can_delete=False,
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