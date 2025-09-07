from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
import os
from decimal import Decimal, InvalidOperation

from .forms import EntryForm
from .forms_upload import UploadForm
from .models import Entry, Country

def shipment_entry_view(request):
    if request.method == "POST":
        form = EntryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("tariff_upload")
        countries = Country.objects.all().order_by('name') # Added
        return render(request, "tariff/shipment_entry_form.html", {'countries': countries}) # Modified context
    countries = Country.objects.all().order_by('name') # Added
    
    return render(request, "tariff/shipment_entry_form.html", {'countries': countries}) # Modified context

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

            # Handle Section 301 rate
            rate_str = (request.POST.get('section_301_rate', '0') or '0').strip()
            try:
                rate = Decimal(rate_str)
            except InvalidOperation:
                rate = Decimal('0')

            if name and code:
                country, created = Country.objects.get_or_create(
                    name=name,
                    code=code,
                    defaults={'section_301_rate': rate}
                )
                messages.success(request, f'Country {name} added')

        elif 'update_country' in request.POST:
            country_id = request.POST.get('country_id')
            rate_str = (request.POST.get('section_301_rate', '0') or '0').strip()
            try:
                rate = Decimal(rate_str)
            except InvalidOperation:
                rate = Decimal('0')
            Country.objects.filter(id=country_id).update(section_301_rate=rate)
            messages.success(request, 'Country updated successfully')
            return redirect('tariff_countries')

        elif 'delete_country' in request.POST:
            country_id = request.POST.get('country_id')
            Country.objects.filter(id=country_id).delete()
            messages.success(request, 'Country deleted')
        
        return redirect('tariff_countries')
    
    countries = Country.objects.all()
    return render(request, 'tariff/countries.html', {'countries': countries})
