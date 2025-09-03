from django.http import HttpResponse, FileResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
import os
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .forms import InvoiceUploadForm, HTSUSCodeForm, SKUForm, CostPoolForm
from .models import Invoice, InvoiceLine, SKU, Container, HTSUSCode, CostPool, AllocatedCost
from .services import AllocationService
import csv
import io
import json
from datetime import datetime
from decimal import Decimal
import pandas as pd


def home(request):
    return render(request, 'home.html')

@login_required
def clear_invoice_data(request):
    """Clear only uploaded invoice data, keep SKU and HTS reference data"""
    from cogs.models import Invoice, InvoiceLine, Container, CostPool, AllocatedCost
    # Delete in correct order due to foreign keys
    AllocatedCost.objects.all().delete()
    CostPool.objects.all().delete()
    InvoiceLine.objects.all().delete()
    Invoice.objects.all().delete()
    Container.objects.all().delete()
    messages.success(request, 'All invoice data cleared successfully')
    return redirect('results')

@login_required
def clear_all_data(request):
    """Clear all invoice data"""
    from cogs.models import Invoice, InvoiceLine, Container, CostPool, AllocatedCost
    # Delete all invoice-related data in correct order
    AllocatedCost.objects.all().delete()
    CostPool.objects.all().delete()
    InvoiceLine.objects.all().delete()
    Invoice.objects.all().delete()
    Container.objects.all().delete()
    messages.success(request, 'All data cleared successfully')
    return redirect('home')


def invoice_upload(request):
    if request.method == 'POST':
        form = InvoiceUploadForm(request.POST, request.FILES)
        # Ensure variable is always defined to avoid NameError
        country_origin = None
        if form.is_valid():
            csv_file = request.FILES['file']
            country_origin = form.cleaned_data.get('country_origin') or None
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
                            'country_origin': country_origin,
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


def sku_list(request):
    skus = SKU.objects.all()
    query = request.GET.get('query')
    if query:
        skus = skus.filter(sku__icontains=query)
    return render(request, 'sku_list.html', {'skus': skus})


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
                
                htsus_code_str = row.get('htsus_code')
                if htsus_code_str:
                    try:
                        htsus_code = HTSUSCode.objects.get(code=htsus_code_str)
                        sku.htsus_code = htsus_code
                    except HTSUSCode.DoesNotExist:
                        messages.warning(request, f"HTSUS code {htsus_code_str} not found for SKU {sku_val}. Please create it first.")

                rate_override = row.get('htsus_rate_pct')
                if rate_override:
                    sku.htsus_rate_pct = Decimal(rate_override)
                
                sku.save()

            messages.success(request, 'SKUs uploaded successfully')

        except Exception as e:
            messages.error(request, f'Error processing file: {e}')
        
        return redirect('sku_list')
    return redirect('sku_list')


def sku_download(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="skus.csv"'

    writer = csv.writer(response)
    writer.writerow(['sku', 'name', 'htsus_code', 'htsus_rate_pct'])

    for sku in SKU.objects.all():
        writer.writerow([
            sku.sku,
            sku.name,
            sku.htsus_code.code if sku.htsus_code else '',
            sku.htsus_rate_pct if sku.htsus_rate_pct is not None else ''
        ])

    return response


def htsus_code_list(request):
    if request.method == 'POST':
        form = HTSUSCodeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'HTSUS code added successfully')
            return redirect('htsus_code_list')
    else:
        form = HTSUSCodeForm()
    
    codes = HTSUSCode.objects.all()
    return render(request, 'htsus_code_list.html', {'form': form, 'codes': codes})


def htsus_code_delete(request, pk):
    code = get_object_or_404(HTSUSCode, pk=pk)
    code.delete()
    messages.success(request, 'HTSUS code deleted successfully')
    return redirect('htsus_code_list')


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


