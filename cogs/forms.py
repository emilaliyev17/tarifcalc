from django import forms
from .models import HTSUSCode, SKU, CostPool
from tariff.models import Country

class InvoiceUploadForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={"class": "form-control"}))
    country_origin = forms.ChoiceField(
        required=False,
        choices=[],
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Country of Origin"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [('', 'Select country (optional)')] + list(Country.objects.values_list('code', 'name'))
        self.fields['country_origin'].choices = choices

class HTSUSCodeForm(forms.ModelForm):
    class Meta:
        model = HTSUSCode
        fields = ['code', 'description', 'rate_pct']

class SKUForm(forms.ModelForm):
    class Meta:
        model = SKU
        fields = ['sku', 'name', 'htsus_code', 'htsus_rate_pct']

class CostPoolForm(forms.ModelForm):
    class Meta:
        model = CostPool
        fields = ['name', 'scope', 'method', 'amount_total', 'container', 'invoice']
