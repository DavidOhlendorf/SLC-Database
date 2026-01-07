# variables/forms.py

from django import forms
from .models import Variable

# Form for creating and updating Variable instances
class VariableForm(forms.ModelForm):
    class Meta:
        model = Variable
        fields = [
            "varname", "varlab", "comment",
            "ver", "reason_ver",
            "gen", "reason_gen",
            "plausi", "reason_plausi",
            "flag", "reason_flag",
        ]
        widgets = {
            "varname": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "varlab": forms.TextInput(attrs={"class": "form-control"}),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "ver": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "gen": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "plausi": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "flag": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "reason_ver": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "reason_gen": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "reason_plausi": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "reason_flag": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean_varname(self):
        varname = (self.cleaned_data.get("varname") or "").strip()
        if len(varname) < 2:
            raise forms.ValidationError("Der Variablenname muss mindestens 2 Zeichen haben.")

        qs = Variable.objects.filter(varname__iexact=varname)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("Dieser Variablenname ist bereits vergeben.")

        return varname
