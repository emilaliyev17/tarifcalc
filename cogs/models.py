from django.db import models

class HSUSCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField()
    rate_pct = models.DecimalField(max_digits=5, decimal_places=2, help_text="e.g. 3.5 means 3.5%")

    def __str__(self):
        return self.code

class SKU(models.Model):
    sku = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    hsus_code = models.ForeignKey(HSUSCode, on_delete=models.SET_NULL, blank=True, null=True)
    hsus_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text="Overrides HSUSCode rate if present")

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

    class Method(models.TextChoices):
        PRICE = 'PRICE', 'Price'
        VOLUME = 'VOLUME', 'Volume'
        QUANTITY = 'QUANTITY', 'Quantity'

    name = models.CharField(max_length=255)
    scope = models.CharField(max_length=10, choices=Scope.choices)
    method = models.CharField(max_length=10, choices=Method.choices)
    amount_total = models.DecimalField(max_digits=10, decimal_places=2)
    container = models.ForeignKey(Container, on_delete=models.CASCADE, blank=True, null=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, blank=True, null=True)
    auto_compute = models.BooleanField(default=False, help_text="True for system pools like HSUS tariff")

    def __str__(self):
        return self.name

class AllocatedCost(models.Model):
    cost_pool = models.ForeignKey(CostPool, on_delete=models.CASCADE)
    invoice_line = models.ForeignKey(InvoiceLine, on_delete=models.CASCADE)
    amount_allocated = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cost_pool.name} - {self.invoice_line}"