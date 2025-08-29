from django import forms
from .models import Entry

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