def recalculate_costs(request):
    service = AllocationService()
    for cost_pool in CostPool.objects.filter(auto_compute=False):
        service.allocate_cost(cost_pool)
    for invoice in Invoice.objects.all():
        service.compute_htsus_for_invoice(invoice)
    messages.success(request, 'Costs recalculated successfully')
    return redirect('results')


def toggle_htsus(request, invoice_pk):
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    htsus_pool = CostPool.objects.filter(invoice=invoice, name="HTSUS Tariff").first()
    if htsus_pool:
        htsus_pool.delete()
        messages.success(request, 'HTSUS tariff disabled for this invoice')
    else:
        service = AllocationService()
        service.compute_htsus_for_invoice(invoice)
        messages.success(request, 'HTSUS tariff enabled for this invoice')
    return redirect('results')


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
    other_cost_pool_names = CostPool.objects.exclude(name__in=['Freight Cost', 'HTSUS Tariff']).values_list('name', flat=True).distinct()

    # Prepare data for template
    results_data = []
    for line in lines:
        vendor_cost = line.price_vendor * line.quantity
        freight_cost = line.allocatedcost_set.filter(cost_pool__name='Freight Cost').first()
        freight_cost_amount = freight_cost.amount_allocated if freight_cost else 0
        htsus_tariff = line.allocatedcost_set.filter(cost_pool__name='HTSUS Tariff').first()
        htsus_tariff_amount = htsus_tariff.amount_allocated if htsus_tariff else 0
        
        # Collect all other allocated costs for this line
        other_cost_allocations = {}
        current_line_other_costs_total = Decimal(0)
        for allocated_cost in line.allocatedcost_set.all():
            if allocated_cost.cost_pool.name not in ['Freight Cost', 'HTSUS Tariff']:
                other_cost_allocations[allocated_cost.cost_pool.name] = allocated_cost.amount_allocated
                current_line_other_costs_total += allocated_cost.amount_allocated

        total_cost = vendor_cost + freight_cost_amount + htsus_tariff_amount + current_line_other_costs_total
        unit_total_cost = (total_cost / line.quantity).quantize(Decimal('0.01')) if line.quantity > 0 else Decimal(0)

        results_data.append({
            'line': line,
            'vendor_cost': vendor_cost,
            'freight_cost': freight_cost_amount,
            'htsus_tariff': htsus_tariff_amount,
            'other_cost_allocations': other_cost_allocations, # New: detailed other costs
            'total_cost': total_cost,
            'unit_total_cost': unit_total_cost,
        })

    # Get all freight costs for display
    freight_costs = CostPool.objects.filter(name='Freight Cost')
    total_freight_cost = sum(cost.amount_total for cost in freight_costs)

    # Get all other custom costs for display
    other_custom_costs = CostPool.objects.exclude(name__in=['Freight Cost', 'HTSUS Tariff'])
    total_other_custom_costs = sum(cost.amount_total for cost in other_custom_costs)

    return render(request, 'results.html', {
        'results_data': results_data,
        'freight_costs': freight_costs,
        'total_freight_cost': total_freight_cost,
        'other_custom_costs': other_custom_costs, # Keep for the summary card
        'total_other_custom_costs': total_other_custom_costs, # Keep for the summary card
        'other_cost_pool_names': other_cost_pool_names, # New: for dynamic columns
    })


def debug_base_dir(request):
    return HttpResponse(settings.BASE_DIR)


def download_htsus_sku_template(request):
    file_path = os.path.join(settings.BASE_DIR, 'cogs', 'static', 'cogs', 'htsus_sku_template.csv')
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='htsus_sku_template.csv')
    else:
        messages.error(request, 'Template file not found.')
        return redirect('home')


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


def delete_cost_pool(request, pk):
    cost_pool = get_object_or_404(CostPool, pk=pk)
    cost_pool.delete()
    messages.success(request, f'Removed {cost_pool.name}: ${cost_pool.amount_total}')
    
    # Recalculate remaining costs
    service = AllocationService()
    for pool in CostPool.objects.filter(auto_compute=False):
        service.allocate_cost(pool)
    
    return redirect('results')


