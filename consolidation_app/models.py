from django.db import models

class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True, blank=True, null=True) # Optional company code

    def __str__(self):
        return self.name

class ChartOfAccount(models.Model):
    account_number = models.CharField(max_length=50, unique=True) # Acc#
    account_name = models.CharField(max_length=255) # Account Name
    account_type = models.CharField(max_length=100) # Account Type (e.g., Asset, Liability, Equity, Revenue, Expense)
    category = models.CharField(max_length=100) # Category (e.g., IN, COGS, EXP)
    llm_suggested_category = models.CharField(max_length=100, blank=True, null=True) # LLM suggested category
    is_active = models.BooleanField(default=True) # For toggling inactive/duplicate accounts
    is_new_pending_approval = models.BooleanField(default=False) # For new GL codes detected on upload

    def __str__(self):
        return f"{self.account_number} - {self.account_name}"

class Project(models.Model):
    name = models.CharField(max_length=255, unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

class FinancialData(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    chart_of_account = models.ForeignKey(ChartOfAccount, on_delete=models.CASCADE)
    period_date = models.DateField() # Stores the month/year (e.g., first day of the month)
    ptd_value = models.DecimalField(max_digits=18, decimal_places=2) # Period-to-Date value
    is_pnl = models.BooleanField(default=True) # True for P&L, False for Balance Sheet
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True) # Link to a project if applicable

    class Meta:
        unique_together = ('company', 'chart_of_account', 'period_date', 'is_pnl') # Ensure unique entries

    def __str__(self):
        return f"{self.company.name} - {self.chart_of_account.account_name} - {self.period_date.strftime('%Y-%m')} - {'P&L' if self.is_pnl else 'BS'}"

class SupportingDocument(models.Model):
    financial_data_entry = models.ForeignKey(FinancialData, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='attachments/')
    description = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    llm_summary = models.TextField(blank=True, null=True) # LLM generated summary of the document

    def __str__(self):
        return f"Attachment for {self.financial_data_entry} - {self.description or self.file.name}"

class Budget(models.Model):
    name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    period_start_date = models.DateField()
    period_end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        unique_together = ('name', 'company', 'period_start_date', 'period_end_date')

    def __str__(self):
        return f"{self.name} ({self.company.name}) from {self.period_start_date} to {self.period_end_date}"

class AllocationRule(models.Model):
    ALLOCATION_TYPES = [
        ('revenue', 'Revenue-based'),
        ('headcount', 'Headcount-based'),
        ('custom', 'Custom Ratio'),
    ]
    name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    allocation_type = models.CharField(max_length=50, choices=ALLOCATION_TYPES)
    source_account = models.ForeignKey(ChartOfAccount, on_delete=models.CASCADE, related_name='source_for_allocations')
    target_accounts = models.ManyToManyField(ChartOfAccount, related_name='target_for_allocations')
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.get_allocation_type_display()})"

class BudgetFinancialData(models.Model):
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE)
    chart_of_account = models.ForeignKey(ChartOfAccount, on_delete=models.CASCADE)
    period_date = models.DateField()
    budget_value = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        unique_together = ('budget', 'chart_of_account', 'period_date')

    def __str__(self):
        return f"{self.budget.name} - {self.chart_of_account.account_name} - {self.period_date.strftime('%Y-%m')} - {self.budget_value}"
