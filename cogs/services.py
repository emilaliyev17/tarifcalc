from .models import InvoiceLine, CostPool, AllocatedCost, HSUSCode, SKU
from decimal import Decimal

class AllocationService:

    def compute_normalizers(self, scope, method, queryset):
        if method == CostPool.Method.PRICE:
            return sum(line.price_vendor * line.quantity for line in queryset)
        elif method == CostPool.Method.VOLUME:
            return Decimal(sum(line.unit_volume_cc * line.quantity for line in queryset))
        elif method == CostPool.Method.QUANTITY:
            return Decimal(sum(line.quantity for line in queryset))
        return Decimal(0)

    def allocate_cost(self, cost_pool):
        if cost_pool.scope == CostPool.Scope.INVOICE:
            lines = InvoiceLine.objects.filter(invoice=cost_pool.invoice)
        else: # CONTAINER
            lines = InvoiceLine.objects.filter(invoice__container=cost_pool.container)

        normalizer = self.compute_normalizers(cost_pool.scope, cost_pool.method, lines)

        if normalizer == 0:
            # Allocate equally if normalizer is zero
            if lines.count() > 0:
                amount_per_line = cost_pool.amount_total / lines.count()
                for line in lines:
                    AllocatedCost.objects.create(
                        cost_pool=cost_pool,
                        invoice_line=line,
                        amount_allocated=amount_per_line
                    )
            return

        allocations = []
        for line in lines:
            if cost_pool.method == CostPool.Method.PRICE:
                share = (line.price_vendor * line.quantity) / normalizer
            elif cost_pool.method == CostPool.Method.VOLUME:
                share = Decimal(line.unit_volume_cc * line.quantity) / normalizer
            elif cost_pool.method == CostPool.Method.QUANTITY:
                share = Decimal(line.quantity) / normalizer
            else:
                share = Decimal(0)
            
            amount = cost_pool.amount_total * share
            allocations.append(AllocatedCost(cost_pool=cost_pool, invoice_line=line, amount_allocated=amount))

        self.round_and_fix_pennies(cost_pool.amount_total, allocations)

        AllocatedCost.objects.bulk_create(allocations)

    def compute_hsus_for_invoice(self, invoice):
        hsus_cost_pool, created = CostPool.objects.get_or_create(
            invoice=invoice,
            name="HSUS Tariff",
            defaults={
                'scope': CostPool.Scope.INVOICE,
                'method': CostPool.Method.PRICE,
                'auto_compute': True,
                'amount_total': Decimal(0)
            }
        )

        total_tariff = Decimal(0)
        for line in invoice.lines.all():
            rate = line.sku.hsus_rate_pct or (line.sku.hsus_code.rate_pct if line.sku.hsus_code else Decimal(0))
            tariff_amount = (line.price_vendor * line.quantity) * (rate / Decimal(100))
            total_tariff += tariff_amount

        hsus_cost_pool.amount_total = total_tariff
        hsus_cost_pool.save()
        self.allocate_cost(hsus_cost_pool)

    def round_and_fix_pennies(self, total_amount, allocations):
        total_allocated = Decimal(0)
        for alloc in allocations:
            alloc.amount_allocated = round(alloc.amount_allocated, 2)
            total_allocated += alloc.amount_allocated

        rounding_diff = total_amount - total_allocated
        if rounding_diff != Decimal(0) and allocations:
            allocations.sort(key=lambda x: x.amount_allocated, reverse=True)
            allocations[0].amount_allocated += rounding_diff
