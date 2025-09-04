from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.invoice_upload, name='invoice_upload'),
    path('clear-invoice-data/', views.clear_invoice_data, name='clear_invoice_data'),
    path('clear-data/', views.clear_all_data, name='clear_all_data'),
    path('skus/', views.sku_list, name='sku_list'),
    path('skus/upload/', views.sku_upload, name='sku_upload'),
    path('skus/download/', views.sku_download, name='sku_download'),
    path('skus/clear/', views.clear_all_skus, name='clear_all_skus'),
    path('skus/template/download/', views.download_htsus_sku_template, name='download_htsus_sku_template'),
    path('skus/<int:pk>/edit/', views.sku_edit, name='sku_edit'),
    path('htsus/<int:pk>/delete/', views.htsus_code_delete, name='htsus_code_delete'),
    path('htsus/upload/', views.htsus_bulk_upload, name='htsus_bulk_upload'),
    path('htsus/template/', views.download_htsus_template, name='download_htsus_template'),
    path('htsus/export/', views.export_htsus_codes, name='export_htsus_codes'),
    path('results/', views.results, name='results'),
    path('download-results-csv/', views.download_results_csv, name='download_results_csv'),
    path('cost-pool/add/', views.add_cost_pool, name='add_cost_pool'),
    path('delete-cost-pool/<int:pk>/', views.delete_cost_pool, name='delete_cost_pool'),
    path('recalculate/', views.recalculate_costs, name='recalculate_costs'),
    path('invoice/<int:invoice_pk>/toggle-htsus/', views.toggle_htsus, name='toggle_htsus'),
    path('debug-base-dir/', views.debug_base_dir, name='debug_base_dir'),
    path('add-freight-cost/', views.add_freight_cost, name='add_freight_cost'),
    path('add-custom-cost/', views.add_custom_cost, name='add_custom_cost'),
]
