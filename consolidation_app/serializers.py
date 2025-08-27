from rest_framework import serializers
from .models import FinancialData, Company, ChartOfAccount, Project, Budget, BudgetFinancialData, AllocationRule

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'

class ChartOfAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartOfAccount
        fields = '__all__'

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'

class BudgetSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    class Meta:
        model = Budget
        fields = '__all__'

class BudgetFinancialDataSerializer(serializers.ModelSerializer):
    budget_name = serializers.CharField(source='budget.name', read_only=True)
    account_name = serializers.CharField(source='chart_of_account.account_name', read_only=True)
    class Meta:
        model = BudgetFinancialData
        fields = '__all__'

class AllocationRuleSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    source_account_name = serializers.CharField(source='source_account.account_name', read_only=True)
    target_account_names = serializers.StringRelatedField(many=True, source='target_accounts', read_only=True)
    class Meta:
        model = AllocationRule
        fields = '__all__'

class FinancialDataSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    account_name = serializers.CharField(source='chart_of_account.account_name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = FinancialData
        fields = [
            'id',
            'company',
            'company_name',
            'chart_of_account',
            'account_name',
            'period_date',
            'ptd_value',
            'is_pnl',
            'project',
            'project_name',
        ]
