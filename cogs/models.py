from django.db import models
from django.contrib.auth.models import User
import json

class HTSUSCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField()
    rate_pct = models.DecimalField(max_digits=5, decimal_places=2, help_text="e.g. 3.5 means 3.5%")

    def __str__(self):
        return self.code

# --- LEGACY SKU MODEL - COMMENTED FOR MIGRATION ---
# class SKU(models.Model):
#     sku = models.CharField(max_length=100, unique=True)
#     name = models.CharField(max_length=255, blank=True, null=True)
#     htsus_code = models.ForeignKey(HTSUSCode, on_delete=models.SET_NULL, blank=True, null=True)
#     htsus_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text="Overrides HTSUSCode rate if present")
#
#     def __str__(self):
#         return self.sku

# --- NEW UNIFIED SKU MODEL ---
class SKU(models.Model):
    # Core fields
    sku = models.CharField(max_length=100, unique=True)  # Keep longer length from COGS
    name = models.CharField(max_length=255, blank=True, null=True)

    # HTS and tariff fields
    htsus_code = models.ForeignKey(HTSUSCode, on_delete=models.SET_NULL, blank=True, null=True)
    htsus_rate_pct = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        blank=True,
        null=True,
        help_text="Overrides HTSUSCode rate if present"
    )

    # Origin and trade program fields (from Tariff)
    origin_country = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        help_text="ISO 2-letter country code"
    )
    claimed_spi = models.CharField(
        max_length=10,
        blank=True,
        help_text="Special Program Indicator"
    )

    # Effective date fields (from Tariff)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)

    # Override tracking
    override_reason = models.TextField(
        blank=True,
        help_text="Reason for rate override"
    )

    def __str__(self):
        return self.sku

class Container(models.Model):
    container_id = models.CharField(max_length=100, unique=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.container_id

class Invoice(models.Model):
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    container = models.ForeignKey(Container, on_delete=models.SET_NULL, blank=True, null=True)
    po_number = models.CharField(max_length=100)
    currency = models.CharField(max_length=3, default="USD")
    apply_db_htsus_rate = models.BooleanField(default=True, help_text="If False, manual HTSUS rate will be used for this invoice.")
    manual_htsus_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text="Manual HTSUS rate for this invoice (e.g. 3.5 for 3.5%). Used if 'Apply DB HTSUS Rate' is False.")

    def __str__(self):
        return self.invoice_number

class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    sku = models.ForeignKey(SKU, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    price_vendor = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per unit")
    total_vendor = models.DecimalField(max_digits=10, decimal_places=2, help_text="Denormalized from CSV for validation")
    unit_volume_cc = models.FloatField(help_text="Volume per unit in cubic centimeters")

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.sku.sku}"

class CostPool(models.Model):
    class Scope(models.TextChoices):
        INVOICE = 'INVOICE', 'Invoice'
        CONTAINER = 'CONTAINER', 'Container'
        ALL = 'ALL', 'All'

    class Method(models.TextChoices):
        PRICE = 'PRICE', 'Price'
        VOLUME = 'VOLUME', 'Volume'
        QUANTITY = 'QUANTITY', 'Quantity'
        EQUALLY = 'EQUALLY', 'Equally'
        PRICE_QUANTITY = 'PRICE_QUANTITY', 'Price * Quantity'

    name = models.CharField(max_length=255)
    scope = models.CharField(max_length=10, choices=Scope.choices)
    method = models.CharField(max_length=20, choices=Method.choices)
    amount_total = models.DecimalField(max_digits=10, decimal_places=2)
    container = models.ForeignKey(Container, on_delete=models.CASCADE, blank=True, null=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, blank=True, null=True)
    auto_compute = models.BooleanField(default=False, help_text="True for system pools like HTSUS tariff")
    shipment_company = models.CharField(max_length=200, blank=True, null=True)
    shipment_invoice = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

class AllocatedCost(models.Model):
    cost_pool = models.ForeignKey(CostPool, on_delete=models.CASCADE)
    invoice_line = models.ForeignKey(InvoiceLine, on_delete=models.CASCADE)
    amount_allocated = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cost_pool.name} - {self.invoice_line}"


# ============= DATA PERSISTENCE MODELS =============
class CalculationHistory(models.Model):
    """Store history of all COGS calculations"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Original file info
    invoice_file_name = models.CharField(max_length=255)
    total_items = models.IntegerField(default=0)
    
    # Calculation results
    total_vendor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_additional_costs = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_final_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Calculation parameters (stored as JSON)
    calculation_params = models.JSONField(default=dict, blank=True)
    
    # Status
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('saved', 'Saved'),
        ('archived', 'Archived'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Optional notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Calculation History'
        verbose_name_plural = 'Calculation Histories'
    
    def __str__(self):
        return f"{self.invoice_file_name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class CalculationLineItem(models.Model):
    """Store individual line items from calculations"""
    calculation = models.ForeignKey(CalculationHistory, on_delete=models.CASCADE, related_name='line_items')
    
    # Item details
    item_number = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    vendor_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    volume = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    
    # HTSUS/Tariff
    htsus_code = models.CharField(max_length=20, blank=True)
    tariff_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Costs breakdown
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    customs_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_costs = models.JSONField(default=dict, blank=True)
    
    # Final calculations
    total_additional_costs = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        return f"{self.item_number} - {self.description[:50]}"
