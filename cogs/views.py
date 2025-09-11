from django.http import HttpResponse, FileResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
import os
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .forms import InvoiceUploadForm, HTSUSCodeForm, SKUForm, CostPoolForm
from .models import Invoice, InvoiceLine, SKU, Container, HTSUSCode, CostPool, AllocatedCost, SavedResults
from .services import AllocationService
from tariff.models import Country
import csv
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.db import IntegrityError
from django.db.models import Count, Sum, Min, Max
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
                    for fmt in ('%Y-%m-%d', '%m/%d/%y', '%d.%m.%Y', '%m/%d/%Y'):
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
                        quantity=int(float(row.get('Quantity'))),
                        price_vendor=Decimal(row.get('Price')),
                        total_vendor=Decimal(row.get('Total')),
                        unit_volume_cc=float(row.get('Volume'))
                    )

                messages.success(request, 'Invoice uploaded successfully')
                return redirect('results')

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
        csv_file = request.FILES.get('file')

        if not csv_file or not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('sku_list')

        try:
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            created_skus, updated_skus = 0, 0
            created_hts, updated_hts = 0, 0

            required_headers = ['sku', 'name', 'htsus_code', 'htsus_rate_pct']
            if not all(header in reader.fieldnames for header in required_headers):
                messages.error(request, f"CSV file must contain headers: {', '.join(required_headers)}")
                return redirect('sku_list')

            for row in reader:
                sku_val = (row.get('sku') or '').strip()
                if not sku_val:
                    continue

                hts_code_str = (row.get('htsus_code') or '').strip()
                rate_str = (row.get('htsus_rate_pct') or '').strip()
                desc = (row.get('description') or 'Imported via SKU upload').strip()

                hts_obj = None
                if hts_code_str:
                    rate_val = None
                    if rate_str:
                        try:
                            rate_val = Decimal(rate_str)
                        except InvalidOperation:
                            raise ValueError(f"Invalid rate format '{rate_str}' for HTSUS {hts_code_str}")

                    hts_obj, hts_created = HTSUSCode.objects.update_or_create(
                        code=hts_code_str,
                        defaults={
                            'description': desc,
                            'rate_pct': rate_val,
                        }
                    )
                    if hts_created:
                        created_hts += 1
                    else:
                        updated_hts += 1

                sku_defaults = {
                    'name': (row.get('name') or '').strip() or sku_val,
                    'htsus_code': hts_obj
                }


                sku_obj, sku_created = SKU.objects.update_or_create(
                    sku=sku_val,
                    defaults=sku_defaults
                )
                if sku_created:
                    created_skus += 1
                else:
                    updated_skus += 1

            messages.success(
                request,
                f"Processing complete. SKU: {created_skus} created, {updated_skus} updated. "
                f"HTSUS: {created_hts} created, {updated_hts} updated."
            )

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
        # Calculate HTSUS tariff on the fly based on SKU rates
        htsus_rate = Decimal('0')
        if line.sku and line.sku.htsus_rate_pct is not None:
            htsus_rate = line.sku.htsus_rate_pct
        elif line.sku and line.sku.htsus_code and line.sku.htsus_code.rate_pct:
            htsus_rate = line.sku.htsus_code.rate_pct
        htsus_tariff_amount = vendor_cost * (htsus_rate / Decimal('100'))
        
        # Calculate Section 301 duty based on country
        section_301_amount = Decimal('0')
        if line.invoice and line.invoice.country_origin:
            try:
                country = Country.objects.get(code=line.invoice.country_origin)
                section_301_rate = country.section_301_rate or Decimal('0')
                section_301_amount = vendor_cost * (section_301_rate / Decimal('100'))
            except Country.DoesNotExist:
                section_301_amount = Decimal('0')
        
        # Collect all other allocated costs for this line
        other_cost_allocations = {}
        current_line_other_costs_total = Decimal(0)
        for allocated_cost in line.allocatedcost_set.all():
            if allocated_cost.cost_pool.name not in ['Freight Cost', 'HTSUS Tariff']:
                other_cost_allocations[allocated_cost.cost_pool.name] = allocated_cost.amount_allocated
                current_line_other_costs_total += allocated_cost.amount_allocated

        total_cost = vendor_cost + freight_cost_amount + htsus_tariff_amount + section_301_amount + current_line_other_costs_total
        unit_total_cost = (total_cost / line.quantity).quantize(Decimal('0.01')) if line.quantity > 0 else Decimal(0)

        results_data.append({
            'line': line,
            'vendor_cost': vendor_cost,
            'freight_cost': freight_cost_amount,
            'htsus_tariff': htsus_tariff_amount,
            'section_301': section_301_amount,  # ADD THIS LINE
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
        allocation_scope = data.get('allocation_scope', 'container')
        allocation_method = data.get('allocation_method', 'volume')
        container_id = data.get('container_id', None)
        invoice_id = data.get('invoice_id', None)
        
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
                'scope': CostPool.Scope.CONTAINER if allocation_scope == 'container' else CostPool.Scope.INVOICE if allocation_scope == 'invoice' else CostPool.Scope.ALL,
                'method': CostPool.Method.VOLUME if allocation_method == 'volume' else CostPool.Method.PRICE_QUANTITY,
                'amount_total': Decimal(str(total_freight_cost)),
                'shipment_company': shipment_company,
                'shipment_invoice': shipment_invoice,
                'container_id': container_id if allocation_scope == 'container' and container_id else None,
                'invoice_id': invoice_id if allocation_scope == 'invoice' and invoice_id else None,
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
        container_id = data.get('container_id', None)
        invoice_id = data.get('invoice_id', None)
        
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
            container_id=container_id if allocation_scope == 'container' and container_id else None,
            invoice_id=invoice_id if allocation_scope == 'invoice' and invoice_id else None,
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
        'HTSUS Tariff', 'Section 301'
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
        # Calculate HTSUS tariff on the fly for CSV export
        htsus_rate = Decimal('0')
        if line.sku and line.sku.htsus_rate_pct is not None:
            htsus_rate = line.sku.htsus_rate_pct
        elif line.sku and line.sku.htsus_code and line.sku.htsus_code.rate_pct:
            htsus_rate = line.sku.htsus_code.rate_pct
        htsus_tariff_amount = vendor_cost * (htsus_rate / Decimal('100'))

        # Calculate Section 301 duty based on country
        section_301_amount = Decimal('0')
        if line.invoice and line.invoice.country_origin:
            try:
                country = Country.objects.get(code=line.invoice.country_origin)
                section_301_rate = country.section_301_rate or Decimal('0')
                section_301_amount = vendor_cost * (section_301_rate / Decimal('100'))
            except Country.DoesNotExist:
                section_301_amount = Decimal('0')
        
        other_costs_values = []
        current_line_other_costs_total = Decimal(0)
        for cost_name in other_cost_pool_names:
            cost_value = allocations.get(cost_name, Decimal(0))
            other_costs_values.append(f'${cost_value:.2f}')
            current_line_other_costs_total += cost_value

        total_cost = vendor_cost + freight_cost_amount + htsus_tariff_amount + section_301_amount + current_line_other_costs_total
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
            f'${section_301_amount:.2f}',
        ] + other_costs_values + [
            f'${total_cost:.2f}',
            f'${unit_total_cost:.2f}'
        ]
        writer.writerow(row)

    return response


def clear_all_skus(request):
    if request.method == 'POST':
        try:
            deleted_count, _ = SKU.objects.all().delete()
            messages.success(request, f"Successfully deleted {str(deleted_count)} SKUs.")
        except IntegrityError:
            messages.error(request, "Could not delete all SKUs because some are still linked to existing invoices.")
    return redirect('sku_list')


@login_required
def get_containers_list(request):
    """API endpoint to get list of all containers for dropdown"""
    try:
        containers = Container.objects.all().order_by('-id')
        data = [
            {
                'id': container.id,
                'container_id': container.container_id,
                'display': container.container_id
            }
            for container in containers
        ]
        return JsonResponse({'success': True, 'containers': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_invoices_list(request):
    """API endpoint to get list of all invoices for dropdown"""
    try:
        invoices = Invoice.objects.all().order_by('-invoice_date', '-id')
        data = [
            {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'date': invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
                'container': invoice.container.container_id if invoice.container else 'No container',
                'display': f"{invoice.invoice_number} ({invoice.invoice_date})"
            }
            for invoice in invoices
        ]
        return JsonResponse({'success': True, 'invoices': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def save_results_snapshot(request):
    """
    Save current results to SavedResults table.
    Reuses the same calculation logic as results() view.
    """
    try:
        # Generate batch name with timestamp
        batch_name = f"Results {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Get the same data that results() view uses (lines 281-293)
        lines = InvoiceLine.objects.all().select_related('invoice', 'sku').prefetch_related('allocatedcost_set__cost_pool')
        
        # Apply same filtering logic as results() view
        container_filter = request.GET.get('container')
        invoice_filter = request.GET.get('invoice')
        date_filter = request.GET.get('date')

        if container_filter:
            lines = lines.filter(invoice__container__container_id=container_filter)
        if invoice_filter:
            lines = lines.filter(invoice__invoice_number=invoice_filter)
        if date_filter:
            lines = lines.filter(invoice__invoice_date=date_filter)
        
        # Reuse the exact calculation logic from results() view (lines 300-342)
        saved_count = 0
        
        for line in lines:
            # Calculate all costs (same as results view)
            vendor_cost = line.price_vendor * line.quantity
            
            # Get freight cost (same logic as results view)
            freight_cost = line.allocatedcost_set.filter(cost_pool__name='Freight Cost').first()
            freight_cost_amount = freight_cost.amount_allocated if freight_cost else 0
            
            # Calculate HTSUS tariff on the fly based on SKU rates (same logic as results view)
            htsus_rate = Decimal('0')
            if line.sku and line.sku.htsus_rate_pct is not None:
                htsus_rate = line.sku.htsus_rate_pct
            elif line.sku and line.sku.htsus_code and line.sku.htsus_code.rate_pct:
                htsus_rate = line.sku.htsus_code.rate_pct
            htsus_tariff_amount = vendor_cost * (htsus_rate / Decimal('100'))
            
            # Calculate Section 301 duty based on country (same logic as results view)
            section_301_amount = Decimal('0')
            if line.invoice and line.invoice.country_origin:
                try:
                    country = Country.objects.get(code=line.invoice.country_origin)
                    section_301_rate = country.section_301_rate or Decimal('0')
                    section_301_amount = vendor_cost * (section_301_rate / Decimal('100'))
                except Country.DoesNotExist:
                    section_301_amount = Decimal('0')
            
            # Collect all other allocated costs for this line (same logic as results view)
            other_cost_allocations = {}
            current_line_other_costs_total = Decimal(0)
            for allocated_cost in line.allocatedcost_set.all():
                if allocated_cost.cost_pool.name not in ['Freight Cost', 'HTSUS Tariff']:
                    other_cost_allocations[allocated_cost.cost_pool.name] = float(allocated_cost.amount_allocated)
                    current_line_other_costs_total += allocated_cost.amount_allocated

            # Calculate totals (same logic as results view)
            total_cost = vendor_cost + freight_cost_amount + htsus_tariff_amount + section_301_amount + current_line_other_costs_total
            unit_total_cost = (total_cost / line.quantity).quantize(Decimal('0.01')) if line.quantity > 0 else Decimal(0)
            
            # Save to SavedResults
            SavedResults.objects.create(
                batch_name=batch_name,
                invoice_number=line.invoice.invoice_number,
                invoice_date=line.invoice.invoice_date,
                container_id=line.invoice.container.container_id if line.invoice.container else '',
                po_number=line.invoice.po_number,
                sku=line.sku.sku if line.sku else '',
                quantity=line.quantity,
                vendor_price=line.price_vendor,
                vendor_cost=vendor_cost,
                freight_cost=freight_cost_amount,
                htsus_tariff=htsus_tariff_amount,
                section_301=section_301_amount,
                other_costs=other_cost_allocations,  # JSON field
                total_cost=total_cost,
                unit_total_cost=unit_total_cost
            )
            saved_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Saved {saved_count} results to batch "{batch_name}"',
            'batch_name': batch_name,
            'saved_count': saved_count
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Error saving results: {str(e)}'
        })


@login_required
def reports_list(request):
    """
    Display all saved batches with summary information
    """
    # Get batch summaries
    batch_summaries = SavedResults.objects.values('batch_name').annotate(
        record_count=Count('id'),
        total_cost=Sum('total_cost'),
        created_at=Min('created_at')
    ).order_by('-created_at')
    
    return render(request, 'reports_list.html', {
        'batch_summaries': batch_summaries,
        'total_batches': batch_summaries.count()
    })


@login_required
def reports_detail(request, batch_name):
    """
    Display detailed results for a specific batch
    Reuse results.html table structure
    """
    # Get all records for this batch
    batch_records = SavedResults.objects.filter(batch_name=batch_name).order_by('invoice_number', 'sku')
    
    if not batch_records.exists():
        messages.error(request, f'Batch "{batch_name}" not found')
        return redirect('reports_list')
    
    # Get unique cost types for dynamic columns
    other_cost_types = set()
    for record in batch_records:
        if record.other_costs:
            other_cost_types.update(record.other_costs.keys())
    other_cost_types = sorted(list(other_cost_types))
    
    # Calculate summary stats
    total_records = batch_records.count()
    total_cost = sum(record.total_cost for record in batch_records)
    
    return render(request, 'reports_detail.html', {
        'batch_name': batch_name,
        'batch_records': batch_records,
        'other_cost_types': other_cost_types,
        'total_records': total_records,
        'total_cost': total_cost,
        'created_at': batch_records.first().created_at
    })


@login_required
def reports_export(request, batch_name):
    """
    Export specific batch to CSV
    Reuse download_results_csv logic
    """
    batch_records = SavedResults.objects.filter(batch_name=batch_name)
    
    if not batch_records.exists():
        messages.error(request, f'Batch "{batch_name}" not found')
        return redirect('reports_list')
    
    # Get unique cost types for headers
    other_cost_types = set()
    for record in batch_records:
        if record.other_costs:
            other_cost_types.update(record.other_costs.keys())
    other_cost_types = sorted(list(other_cost_types))
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{batch_name}_export.csv"'
    writer = csv.writer(response)
    
    # Write header
    header = [
        'Invoice#', 'Date', 'Container ID', 'PO#', 'SKU', 
        'Quantity', 'Vendor Price', 'Vendor Cost', 'Freight Cost',
        'HTSUS Tariff', 'Section 301'
    ] + other_cost_types + [
        'TOTAL COST', 'Unit Total Cost'
    ]
    writer.writerow(header)
    
    # Write data rows
    for record in batch_records:
        other_costs_values = [record.other_costs.get(cost_type, 0) for cost_type in other_cost_types]
        
        row = [
            record.invoice_number,
            record.invoice_date.strftime('%m/%d/%Y'),
            record.container_id,
            record.po_number,
            record.sku,
            record.quantity,
            f'${record.vendor_price:.2f}',
            f'${record.vendor_cost:.2f}',
            f'${record.freight_cost:.2f}',
            f'${record.htsus_tariff:.2f}',
            f'${record.section_301:.2f}',
        ] + [f'${cost:.2f}' for cost in other_costs_values] + [
            f'${record.total_cost:.2f}',
            f'${record.unit_total_cost:.2f}'
        ]
        writer.writerow(row)
    
    return response


@login_required
@require_POST
def reports_delete(request, batch_name):
    """
    Delete a specific batch
    """
    try:
        deleted_count, _ = SavedResults.objects.filter(batch_name=batch_name).delete()
        messages.success(request, f'Deleted batch "{batch_name}" ({deleted_count} records)')
    except Exception as e:
        messages.error(request, f'Error deleting batch: {str(e)}')
    
    return redirect('reports_list')


@login_required
def reports_custom(request):
    """Custom report generator with filtering"""
    
    filter_type = request.GET.get('filter_type')
    filter_value = request.GET.get('filter_value')
    
    # Get all unique values for dropdowns
    all_dates = SavedResults.objects.values_list('invoice_date', flat=True).distinct().order_by('-invoice_date')
    all_invoices = SavedResults.objects.values_list('invoice_number', flat=True).distinct().order_by('invoice_number')
    all_pos = SavedResults.objects.values_list('po_number', flat=True).distinct().order_by('po_number')
    all_containers = SavedResults.objects.exclude(container_id='').values_list('container_id', flat=True).distinct().order_by('container_id')
    
    # Filter results if parameters provided
    filtered_results = None
    if filter_type and filter_value:
        if filter_type == 'date':
            filtered_results = SavedResults.objects.filter(invoice_date=filter_value)
        elif filter_type == 'invoice':
            filtered_results = SavedResults.objects.filter(invoice_number=filter_value)
        elif filter_type == 'po':
            filtered_results = SavedResults.objects.filter(po_number=filter_value)
        elif filter_type == 'container':
            filtered_results = SavedResults.objects.filter(container_id=filter_value)
            
        # Get dynamic cost columns
        if filtered_results:
            other_cost_types = set()
            for record in filtered_results:
                if record.other_costs:
                    other_cost_types.update(record.other_costs.keys())
            other_cost_types = sorted(list(other_cost_types))
        else:
            other_cost_types = []
    else:
        other_cost_types = []
    
    # Handle CSV download
    if request.GET.get('download') == 'csv' and filtered_results:
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="custom_report_{filter_type}_{filter_value}.csv"'
        writer = csv.writer(response)
        
        # Write header
        header = [
            'Invoice#', 'Date', 'Container ID', 'PO#', 'SKU', 
            'Quantity', 'Vendor Price', 'Vendor Cost', 'Freight Cost',
            'HTSUS Tariff', 'Section 301'
        ] + other_cost_types + [
            'TOTAL COST', 'Unit Total Cost'
        ]
        writer.writerow(header)
        
        # Write data rows
        for record in filtered_results:
            other_costs_values = [record.other_costs.get(cost_type, 0) for cost_type in other_cost_types]
            
            row = [
                record.invoice_number,
                record.invoice_date.strftime('%m/%d/%Y'),
                record.container_id,
                record.po_number,
                record.sku,
                record.quantity,
                f'${record.vendor_price:.2f}',
                f'${record.vendor_cost:.2f}',
                f'${record.freight_cost:.2f}',
                f'${record.htsus_tariff:.2f}',
                f'${record.section_301:.2f}',
            ] + [f'${cost:.2f}' for cost in other_costs_values] + [
                f'${record.total_cost:.2f}',
                f'${record.unit_total_cost:.2f}'
            ]
            writer.writerow(row)
        
        return response
    
    context = {
        'all_dates': [d.strftime('%Y-%m-%d') for d in all_dates],
        'all_invoices': list(all_invoices),
        'all_pos': list(all_pos),
        'all_containers': list(all_containers),
        'filter_type': filter_type,
        'filter_value': filter_value,
        'filtered_results': filtered_results,
        'other_cost_types': other_cost_types
    }
    
    return render(request, 'reports_custom.html', context)
