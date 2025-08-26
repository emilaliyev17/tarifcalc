from django.http import HttpResponse, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
import os
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import InvoiceUploadForm, HSUSCodeForm, SKUForm, CostPoolForm
from .models import Invoice, InvoiceLine, SKU, Container, HSUSCode, CostPool, AllocatedCost
from .services import AllocationService
import csv
import io
from datetime import datetime
from decimal import Decimal

@login_required
def home(request):
    return render(request, 'home.html')

@login_required
def invoice_upload(request):
    if request.method == 'POST':
        form = InvoiceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'This is not a CSV file')
                return redirect('invoice_upload')

            try:
                decoded_file = csv_file.read().decode('utf-8')
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)

                for row in reader:
                    # Normalize date format
                    invoice_date_str = row.get('Invoice date')
                    invoice_date = None
                    for fmt in ('%Y-%m-%d', '%m/%d/%y', '%d.%m.%Y'):
                        try:
                            invoice_date = datetime.strptime(invoice_date_str, fmt).date()
                            break
                        except (ValueError, TypeError):
                            continue
                    if not invoice_date:
                        raise ValueError(f"Date format for {invoice_date_str} not supported")

                    container, _ = Container.objects.get_or_create(container_id=row.get('Container ID'))
                    sku, _ = SKU.objects.get_or_create(sku=row.get('SKU'))

                    invoice, _ = Invoice.objects.get_or_create(
                        invoice_number=row.get('Invoice#'),
                        defaults={
                            'invoice_date': invoice_date,
                            'container': container,
                            'po_number': row.get('PO#'),
                        }
                    )

                    InvoiceLine.objects.create(
                        invoice=invoice,
                        sku=sku,
                        quantity=int(row.get('Quantity')),
                        price_vendor=Decimal(row.get('Price')),
                        total_vendor=Decimal(row.get('Total')),
                        unit_volume_cc=float(row.get('Volume'))
                    )

                messages.success(request, 'Invoice uploaded successfully')
                return redirect('home')

            except Exception as e:
                messages.error(request, f'Error processing file: {e}')
                return redirect('invoice_upload')
    else:
        form = InvoiceUploadForm()
    return render(request, 'invoice_upload.html', {'form': form})

@login_required
def sku_list(request):
    skus = SKU.objects.all()
    query = request.GET.get('query')
    if query:
        skus = skus.filter(sku__icontains=query)
    return render(request, 'sku_list.html', {'skus': skus})

@login_required
def sku_edit(request, pk):
    sku = get_object_or_404(SKU, pk=pk)
    if request.method == 'POST':
        form = SKUForm(request.POST, instance=sku)
        if form.is_valid():
            form.save()
            messages.success(request, 'SKU updated successfully')
            return redirect('sku_list')
    else:
        form = SKUForm(instance=sku)
    return render(request, 'sku_edit.html', {'form': form, 'sku': sku})

