from django import forms
from .models import Entry, Country

MODE_CHOICES = [
    ("ocean", "ocean"),
    ("air", "air"),
    ("truck", "truck"),
    ("rail", "rail"),
]

class EntryForm(forms.ModelForm):
    country_origin = forms.ModelChoiceField(
        queryset=Country.objects.all().order_by('name'),
        empty_label="Select a country...",
        widget=forms.Select(attrs={'class': 'form-select'}),
        to_field_name='code',
        label="Country origin"
    )
    
    class Meta:
        model = Entry
        fields = [
            "mode",
            "claimed_spi",
            "country_origin",  # Keep this in fields list
        ]
        widgets = {
            "mode": forms.Select(choices=MODE_CHOICES),
        }

    def clean_country_origin(self):
        v = self.cleaned_data.get("country_origin", "")
        return v.strip().upper()
