from django import forms

class UploadForm(forms.Form):
    cbp_7501_pdf = forms.FileField(required=False)
    commercial_invoice = forms.FileField(required=False)
    sku_hts_map = forms.FileField(required=False)