@login_required
def sku_upload(request):
    if request.method == 'POST':
        csv_file = request.FILES['file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'This is not a CSV file')
            return redirect('sku_list')

        try:
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            for row in reader:
                sku_val = row.get('sku')
                if not sku_val:
                    continue

                sku, created = SKU.objects.get_or_create(sku=sku_val)
                sku.name = row.get('name', sku.name)
                
                hsus_code_str = row.get('hsus_code')
                if hsus_code_str:
                    try:
                        hsus_code = HSUSCode.objects.get(code=hsus_code_str)
                        sku.hsus_code = hsus_code
                    except HSUSCode.DoesNotExist:
                        messages.warning(request, f"HSUS code {hsus_code_str} not found for SKU {sku_val}. Please create it first.")

                rate_override = row.get('hsus_rate_pct')
                if rate_override:
                    sku.hsus_rate_pct = Decimal(rate_override)
                
                sku.save()

            messages.success(request, 'SKUs uploaded successfully')

        except Exception as e:
            messages.error(request, f'Error processing file: {e}')
        
        return redirect('sku_list')
    return redirect('sku_list')

@login_required
def sku_download(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="skus.csv"'

    writer = csv.writer(response)
    writer.writerow(['sku', 'name', 'hsus_code', 'hsus_rate_pct'])

    for sku in SKU.objects.all():
        writer.writerow([
            sku.sku,
            sku.name,
            sku.hsus_code.code if sku.hsus_code else '',
            sku.hsus_rate_pct if sku.hsus_rate_pct is not None else ''
        ])

    return response

@login_required
def hsus_code_list(request):
    if request.method == 'POST':
        form = HSUSCodeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'HSUS code added successfully')
            return redirect('hsus_code_list')
    else:
        form = HSUSCodeForm()
    
    codes = HSUSCode.objects.all()
    return render(request, 'hsus_code_list.html', {'form': form, 'codes': codes})

@login_required
def hsus_code_delete(request, pk):
    code = get_object_or_404(HSUSCode, pk=pk)
    code.delete()
    messages.success(request, 'HSUS code deleted successfully')
    return redirect('hsus_code_list')

@login_required
def add_cost_pool(request):
    if request.method == 'POST':
        form = CostPoolForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cost pool added successfully')
            return redirect('results')
    else:
        form = CostPoolForm()
    return render(request, 'add_cost_pool.html', {'form': form})

@login_required
def recalculate_costs(request):
    service = AllocationService()
    for cost_pool in CostPool.objects.filter(auto_compute=False):
        service.allocate_cost(cost_pool)
    for invoice in Invoice.objects.all():
        service.compute_hsus_for_invoice(invoice)
    messages.success(request, 'Costs recalculated successfully')
    return redirect('results')

@login_required
def toggle_hsus(request, invoice_pk):
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    hsus_pool = CostPool.objects.filter(invoice=invoice, name="HSUS Tariff").first()
    if hsus_pool:
        hsus_pool.delete()
        messages.success(request, 'HSUS tariff disabled for this invoice')
    else:
        service = AllocationService()
        service.compute_hsus_for_invoice(invoice)
        messages.success(request, 'HSUS tariff enabled for this invoice')
    return redirect('results')

@login_required
def results(request):
    lines = InvoiceLine.objects.all().select_related('invoice', 'sku').prefetch_related('allocatedcost_set__cost_pool')
    
    # Filtering logic here
    container_filter = request.GET.get('container')
    invoice_filter = request.GET.get('invoice')
    date_filter = request.GET.get('date')

    if container_filter:
        lines = lines.filter(invoice__container__container_id=container_filter)
    if invoice_filter:
        lines = lines.filter(invoice__invoice_number=invoice_filter)
    if date_filter:
        lines = lines.filter(invoice__invoice_date=date_filter)

    # Prepare data for template
    results_data = []
    for line in lines:
        vendor_cost = line.price_vendor * line.quantity
        freight_cost = line.allocatedcost_set.filter(cost_pool__name__iexact='freight cost').first()
        freight_cost_amount = freight_cost.amount_allocated if freight_cost else 0
        hsus_tariff = line.allocatedcost_set.filter(cost_pool__name='HSUS Tariff').first()
        hsus_tariff_amount = hsus_tariff.amount_allocated if hsus_tariff else 0
        
        other_costs = line.allocatedcost_set.exclude(cost_pool__name__in=['Freight cost', 'HSUS Tariff'])
        other_costs_total = sum(c.amount_allocated for c in other_costs)

        total_cost = vendor_cost + freight_cost_amount + hsus_tariff_amount + other_costs_total
        unit_total_cost = (total_cost / line.quantity).quantize(Decimal('0.01')) if line.quantity > 0 else Decimal(0)

        results_data.append({
            'line': line,
            'vendor_cost': vendor_cost,
            'freight_cost': freight_cost_amount,
            'hsus_tariff': hsus_tariff_amount,
            'other_costs': other_costs,
            'total_cost': total_cost,
            'unit_total_cost': unit_total_cost,
        })

    return render(request, 'results.html', {'results_data': results_data})

@login_required
def download_hsus_sku_template(request):
    file_path = os.path.join(settings.BASE_DIR, 'cogs', 'static', 'cogs', 'hsus_sku_template.csv')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='hsus_sku_template.csv')
    else:
        messages.error(request, 'Template file not found.')
        return redirect('home') # Or a more appropriate redirect
