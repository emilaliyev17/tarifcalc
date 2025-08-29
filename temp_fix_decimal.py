from cogs.models import InvoiceLine
from decimal import Decimal
# Check for non-numeric values in decimal fields
for line in InvoiceLine.objects.all():
    try:
        if line.price_vendor:
            Decimal(str(line.price_vendor))
        if line.unit_volume_cc:
            Decimal(str(line.unit_volume_cc))
    except:
        print(f"Bad data in InvoiceLine {line.id}: price={line.price_vendor}, volume={line.unit_volume_cc}")
        # Set to 0 if invalid
        if line.price_vendor and not isinstance(line.price_vendor, (int, float, Decimal)):
            line.price_vendor = 0
        if line.unit_volume_cc and not isinstance(line.unit_volume_cc, (int, float, Decimal)):
            line.unit_volume_cc = 0
        line.save()