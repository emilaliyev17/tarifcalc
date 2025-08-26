from django.contrib import admin
from .models import HSUSCode, SKU, Container, Invoice, InvoiceLine, CostPool, AllocatedCost
 
# Register your models here.
admin.site.register(HSUSCode)
admin.site.register(SKU)
admin.site.register(Container)
admin.site.register(Invoice)
admin.site.register(InvoiceLine)
admin.site.register(CostPool)
admin.site.register(AllocatedCost)