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
            "entry_number",
            "entry_date",
            "import_date",
            "mode",
            "port_of_entry",
            "claimed_spi",
            "country_origin",
            "country_export",
            "notes",
        ]
        widgets = {
            "entry_date": forms.DateInput(attrs={"type": "date"}),
            "import_date": forms.DateInput(attrs={"type": "date"}),
            "mode": forms.Select(choices=MODE_CHOICES),
        }

    def clean_country_origin(self):
        v = self.cleaned_data.get("country_origin", "")
        return v.strip().upper()

    def clean_country_export(self):
        v = self.cleaned_data.get("country_export", "")
        return v.strip().upper()