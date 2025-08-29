from django import forms
from .models import Entry

MODE_CHOICES = [
    ("ocean", "ocean"),
    ("air", "air"),
    ("truck", "truck"),
    ("rail", "rail"),
]

class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = [
            "mode",           # влияет на HMF (только ocean)
            "claimed_spi",    # может занулить тариф (напр., USMCA)
            "country_origin", # влияет на duty/ремедии
        ]
        widgets = {
            "mode": forms.Select(choices=MODE_CHOICES),
        }

    def clean_country_origin(self):
        v = self.cleaned_data.get("country_origin", "")
        return v.strip().upper()
