from django.db import models

RATE_TYPES = (("adval","Ad Valorem"), ("spec","Specific"), ("compound","Compound"))

class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=2, unique=True)  # ISO code
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Countries"
    
    def __str__(self):
        return f"{self.name} ({self.code})"

class HTSCode(models.Model):
    code = models.CharField(max_length=12, unique=True)  # allow dotted or undotted
    description = models.TextField()
    uom = models.CharField(max_length=20, blank=True)
    def __str__(self): return self.code

class TradeProgram(models.Model):
    code = models.CharField(max_length=10, unique=True)  # SPI like S, S+, A, AU, CA
    name = models.CharField(max_length=100)
    note_ref = models.CharField(max_length=50, blank=True)
    def __str__(self): return self.code

class TariffRate(models.Model):
    hts = models.ForeignKey(HTSCode, on_delete=models.CASCADE)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)
    program = models.ForeignKey(TradeProgram, on_delete=models.SET_NULL, null=True, blank=True)
    column = models.CharField(max_length=8, default="1-General")
    rate_type = models.CharField(max_length=10, choices=RATE_TYPES)
    adval_pct = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    specific_amount = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    specific_uom = models.CharField(max_length=20, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

class AdditionalDuty(models.Model):
    hts = models.ForeignKey(HTSCode, on_delete=models.CASCADE)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    kind = models.CharField(max_length=20)  # "301", "232", "Safeguard"
    rate_type = models.CharField(max_length=10, choices=RATE_TYPES)
    adval_pct = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    specific_amount = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    specific_uom = models.CharField(max_length=20, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

class ADCVDCase(models.Model):
    hts = models.ForeignKey(HTSCode, on_delete=models.CASCADE)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    case_no = models.CharField(max_length=50)
    cash_deposit_rate_pct = models.DecimalField(max_digits=7, decimal_places=4)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

class SystemFee(models.Model):
    year = models.IntegerField(unique=True)
    mpf_pct = models.DecimalField(max_digits=7, decimal_places=6)  # 0.003464
    mpf_min = models.DecimalField(max_digits=10, decimal_places=2)
    mpf_max = models.DecimalField(max_digits=10, decimal_places=2)
    hmf_pct = models.DecimalField(max_digits=7, decimal_places=6)  # 0.00125

class Entry(models.Model):
    entry_number = models.CharField(max_length=32, unique=True)
    entry_date = models.DateField(null=True, blank=True)
    import_date = models.DateField()
    mode = models.CharField(max_length=10)  # ocean, air, truck, rail
    port_of_entry = models.CharField(max_length=10, blank=True)
    importer_name = models.CharField(max_length=128, blank=True)
    country_origin = models.CharField(max_length=2)
    country_export = models.CharField(max_length=2, blank=True)
    claimed_spi = models.CharField(max_length=10, blank=True)
    notes = models.TextField(blank=True)
    entered_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    gross_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

class EntryLine(models.Model):
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE)
    line_no = models.IntegerField()
    hts_code = models.CharField(max_length=12)
    description = models.TextField(blank=True)
    entered_value = models.DecimalField(max_digits=14, decimal_places=2)
    hts_rate = models.CharField(max_length=16, blank=True)

class InvoiceLine(models.Model):
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE)
    invoice_no = models.CharField(max_length=32)
    sku = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    qty = models.DecimalField(max_digits=14, decimal_places=4)
    uom = models.CharField(max_length=16, default="unit")
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)
    country_origin = models.CharField(max_length=2, blank=True)

class InvoiceToEntryMap(models.Model):
    invoice_line = models.ForeignKey(InvoiceLine, on_delete=models.CASCADE)
    entry_line = models.ForeignKey(EntryLine, on_delete=models.CASCADE)
    qty_mapped = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    value_mapped = models.DecimalField(max_digits=14, decimal_places=2, default=0)

class SkuHtsMapping(models.Model):
    sku = models.CharField(max_length=64, unique=True)
    hts_code = models.CharField(max_length=12)
    origin_country = models.CharField(max_length=2)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    claimed_spi = models.CharField(max_length=10, blank=True)
    rate_override_pct = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    override_reason = models.TextField(blank=True)