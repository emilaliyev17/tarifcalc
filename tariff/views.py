from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
import os

from .forms import EntryForm
from .forms_upload import UploadForm
from .models import Entry, Country

def shipment_entry_view(request):
    if request.method == "POST":
        form = EntryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("tariff_upload")
        return render(request, "tariff/shipment_entry_form.html", {"form": form})
    form = EntryForm()
    return render(request, "tariff/shipment_entry_form.html", {"form": form})

def upload_docs_view(request):
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            import os
            from django.conf import settings
            base = getattr(settings, 'MEDIA_ROOT', 'media')
            tmp = os.path.join(base, 'tmp')
            os.makedirs(tmp, exist_ok=True)
            for field in ("cbp_7501_pdf","commercial_invoice","sku_hts_map"):
                f = form.cleaned_data.get(field)
                if f:
                    dest = os.path.join(tmp, f.name)
                    with open(dest, 'wb') as out:
                        for chunk in f.chunks():
                            out.write(chunk)
            return redirect("tariff_match")
        return render(request, "tariff/upload_docs.html", {"form": form})
    form = UploadForm()
    return render(request, "tariff/upload_docs.html", {"form": form})

def match_sku_hts_view(request):
    return render(request, "tariff/match_sku_hts.html", {
        "invoice_lines": [],
        "entry_lines": [],
        "mappings": [],
        "totals": {"invoice": 0, "entry": 0, "matched": 0}
    })

def calculate_duties_view(request, entry_id: int):
    return HttpResponse("Calculation result placeholder")

def download_invoice_template(request):
    csv = "invoice_no,sku,description,qty,uom,unit_price,line_total,country_origin"
    return HttpResponse(csv, content_type="text/csv")

def download_sku_hts_template(request):
    csv = "sku,hts_code,origin_country,effective_from,effective_to,claimed_spi,rate_override_pct,override_reason"
    return HttpResponse(csv, content_type="text/csv")
from django.shortcuts import render
def countries_view(request):
    if request.method == 'POST':
        if 'add_country' in request.POST:
            name = request.POST.get('name')
            code = request.POST.get('code', '').upper()
            if name and code:
                Country.objects.get_or_create(name=name, code=code)
                messages.success(request, f'Country {name} added')
        
        elif 'delete_country' in request.POST:
            country_id = request.POST.get('country_id')
            Country.objects.filter(id=country_id).delete()
            messages.success(request, 'Country deleted')
        
        return redirect('tariff_countries')
    
    countries = Country.objects.all()
    return render(request, 'tariff/countries.html', {'countries': countries})
