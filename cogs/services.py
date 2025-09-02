from .models import InvoiceLine, CostPool, AllocatedCost, HTSUSCode, SKU
from decimal import Decimal
from django.db import models
from tariff.models import Entry
from datetime import date

class AllocationService:

    def compute_normalizers(self, scope, method, queryset):
        if method == CostPool.Method.PRICE:
            return sum(line.price_vendor * line.quantity for line in queryset)
        elif method == CostPool.Method.VOLUME:
            return Decimal(sum(line.unit_volume_cc * line.quantity for line in queryset))
        elif method == CostPool.Method.QUANTITY:
            return Decimal(sum(line.quantity for line in queryset))
        elif method == CostPool.Method.PRICE_QUANTITY:
            return sum(line.price_vendor * line.quantity for line in queryset)
        return Decimal(0)

    def allocate_cost(self, cost_pool):
        if cost_pool.scope == CostPool.Scope.INVOICE:
            if cost_pool.invoice:
                lines = InvoiceLine.objects.filter(invoice=cost_pool.invoice)
            else:
                lines = InvoiceLine.objects.all()
        elif cost_pool.scope == CostPool.Scope.CONTAINER:
            if cost_pool.container:
                lines = InvoiceLine.objects.filter(invoice__container=cost_pool.container)
            else:
                lines = InvoiceLine.objects.all()
        else: # ALL
            lines = InvoiceLine.objects.all()

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
            elif cost_pool.method == CostPool.Method.PRICE_QUANTITY:
                share = (line.price_vendor * line.quantity) / normalizer
            else:
                share = Decimal(0)
            
            amount = cost_pool.amount_total * share
            allocations.append(AllocatedCost(cost_pool=cost_pool, invoice_line=line, amount_allocated=amount))

        self.round_and_fix_pennies(cost_pool.amount_total, allocations)

        AllocatedCost.objects.bulk_create(allocations)

    def compute_htsus_for_invoice(self, invoice):
        """Calculate HTSUS tariffs with support for country-specific rates"""

        htsus_cost_pool, created = CostPool.objects.get_or_create(
            invoice=invoice,
            name="HTSUS Tariff",
            defaults={
                'scope': CostPool.Scope.INVOICE,
                'method': CostPool.Method.PRICE,
                'auto_compute': True,
                'amount_total': Decimal(0)
            }
        )

        # Get country code if Entry is linked
        country_code = None
        if getattr(invoice, 'entry', None):
            country_code = invoice.entry.country_origin

        total_tariff = Decimal(0)

        for line in invoice.lines.all():
            # Rate determination logic
            if not invoice.apply_db_htsus_rate and invoice.manual_htsus_rate_pct is not None:
                # Manual override at invoice level
                rate = invoice.manual_htsus_rate_pct
            else:
                # Check SKU level first
                if line.sku.htsus_rate_pct is not None:
                    rate = line.sku.htsus_rate_pct
                elif line.sku.htsus_code:
                    # Use HTS code rate
                    hts = line.sku.htsus_code

                    # Check if complex rates exist and country is known
                    if getattr(hts, 'has_complex_rates', False) and country_code:
                        # Get country-specific rate
                        rate = self._get_complex_rate(hts, country_code, invoice.invoice_date)
                    else:
                        # Use simple rate
                        rate = hts.rate_pct if hts.rate_pct else Decimal(0)
                else:
                    # No HTS code assigned
                    rate = Decimal(0)

            # Calculate tariff amount
            tariff_amount = (line.price_vendor * line.quantity) * (rate / Decimal(100))
            total_tariff += tariff_amount

        htsus_cost_pool.amount_total = total_tariff
        htsus_cost_pool.save()
        self.allocate_cost(htsus_cost_pool)

    def _get_complex_rate(self, hts_code, country_code, invoice_date):
        """Get complex rate from HTSRateDetail for specific country and date"""

        from cogs.models import HTSRateDetail

        # Find applicable rate detail
        rate_details = HTSRateDetail.objects.filter(
            hts_code=hts_code,
            country_code__in=[country_code, ''],  # Country-specific or global
            effective_from__lte=invoice_date
        ).filter(
            models.Q(effective_to__gte=invoice_date) | models.Q(effective_to__isnull=True)
        ).order_by('-country_code', '-effective_from')  # Prefer country-specific

        if rate_details.exists():
            detail = rate_details.first()

            # For now, return only ad valorem rate
            # TODO: Add support for specific duties and compound rates
            return detail.adval_pct if detail.adval_pct else Decimal(0)

        # Fallback to simple rate
        return hts_code.rate_pct if hts_code.rate_pct else Decimal(0)

    def round_and_fix_pennies(self, total_amount, allocations):
        total_allocated = Decimal(0)
        for alloc in allocations:
            alloc.amount_allocated = round(alloc.amount_allocated, 2)
            total_allocated += alloc.amount_allocated

        rounding_diff = total_amount - total_allocated
        if rounding_diff != Decimal(0) and allocations:
            allocations.sort(key=lambda x: x.amount_allocated, reverse=True)
            allocations[0].amount_allocated += rounding_diff
