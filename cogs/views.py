from django.http import HttpResponse, FileResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
import os
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .forms import InvoiceUploadForm, HSUSCodeForm, SKUForm, CostPoolForm
from .models import Invoice, InvoiceLine, SKU, Container, HSUSCode, CostPool, AllocatedCost
from .services import AllocationService
import csv
import io
import json
from datetime import datetime
from decimal import Decimal
import pandas as pd

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

    # Get all unique names of other custom cost pools for dynamic columns
    other_cost_pool_names = CostPool.objects.exclude(name__in=['Freight Cost', 'HSUS Tariff']).values_list('name', flat=True).distinct()

    # Prepare data for template
    results_data = []
    for line in lines:
        vendor_cost = line.price_vendor * line.quantity
        freight_cost = line.allocatedcost_set.filter(cost_pool__name='Freight Cost').first()
        freight_cost_amount = freight_cost.amount_allocated if freight_cost else 0
        hsus_tariff = line.allocatedcost_set.filter(cost_pool__name='HSUS Tariff').first()
        hsus_tariff_amount = hsus_tariff.amount_allocated if hsus_tariff else 0
        
        # Collect all other allocated costs for this line
        other_cost_allocations = {}
        current_line_other_costs_total = Decimal(0)
        for allocated_cost in line.allocatedcost_set.all():
            if allocated_cost.cost_pool.name not in ['Freight Cost', 'HSUS Tariff']:
                other_cost_allocations[allocated_cost.cost_pool.name] = allocated_cost.amount_allocated
                current_line_other_costs_total += allocated_cost.amount_allocated

        total_cost = vendor_cost + freight_cost_amount + hsus_tariff_amount + current_line_other_costs_total
        unit_total_cost = (total_cost / line.quantity).quantize(Decimal('0.01')) if line.quantity > 0 else Decimal(0)

        results_data.append({
            'line': line,
            'vendor_cost': vendor_cost,
            'freight_cost': freight_cost_amount,
            'hsus_tariff': hsus_tariff_amount,
            'other_cost_allocations': other_cost_allocations, # New: detailed other costs
            'total_cost': total_cost,
            'unit_total_cost': unit_total_cost,
        })

    # Get all freight costs for display
    freight_costs = CostPool.objects.filter(name='Freight Cost')
    total_freight_cost = sum(cost.amount_total for cost in freight_costs)

    # Get all other custom costs for display
    other_custom_costs = CostPool.objects.exclude(name__in=['Freight Cost', 'HSUS Tariff'])
    total_other_custom_costs = sum(cost.amount_total for cost in other_custom_costs)

    return render(request, 'results.html', {
        'results_data': results_data,
        'freight_costs': freight_costs,
        'total_freight_cost': total_freight_cost,
        'other_custom_costs': other_custom_costs, # Keep for the summary card
        'total_other_custom_costs': total_other_custom_costs, # Keep for the summary card
        'other_cost_pool_names': other_cost_pool_names, # New: for dynamic columns
    })

@login_required
def debug_base_dir(request):
    return HttpResponse(settings.BASE_DIR)

@login_required
def download_hsus_sku_template(request):
    file_path = os.path.join(settings.BASE_DIR, 'cogs', 'static', 'cogs', 'hsus_sku_template.csv')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='hsus_sku_template.csv')
    else:
        messages.error(request, 'Template file not found.')
        return redirect('home')

