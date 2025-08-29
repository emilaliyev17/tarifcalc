from django.contrib import admin
from .models import (
    Country, HTSCode, TradeProgram, TariffRate, AdditionalDuty,
    ADCVDCase, SystemFee, Entry, EntryLine, InvoiceLine,
    InvoiceToEntryMap, SkuHtsMapping
)
for m in [Country, HTSCode, TradeProgram, TariffRate, AdditionalDuty,
          ADCVDCase, SystemFee, Entry, EntryLine, InvoiceLine,
          InvoiceToEntryMap, SkuHtsMapping]:
    admin.site.register(m)