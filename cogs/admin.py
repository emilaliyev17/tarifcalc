from django.contrib import admin
from .models import HTSUSCode, SKU, Container, Invoice, InvoiceLine, CostPool, AllocatedCost, CalculationHistory, CalculationLineItem, SavedResults
 
# Custom ModelAdmin for Invoice to display new fields
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'invoice_date', 'container', 'po_number', 'currency', 'apply_db_htsus_rate', 'manual_htsus_rate_pct')
    list_filter = ('invoice_date', 'currency', 'apply_db_htsus_rate')
    search_fields = ('invoice_number', 'po_number')
    fieldsets = (
        (None, {
            'fields': ('invoice_number', 'invoice_date', 'container', 'po_number', 'currency')
        }),
        ('HTSUS Rate Settings', {
            'fields': ('apply_db_htsus_rate', 'manual_htsus_rate_pct'),
            'description': 'Control how HTSUS rates are applied for this invoice.'
        }),
    )

# Unregister the default Invoice admin if it was registered directly
try:
    admin.site.unregister(Invoice)
except admin.sites.NotRegistered:
    pass
# Register your models here.
admin.site.register(HTSUSCode)
admin.site.register(SKU)
admin.site.register(Container)
admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(InvoiceLine)
admin.site.register(CostPool)
admin.site.register(AllocatedCost)

@admin.register(CalculationHistory)
class CalculationHistoryAdmin(admin.ModelAdmin):
    list_display = ['invoice_file_name', 'created_at', 'status', 'total_final_cost', 'total_items']
    list_filter = ['status', 'created_at']
    search_fields = ['invoice_file_name', 'notes']
    date_hierarchy = 'created_at'

@admin.register(CalculationLineItem)
class CalculationLineItemAdmin(admin.ModelAdmin):
    list_display = ['item_number', 'description', 'vendor_price', 'final_unit_cost']
    list_filter = ['calculation__created_at']
    search_fields = ['item_number', 'description', 'htsus_code']

@admin.register(SavedResults)
class SavedResultsAdmin(admin.ModelAdmin):
    list_display = ['batch_name', 'invoice_number', 'sku', 'quantity', 'total_cost', 'created_at']
    list_filter = ['batch_name', 'created_at']
    search_fields = ['batch_name', 'invoice_number', 'sku']
    readonly_fields = ['created_at']
    
    # Show JSON field nicely
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ['other_costs']
        return self.readonly_fields