def htsus_bulk_upload(request):
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
                return redirect('htsus_code_list')
            
            # Process each row
            created_count = 0
            updated_count = 0
            
            for _, row in df.iterrows():
                code = str(row.get('code', '')).strip()
                if not code:
                    continue
                    
                htsus, created = HTSUSCode.objects.update_or_create(
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
        
        return redirect('htsus_code_list')
    
    return redirect('htsus_code_list')


def download_htsus_template(request):
    """Download HTSUS upload template"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="htsus_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['code', 'description', 'rate_pct'])
    writer.writerow(['6109.10.00', 'Example: T-shirts cotton', '16.5'])
    writer.writerow(['6203.42.40', 'Example: Mens trousers', '16.6'])
    writer.writerow(['', 'Add your codes below', ''])
    
    return response


def export_htsus_codes(request):
    """Export all current HTSUS codes"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="htsus_codes_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['code', 'description', 'rate_pct'])
    
    for htsus in HTSUSCode.objects.all().order_by('code'):
        writer.writerow([htsus.code, htsus.description, htsus.rate_pct])
    
    return response


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

@login_required
def download_results_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="results_export.csv"'
    writer = csv.writer(response)

    # Get all unique names of other custom cost pools for dynamic columns
    other_cost_pool_names = list(CostPool.objects.exclude(name__in=['Freight Cost', 'HTSUS Tariff']).values_list('name', flat=True).distinct())

    # Write header row
    header = [
        'Invoice#', 'Date', 'Container ID', 'PO#', 'SKU', 
        'Quantity', 'Vendor Price', 'Vendor Cost', 'Freight Cost',
        'HTSUS Tariff'
    ] + other_cost_pool_names + [
        'TOTAL COST', 'Unit Total Cost'
    ]
    writer.writerow(header)

    lines = InvoiceLine.objects.all().select_related('invoice', 'sku').prefetch_related('allocatedcost_set__cost_pool')

    # Filtering logic from results view
    container_filter = request.GET.get('container')
    invoice_filter = request.GET.get('invoice')
    date_filter = request.GET.get('date')

    if container_filter:
        lines = lines.filter(invoice__container__container_id=container_filter)
    if invoice_filter:
        lines = lines.filter(invoice__invoice_number=invoice_filter)
    if date_filter:
        lines = lines.filter(invoice__invoice_date=date_filter)

    for line in lines:
        vendor_cost = line.price_vendor * line.quantity
        
        allocations = {ac.cost_pool.name: ac.amount_allocated for ac in line.allocatedcost_set.all()}

        freight_cost_amount = allocations.get('Freight Cost', Decimal(0))
        htsus_tariff_amount = allocations.get('HTSUS Tariff', Decimal(0))
        
        other_costs_values = []
        current_line_other_costs_total = Decimal(0)
        for cost_name in other_cost_pool_names:
            cost_value = allocations.get(cost_name, Decimal(0))
            other_costs_values.append(f'${cost_value:.2f}')
            current_line_other_costs_total += cost_value

        total_cost = vendor_cost + freight_cost_amount + htsus_tariff_amount + current_line_other_costs_total
        unit_total_cost = (total_cost / line.quantity) if line.quantity > 0 else Decimal(0)

        row = [
            line.invoice.invoice_number,
            line.invoice.invoice_date.strftime('%m/%d/%Y') if line.invoice.invoice_date else '',
            line.invoice.container.container_id if line.invoice.container else '',
            line.invoice.po_number,
            line.sku.sku if line.sku else '',
            line.quantity,
            f'${line.price_vendor:.2f}' if line.price_vendor else '$0.00',
            f'${vendor_cost:.2f}',
            f'${freight_cost_amount:.2f}',
            f'${htsus_tariff_amount:.2f}',
        ] + other_costs_values + [
            f'${total_cost:.2f}',
            f'${unit_total_cost:.2f}'
        ]
        writer.writerow(row)

    return response
