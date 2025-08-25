from django import forms
from .models import HSUSCode, SKU, CostPool

class InvoiceUploadForm(forms.Form):
    file = forms.FileField()

class HSUSCodeForm(forms.ModelForm):
    class Meta:
        model = HSUSCode
        fields = ['code', 'description', 'rate_pct']

class SKUForm(forms.ModelForm):
    class Meta:
        model = SKU
        fields = ['sku', 'name', 'hsus_code', 'hsus_rate_pct']

class CostPoolForm(forms.ModelForm):
    class Meta:
        model = CostPool
        fields = ['name', 'scope', 'method', 'amount_total', 'container', 'invoice']
