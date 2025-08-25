import pytest
from decimal import Decimal
from cogs.models import Invoice, InvoiceLine, CostPool, AllocatedCost, SKU, Container, HSUSCode
from cogs.services import AllocationService

@pytest.mark.django_db
def test_price_allocation():
    container = Container.objects.create(container_id='C1')
    invoice = Invoice.objects.create(invoice_number='I1', invoice_date='2023-01-01', container=container, po_number='PO1')
    sku1 = SKU.objects.create(sku='SKU1')
    sku2 = SKU.objects.create(sku='SKU2')
    line1 = InvoiceLine.objects.create(invoice=invoice, sku=sku1, quantity=10, price_vendor=Decimal('10.00'), total_vendor=Decimal('100.00'), unit_volume_cc=100)
    line2 = InvoiceLine.objects.create(invoice=invoice, sku=sku2, quantity=20, price_vendor=Decimal('5.00'), total_vendor=Decimal('100.00'), unit_volume_cc=200)
    cost_pool = CostPool.objects.create(name='Freight', scope=CostPool.Scope.INVOICE, method=CostPool.Method.PRICE, amount_total=Decimal('50.00'), invoice=invoice)

    service = AllocationService()
    service.allocate_cost(cost_pool)

    allocations = AllocatedCost.objects.filter(cost_pool=cost_pool)
    assert allocations.count() == 2
    assert allocations.get(invoice_line=line1).amount_allocated == Decimal('25.00')
    assert allocations.get(invoice_line=line2).amount_allocated == Decimal('25.00')

@pytest.mark.django_db
def test_volume_allocation():
    container = Container.objects.create(container_id='C1')
    invoice = Invoice.objects.create(invoice_number='I1', invoice_date='2023-01-01', container=container, po_number='PO1')
    sku1 = SKU.objects.create(sku='SKU1')
    sku2 = SKU.objects.create(sku='SKU2')
    line1 = InvoiceLine.objects.create(invoice=invoice, sku=sku1, quantity=1, price_vendor=Decimal('10.00'), total_vendor=Decimal('10.00'), unit_volume_cc=1000)
    line2 = InvoiceLine.objects.create(invoice=invoice, sku=sku2, quantity=1, price_vendor=Decimal('20.00'), total_vendor=Decimal('20.00'), unit_volume_cc=3000)
    cost_pool = CostPool.objects.create(name='Freight', scope=CostPool.Scope.INVOICE, method=CostPool.Method.VOLUME, amount_total=Decimal('100.00'), invoice=invoice)

    service = AllocationService()
    service.allocate_cost(cost_pool)

    allocations = AllocatedCost.objects.filter(cost_pool=cost_pool)
    assert allocations.count() == 2
    assert allocations.get(invoice_line=line1).amount_allocated == Decimal('25.00')
    assert allocations.get(invoice_line=line2).amount_allocated == Decimal('75.00')

@pytest.mark.django_db
def test_quantity_allocation():
    container = Container.objects.create(container_id='C1')
    invoice = Invoice.objects.create(invoice_number='I1', invoice_date='2023-01-01', container=container, po_number='PO1')
    sku1 = SKU.objects.create(sku='SKU1')
    sku2 = SKU.objects.create(sku='SKU2')
    line1 = InvoiceLine.objects.create(invoice=invoice, sku=sku1, quantity=10, price_vendor=Decimal('10.00'), total_vendor=Decimal('100.00'), unit_volume_cc=100)
    line2 = InvoiceLine.objects.create(invoice=invoice, sku=sku2, quantity=30, price_vendor=Decimal('5.00'), total_vendor=Decimal('150.00'), unit_volume_cc=200)
    cost_pool = CostPool.objects.create(name='Freight', scope=CostPool.Scope.INVOICE, method=CostPool.Method.QUANTITY, amount_total=Decimal('80.00'), invoice=invoice)

    service = AllocationService()
    service.allocate_cost(cost_pool)

    allocations = AllocatedCost.objects.filter(cost_pool=cost_pool)
    assert allocations.count() == 2
    assert allocations.get(invoice_line=line1).amount_allocated == Decimal('20.00')
    assert allocations.get(invoice_line=line2).amount_allocated == Decimal('60.00')
