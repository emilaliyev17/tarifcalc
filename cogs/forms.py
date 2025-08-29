from django import forms
from .models import HTSUSCode, SKU, CostPool

class InvoiceUploadForm(forms.Form):
    file = forms.FileField()

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
