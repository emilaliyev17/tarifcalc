from django.contrib import admin
from .models import HSUSCode, SKU, Container, Invoice, InvoiceLine, CostPool, AllocatedCost
 
# Custom ModelAdmin for Invoice to display new fields
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'invoice_date', 'container', 'po_number', 'currency', 'apply_db_hsus_rate', 'manual_hsus_rate_pct')
    list_filter = ('invoice_date', 'currency', 'apply_db_hsus_rate')
    search_fields = ('invoice_number', 'po_number')
    fieldsets = (
        (None, {
            'fields': ('invoice_number', 'invoice_date', 'container', 'po_number', 'currency')
        }),
        ('HSUS Rate Settings', {
            'fields': ('apply_db_hsus_rate', 'manual_hsus_rate_pct'),
            'description': 'Control how HSUS rates are applied for this invoice.'
        }),
    )

# Unregister the default Invoice admin if it was registered directly
try:
    admin.site.unregister(Invoice)
except admin.sites.NotRegistered:
    pass
# Register your models here.
admin.site.register(HSUSCode)
admin.site.register(SKU)
admin.site.register(Container)
admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(InvoiceLine)
admin.site.register(CostPool)
admin.site.register(AllocatedCost)