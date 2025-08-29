import pytest
from decimal import Decimal
from cogs.models import Invoice, InvoiceLine, CostPool, SKU, HTSUSCode, Container
from cogs.services import AllocationService

@pytest.mark.django_db
def test_htsus_allocation_from_db_rate():
    # Setup HTSUSCode and SKU with DB rate
    htsus_code = HTSUSCode.objects.create(code='HTSUS123', description='Test HTSUS', rate_pct=Decimal('5.00'))
    sku = SKU.objects.create(sku='SKU001', htsus_code=htsus_code, name='Test Product')

    container = Container.objects.create(container_id='C1')
    invoice = Invoice.objects.create(invoice_number='INV001', invoice_date='2023-01-01', container=container, po_number='PO1')
    InvoiceLine.objects.create(invoice=invoice, sku=sku, quantity=10, price_vendor=Decimal('100.00'), total_vendor=Decimal('1000.00'), unit_volume_cc=100)

    service = AllocationService()
    service.compute_htsus_for_invoice(invoice)

    cost_pool = CostPool.objects.get(invoice=invoice, name='HTSUS Tariff')
    assert cost_pool.amount_total == Decimal('50.00') # 1000 * 5% = 50

@pytest.mark.django_db
def test_htsus_allocation_from_sku_override_rate():
    # Setup HTSUSCode and SKU with SKU override rate
    htsus_code = HTSUSCode.objects.create(code='HTSUS123', description='Test HTSUS', rate_pct=Decimal('5.00'))
    sku = SKU.objects.create(sku='SKU001', htsus_code=htsus_code, name='Test Product', htsus_rate_pct=Decimal('7.50'))

    container = Container.objects.create(container_id='C1')
    invoice = Invoice.objects.create(invoice_number='INV002', invoice_date='2023-01-01', container=container, po_number='PO2')
    InvoiceLine.objects.create(invoice=invoice, sku=sku, quantity=10, price_vendor=Decimal('100.00'), total_vendor=Decimal('1000.00'), unit_volume_cc=100)

    service = AllocationService()
    service.compute_htsus_for_invoice(invoice)

    cost_pool = CostPool.objects.get(invoice=invoice, name='HTSUS Tariff')
    assert cost_pool.amount_total == Decimal('75.00') # 1000 * 7.5% = 75

@pytest.mark.django_db
def test_htsus_allocation_manual_invoice_rate():
    # Setup HTSUSCode and SKU (rates won't be used)
    htsus_code = HTSUSCode.objects.create(code='HTSUS123', description='Test HTSUS', rate_pct=Decimal('5.00'))
    sku = SKU.objects.create(sku='SKU001', htsus_code=htsus_code, name='Test Product', htsus_rate_pct=Decimal('7.50'))

    container = Container.objects.create(container_id='C1')
    invoice = Invoice.objects.create(
        invoice_number='INV003',
        invoice_date='2023-01-01',
        container=container,
        po_number='PO3',
        apply_db_htsus_rate=False, # Manual override
        manual_htsus_rate_pct=Decimal('10.00')
    )
    InvoiceLine.objects.create(invoice=invoice, sku=sku, quantity=10, price_vendor=Decimal('100.00'), total_vendor=Decimal('1000.00'), unit_volume_cc=100)

    service = AllocationService()
    service.compute_htsus_for_invoice(invoice)

    cost_pool = CostPool.objects.get(invoice=invoice, name='HTSUS Tariff')
    assert cost_pool.amount_total == Decimal('100.00') # 1000 * 10% = 100

@pytest.mark.django_db
def test_htsus_allocation_manual_invoice_rate_no_manual_value():
    # Test case where apply_db_htsus_rate is False but manual_htsus_rate_pct is None
    htsus_code = HTSUSCode.objects.create(code='HTSUS123', description='Test HTSUS', rate_pct=Decimal('5.00'))
    sku = SKU.objects.create(sku='SKU001', htsus_code=htsus_code, name='Test Product', htsus_rate_pct=Decimal('7.50'))

    container = Container.objects.create(container_id='C1')
    invoice = Invoice.objects.create(
        invoice_number='INV004',
        invoice_date='2023-01-01',
        container=container,
        po_number='PO4',
        apply_db_htsus_rate=False, # Manual override
        manual_htsus_rate_pct=None # No manual value provided
    )
    InvoiceLine.objects.create(invoice=invoice, sku=sku, quantity=10, price_vendor=Decimal('100.00'), total_vendor=Decimal('1000.00'), unit_volume_cc=100)

    service = AllocationService()
    service.compute_htsus_for_invoice(invoice)

    cost_pool = CostPool.objects.get(invoice=invoice, name='HTSUS Tariff')
    # Expect it to fall back to SKU override rate or HTSUSCode rate if manual is None
    assert cost_pool.amount_total == Decimal('75.00') # Should use SKU override rate (7.5%)
