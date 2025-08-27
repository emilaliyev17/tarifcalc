from django.urls import path
from . import views

app_name = 'consolidation_app'

urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('upload-attachment/', views.upload_attachment, name='upload_attachment'),
    path('allocation/', views.allocation_management, name='allocation_management'),
    path('project-profitability/', views.project_profitability, name='project_profitability'),
    path('upload-budget/', views.upload_budget, name='upload_budget'),
    path('budget-vs-actual/', views.budget_vs_actual_report, name='budget_vs_actual_report'),

    # API Endpoints
    path('api/companies/', views.CompanyList.as_view(), name='api_company_list'),
    path('api/chartofaccounts/', views.ChartOfAccountList.as_view(), name='api_chartofaccount_list'),
    path('api/projects/', views.ProjectList.as_view(), name='api_project_list'),
    path('api/financialdata/', views.FinancialDataList.as_view(), name='api_financialdata_list'),
    path('variance-analysis/', views.variance_analysis, name='variance_analysis'),

    # New ListCreateAPIView Endpoints
    path("company/", views.CompanyListCreateView.as_view(), name="api_company_list_create"),
    path("chartofaccount/", views.ChartOfAccountListCreateView.as_view(), name="api_chartofaccount_list_create"),
    path("project/", views.ProjectListCreateView.as_view(), name="api_project_list_create"),
    path("financialdata/", views.FinancialDataListCreateView.as_view(), name="api_financialdata_list_create"),
    path("budget/", views.BudgetListCreateView.as_view(), name="api_budget_list_create"),
    path("budgetfinancialdata/", views.BudgetFinancialDataListCreateView.as_view(), name="api_budgetfinancialdata_list_create"),
    path("allocationrule/", views.AllocationRuleListCreateView.as_view(), name="api_allocationrule_list_create"),
]