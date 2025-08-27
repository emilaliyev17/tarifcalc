from django.contrib import admin
from .models import Company, ChartOfAccount, FinancialData, SupportingDocument, Project, Budget, AllocationRule, BudgetFinancialData

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

@admin.register(ChartOfAccount)
class ChartOfAccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'account_name', 'account_type', 'category', 'llm_suggested_category', 'is_active', 'is_new_pending_approval')
    list_filter = ('is_active', 'is_new_pending_approval', 'account_type', 'category')
    search_fields = ('account_number', 'account_name')
    actions = ['approve_new_accounts', 'set_active', 'set_inactive']

    def approve_new_accounts(self, request, queryset):
        for obj in queryset:
            if obj.is_new_pending_approval:
                # If LLM suggested category, use it, otherwise keep current category
                if obj.llm_suggested_category and obj.category == 'Unknown': # Only update if current category is 'Unknown'
                    obj.category = obj.llm_suggested_category
                obj.is_new_pending_approval = False
                obj.is_active = True # Automatically activate upon approval
                obj.save()
        self.message_user(request, "Selected new accounts have been approved and activated.")
    approve_new_accounts.short_description = "Approve selected new accounts"

    def set_active(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Selected accounts have been set to active.")
    set_active.short_description = "Set selected accounts to active"

    def set_inactive(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Selected accounts have been set to inactive.")
    set_inactive.short_description = "Set selected accounts to inactive"

@admin.register(FinancialData)
class FinancialDataAdmin(admin.ModelAdmin):
    list_display = ('company', 'chart_of_account', 'period_date', 'ptd_value', 'is_pnl', 'project')
    list_filter = ('company', 'period_date', 'is_pnl', 'project')
    search_fields = ('company__name', 'chart_of_account__account_name', 'chart_of_account__account_number')

@admin.register(SupportingDocument)
class SupportingDocumentAdmin(admin.ModelAdmin):
    list_display = ('financial_data_entry', 'file', 'description', 'uploaded_at', 'llm_summary')
    list_filter = ('uploaded_at',)
    search_fields = ('description', 'file', 'financial_data_entry__chart_of_account__account_name')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'start_date', 'end_date')
    list_filter = ('company',)
    search_fields = ('name', 'company__name')

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'period_start_date', 'period_end_date', 'is_active')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'company__name')

@admin.register(AllocationRule)
class AllocationRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'allocation_type', 'source_account')
    list_filter = ('company', 'allocation_type')
    search_fields = ('name', 'source_account__account_name')
    filter_horizontal = ('target_accounts',) # For ManyToMany field

@admin.register(BudgetFinancialData)
class BudgetFinancialDataAdmin(admin.ModelAdmin):
    list_display = ('budget', 'chart_of_account', 'period_date', 'budget_value')
    list_filter = ('budget', 'period_date')
    search_fields = ('budget__name', 'chart_of_account__account_name', 'chart_of_account__account_number')