@login_required
@require_POST
def add_freight_cost(request):
    try:
        data = json.loads(request.body)
        total_freight_cost = float(data.get('total_freight_cost', 0))
        shipment_company = data.get('shipment_company', '')
        shipment_invoice = data.get('shipment_invoice', '')
        
        # Get invoice lines from database
        invoice_lines = InvoiceLine.objects.all().select_related('invoice', 'sku')
        
        if not invoice_lines.exists():
            return JsonResponse({'success': False, 'error': 'No invoice data found in database'})
        
        # Calculate total volume from database records
        total_volume = 0
        for line in invoice_lines:
            if line.unit_volume_cc:
                total_volume += float(line.unit_volume_cc) * line.quantity
        
        if total_volume == 0:
            return JsonResponse({'success': False, 'error': 'Total volume is zero. Please ensure invoice items have volume data.'})
        
        # Create or update freight cost pool with company and invoice info
        freight_pool, created = CostPool.objects.update_or_create(
            name='Freight Cost',
            defaults={
                'scope': CostPool.Scope.CONTAINER,
                'method': CostPool.Method.VOLUME,
                'amount_total': Decimal(str(total_freight_cost)),
                'shipment_company': shipment_company,
                'shipment_invoice': shipment_invoice,
                'auto_compute': False
            }
        )
        
        # Use AllocationService to distribute the cost
        service = AllocationService()
        service.allocate_cost(freight_pool)
        
        return JsonResponse({'success': True, 'message': f'Freight cost ${total_freight_cost} from {shipment_company or "Unknown"} distributed'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def delete_cost_pool(request, pk):
    cost_pool = get_object_or_404(CostPool, pk=pk)
    cost_pool.delete()
    messages.success(request, f'Removed {cost_pool.name}: ${cost_pool.amount_total}')
    
    # Recalculate remaining costs
    service = AllocationService()
    for pool in CostPool.objects.filter(auto_compute=False):
        service.allocate_cost(pool)
    
    return redirect('results')

@login_required
def hsus_bulk_upload(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        
        try:
            # Read file based on extension
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file)
            else:
                messages.error(request, 'Please upload a CSV or Excel file')
                return redirect('hsus_code_list')
            
            # Process each row
            created_count = 0
            updated_count = 0
            
            for _, row in df.iterrows():
                code = str(row.get('code', '')).strip()
                if not code:
                    continue
                    
                hsus, created = HSUSCode.objects.update_or_create(
                    code=code,
                    defaults={
                        'description': str(row.get('description', '')),
                        'rate_pct': float(row.get('rate_pct', 0))
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            
            messages.success(request, f'Successfully imported {created_count} new codes and updated {updated_count} existing codes')
            
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
        
        return redirect('hsus_code_list')
    
    return redirect('hsus_code_list')

@login_required
def download_hsus_template(request):
    """Download HSUS upload template"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="hsus_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['code', 'description', 'rate_pct'])
    writer.writerow(['6109.10.00', 'Example: T-shirts cotton', '16.5'])
    writer.writerow(['6203.42.40', 'Example: Mens trousers', '16.6'])
    writer.writerow(['', 'Add your codes below', ''])
    
    return response

@login_required
def export_hsus_codes(request):
    """Export all current HSUS codes"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="hsus_codes_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['code', 'description', 'rate_pct'])
    
    for hsus in HSUSCode.objects.all().order_by('code'):
        writer.writerow([hsus.code, hsus.description, hsus.rate_pct])
    
    return response

@login_required
@require_POST
def add_custom_cost(request):
    try:
        data = json.loads(request.body)
        cost_name = data.get('cost_name')
        cost_amount = float(data.get('cost_amount', 0))
        allocation_scope = data.get('allocation_scope')
        allocation_method = data.get('allocation_method')
        
        # Map the form values to model choices
        scope_map = {
            'container': CostPool.Scope.CONTAINER,
            'invoice': CostPool.Scope.INVOICE,
            'all': CostPool.Scope.ALL
        }
        
        method_map = {
            'volume': CostPool.Method.VOLUME,
            'price': CostPool.Method.PRICE,
            'quantity': CostPool.Method.QUANTITY,
            'weight': CostPool.Method.EQUALLY,  # Use EQUALLY for weight for now
            'price_quantity': CostPool.Method.PRICE_QUANTITY
        }
        
        # Create cost pool
        cost_pool = CostPool.objects.create(
            name=cost_name,
            scope=scope_map.get(allocation_scope, CostPool.Scope.ALL),
            method=method_map.get(allocation_method, CostPool.Method.PRICE),
            amount_total=Decimal(str(cost_amount)),
            auto_compute=False
        )
        
        # Allocate the cost
        service = AllocationService()
        service.allocate_cost(cost_pool)
        
        return JsonResponse({'success': True, 'message': f'{cost_name} cost of ${cost_amount} has been allocated'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})