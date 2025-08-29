from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.invoice_upload, name='invoice_upload'),
    path('skus/', views.sku_list, name='sku_list'),
    path('skus/upload/', views.sku_upload, name='sku_upload'),
    path('skus/download/', views.sku_download, name='sku_download'),
    path('skus/template/download/', views.download_hsus_sku_template, name='download_hsus_sku_template'),
    path('skus/<int:pk>/edit/', views.sku_edit, name='sku_edit'),
    path('hsus/', views.hsus_code_list, name='hsus_code_list'),
    path('hsus/<int:pk>/delete/', views.hsus_code_delete, name='hsus_code_delete'),
    path('hsus/upload/', views.hsus_bulk_upload, name='hsus_bulk_upload'),
    path('hsus/template/', views.download_hsus_template, name='download_hsus_template'),
    path('hsus/export/', views.export_hsus_codes, name='export_hsus_codes'),
    path('results/', views.results, name='results'),
    path('cost-pool/add/', views.add_cost_pool, name='add_cost_pool'),
    path('delete-cost-pool/<int:pk>/', views.delete_cost_pool, name='delete_cost_pool'),
    path('recalculate/', views.recalculate_costs, name='recalculate_costs'),
    path('invoice/<int:invoice_pk>/toggle-hsus/', views.toggle_hsus, name='toggle_hsus'),
    path('debug-base-dir/', views.debug_base_dir, name='debug_base_dir'),
    path('add-freight-cost/', views.add_freight_cost, name='add_freight_cost'),
    path('add-custom-cost/', views.add_custom_cost, name='add_custom_cost'),
]
