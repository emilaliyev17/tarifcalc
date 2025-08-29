from django.http import HttpResponse
from django.shortcuts import render, redirect
from .forms import EntryForm
from .models import Entry

from .forms import EntryForm
from .models import Entry

def shipment_entry_view(request):
    if request.method == "POST":
        form = EntryForm(request.POST)
        if form.is_valid():
            form.save()
            # redirect for both buttons
            return redirect("tariff_upload")
        return render(request, "tariff/shipment_entry_form.html", {"form": form})
    # initial values for convenience
    from django.utils.timezone import now
    form = EntryForm(initial={"import_date": now().date()})
    return render(request, "tariff/shipment_entry_form.html", {"form": form})

def upload_docs_view(request):
    if request.method == "POST":
        return redirect("tariff_match")
    return render(request, "tariff/upload_docs.html")

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