from django.urls import path
from . import views

urlpatterns = [
    path('countries/', views.countries_view, name='tariff_countries'),
    path("shipment-entry/", views.shipment_entry_view, name="tariff_shipment_entry"),
    path("upload/", views.upload_docs_view, name="tariff_upload"),
    path("match/", views.match_sku_hts_view, name="tariff_match"),
    path("calculate/<int:entry_id>/", views.calculate_duties_view, name="tariff_calculate"),
    path("download/invoice-template/", views.download_invoice_template, name="tariff_download_invoice_template"),
    path("download/sku-hts-template/", views.download_sku_hts_template, name="tariff_download_sku_hts_template"),
]