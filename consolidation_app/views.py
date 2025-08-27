from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Company, ChartOfAccount, FinancialData, SupportingDocument, AllocationRule, Project, Budget, BudgetFinancialData
from .serializers import CompanySerializer, ChartOfAccountSerializer, ProjectSerializer, FinancialDataSerializer, BudgetSerializer, BudgetFinancialDataSerializer, AllocationRuleSerializer
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
import pandas as pd
import io
import os
import openai
from datetime import datetime
from django.db.models import Sum
from django.db.models.functions import TruncMonth

# Configure OpenAI API
# It's recommended to set OPENAI_API_KEY as an environment variable
# For example: export OPENAI_API_KEY='YOUR_API_KEY_HERE'

# Ensure API key is set
if not os.environ.get("OPENAI_API_KEY"):
    print("WARNING: OPENAI_API_KEY environment variable not set. LLM features may not work.")

# Initialize the OpenAI client
try:
    openai_client = openai.OpenAI()
    llm_model_name = "gpt-3.5-turbo" # Or other suitable OpenAI model like "gpt-4o"
except Exception as e:
    openai_client = None
    print(f"Error initializing OpenAI client: {e}. LLM features will be disabled.")

def get_llm_category_suggestion(account_name):
    if not openai_client:
        return None
    try:
        prompt_messages = [
            {"role": "system", "content": "You are a financial assistant. Your task is to suggest a financial category for a given account name. Provide only the category name. Examples of categories are: Income, Cost of Goods Sold, Operating Expense, Asset, Liability, Equity, Other Income, Other Expense."},
            {"role": "user", "content": f"Suggest a category for the account name: {account_name}"}
        ]
        response = openai_client.chat.completions.create(
            model=llm_model_name,
            messages=prompt_messages,
            max_tokens=50, # Limit response length
            temperature=0.0 # Make output deterministic
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error getting LLM category suggestion for {account_name}: {e}")
        return None

def _read_text_from_file(uploaded_file):
    """Helper function to extract text content from common file types."""
    content = ""
    file_name = uploaded_file.name.lower()
    try:
        if file_name.endswith(('.txt', '.csv')):
            content = uploaded_file.read().decode('utf-8')
        # Add more file types here if needed (e.g., .pdf, .docx with appropriate libraries)
        # elif file_name.endswith('.pdf'):
        #     # Use a library like PyPDF2 or pdfminer.six
        #     pass
        # elif file_name.endswith('.docx'):
        #     # Use a library like python-docx
        #     pass
        else:
            return None # Unsupported file type for text extraction
    except Exception as e:
        print(f"Error reading file {file_name}: {e}")
        return None
    return content

def get_llm_summary_suggestion(document_content):
    if not openai_client or not document_content:
        return None
    try:
        prompt_messages = [
            {"role": "system", "content": "You are a financial assistant. Summarize the provided financial document content concisely, highlighting key financial insights or important details. Focus on actionable information. If the document is not financial, state that."},
            {"role": "user", "content": f"Summarize the following document: {document_content[:4000]}"}
        ] # Limit content to avoid exceeding token limits
        response = openai_client.chat.completions.create(
            model=llm_model_name,
            messages=prompt_messages,
            max_tokens=200, # Limit summary length
            temperature=0.0 # Make output deterministic
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error getting LLM summary suggestion: {e}")
        return None

def upload_file(request):
    companies = Company.objects.all() # Get all companies for the dropdown
    projects = Project.objects.all() # Get all projects for the dropdown

    if request.method == 'POST':
        company_id = request.POST.get('company')
        project_id = request.POST.get('project') # Get selected project ID
        uploaded_file = request.FILES.get('financial_file')

        if not company_id or not uploaded_file:
            return render(request, 'consolidation_app/upload.html', {
                'companies': companies,
                'projects': projects,
                'error_message': 'Please select a company and upload a file.'
            })

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return render(request, 'consolidation_app/upload.html', {
                'companies': companies,
                'projects': projects,
                'error_message': 'Selected company does not exist.'
            })

        project = None
        if project_id: # If a project is selected
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                return render(request, 'consolidation_app/upload.html', {
                    'companies': companies,
                    'projects': projects,
                    'error_message': 'Selected project does not exist.'
                })

        # Read the file into a pandas DataFrame
        df = None
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file.read())
        elif uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(io.StringIO(uploaded_file.read().decode('utf-8')))
        else:
            return render(request, 'consolidation_app/upload.html', {
                'companies': companies,
                'projects': projects,
                'error_message': 'Unsupported file format. Please upload .xlsx, .xls, or .csv.'
            })

        # Assuming GL Account Code is in the first column (index 0 or 'A')
        # and Account Name is in the second column (index 1 or 'B')
        gl_codes_in_file = df.iloc[:, 0].astype(str).unique() # Column A
        raw_names_in_file = df.iloc[:, 1].astype(str).unique() # Column B

        existing_coa_numbers = set(ChartOfAccount.objects.values_list('account_number', flat=True))

        new_gl_codes = []
        for code in gl_codes_in_file:
            if code not in existing_coa_numbers:
                account_name = "Unknown"
                try:
                    matching_row = df[df.iloc[:, 0].astype(str) == code].iloc[0]
                    account_name = matching_row.iloc[1] # Column B
                except IndexError:
                    pass

                llm_suggested_category = get_llm_category_suggestion(account_name)

                new_gl_codes.append({'account_number': code, 'account_name': account_name, 'llm_suggested_category': llm_suggested_category})
                ChartOfAccount.objects.create(
                    account_number=code,
                    account_name=account_name,
                    account_type='Unknown', # Placeholder
                    category='Unknown', # Placeholder
                    is_new_pending_approval=True,
                    llm_suggested_category=llm_suggested_category
                )

        # Save financial data (simplified for now, assuming monthly PTD values are in subsequent columns)
        # This part needs to be expanded to correctly parse and save all monthly values
        # For now, just saving the first value for demonstration
        for index, row in df.iterrows():
            gl_code = str(row.iloc[0])
            coa_entry = ChartOfAccount.objects.get(account_number=gl_code)
            # Assuming the first value column is C (index 2)
            ptd_value = row.iloc[2] if len(row) > 2 else 0 # Get PTD value from column C
            
            # Determine period_date (simplified: assuming data is for current month for now)
            # In a real scenario, you'd parse the month from the column headers or user input
            current_month = datetime.now().replace(day=1).date()

            FinancialData.objects.create(
                company=company,
                chart_of_account=coa_entry,
                period_date=current_month,
                ptd_value=ptd_value,
                is_pnl=True, # Assuming P&L for now, needs to be determined from file type
                project=project # Save the linked project
            )

        context = {
            'companies': companies,
            'projects': projects,
            'success_message': f'File uploaded for {company.name}. '
                               f'Processed {len(gl_codes_in_file)} GL codes and saved financial data.'
        }
        if new_gl_codes:
            context['new_gl_codes'] = new_gl_codes
            context['success_message'] += f' {len(new_gl_codes)} new GL codes detected and flagged for approval.'

        return render(request, 'consolidation_app/upload.html', context)

    return render(request, 'consolidation_app/upload.html', {'companies': companies, 'projects': projects})

def upload_attachment(request):
    financial_data_entries = FinancialData.objects.all() # For dropdown

    if request.method == 'POST':
        financial_data_entry_id = request.POST.get('financial_data_entry')
        uploaded_file = request.FILES.get('attachment_file')
        description = request.POST.get('description', '')

        if not financial_data_entry_id or not uploaded_file:
            return render(request, 'consolidation_app/upload_attachment.html', {
                'financial_data_entries': financial_data_entries,
                'error_message': 'Please select a financial data entry and upload a file.'
            })

        try:
            financial_data_entry = FinancialData.objects.get(id=financial_data_entry_id)
        except FinancialData.DoesNotExist:
            return render(request, 'consolidation_app/upload_attachment.html', {
                'financial_data_entries': financial_data_entries,
                'error_message': 'Selected financial data entry does not exist.'
            })

        # Extract text content for LLM summarization
        document_content = _read_text_from_file(uploaded_file)
        llm_summary = None
        if document_content:
            llm_summary = get_llm_summary_suggestion(document_content)

        # Save the attachment
        SupportingDocument.objects.create(
            financial_data_entry=financial_data_entry,
            file=uploaded_file,
            description=description,
            llm_summary=llm_summary
        )

        context = {
            'financial_data_entries': financial_data_entries,
            'success_message': f'Attachment \'{uploaded_file.name}\' uploaded successfully for {financial_data_entry}.'
        }
        if llm_summary:
            context['success_message'] += f' LLM Summary: {llm_summary}'

        return render(request, 'consolidation_app/upload_attachment.html', context)

def _perform_allocation(allocation_rule, period_date):
    """Performs the allocation calculation based on the rule and period."""
    # Fetch source account data for the given period and company
    source_data = FinancialData.objects.filter(
        company=allocation_rule.company,
        chart_of_account=allocation_rule.source_account,
        period_date=period_date
    ).first()

    if not source_data or source_data.ptd_value == 0:
        print(f"No source data or zero value for allocation rule {allocation_rule.name} in {period_date}")
        return

    total_source_value = source_data.ptd_value

    # Fetch target account data for the same period and company
    # This assumes allocation is based on the PTD value of target accounts
    target_data_queryset = FinancialData.objects.filter(
        company=allocation_rule.company,
        chart_of_account__in=allocation_rule.target_accounts.all(),
        period_date=period_date
    )

    total_target_basis = sum([data.ptd_value for data in target_data_queryset])

    if total_target_basis == 0:
        print(f"Zero total target basis for allocation rule {allocation_rule.name} in {period_date}")
        return

    for target_data in target_data_queryset:
        allocation_ratio = target_data.ptd_value / total_target_basis
        allocated_amount = total_source_value * allocation_ratio

        # Create new FinancialData entry for the allocated amount
        # You might want to define a specific ChartOfAccount for allocated expenses/income
        # For simplicity, using a placeholder account for now.
        # In a real scenario, you'd have specific allocated accounts or adjust existing ones.
        allocated_account, created = ChartOfAccount.objects.get_or_create(
            account_number=f"ALLOCATED_{allocation_rule.source_account.account_number}",
            defaults={
                'account_name': f"Allocated {allocation_rule.source_account.account_name}",
                'account_type': allocation_rule.source_account.account_type,
                'category': allocation_rule.source_account.category,
                'is_active': True
            }
        )

        FinancialData.objects.create(
            company=allocation_rule.company,
            chart_of_account=allocated_account,
            period_date=period_date,
            ptd_value=allocated_amount,
            is_pnl=source_data.is_pnl # Keep the same P&L/BS type
        )
        print(f"Allocated {allocated_amount} from {allocation_rule.source_account.account_name} to {target_data.chart_of_account.account_name}")

def allocation_management(request):
    allocation_rules = AllocationRule.objects.all()

    if request.method == 'POST':
        # Get period date from form
        period_date_str = request.POST.get('period_date')
        if not period_date_str:
            return render(request, 'consolidation_app/allocation_management.html', {
                'allocation_rules': allocation_rules,
                'error_message': 'Please select a period date.'
            })
        try:
            period_date = datetime.strptime(period_date_str, '%Y-%m-%d').date()
        except ValueError:
            return render(request, 'consolidation_app/allocation_management.html', {
                'allocation_rules': allocation_rules,
                'error_message': 'Invalid date format. Please use YYYY-MM-DD.'
            })

        # Trigger allocation for all rules for the selected period
        for rule in allocation_rules:
            _perform_allocation(rule, period_date)

        message = "Allocation process completed for selected period."
        return render(request, 'consolidation_app/allocation_management.html', {
            'allocation_rules': allocation_rules,
            'message': message
        })

    return render(request, 'consolidation_app/allocation_management.html', {'allocation_rules': allocation_rules})

def project_profitability(request):
    projects = Project.objects.all()
    profitability_data = []

    for project in projects:
        # Fetch financial data for the project
        project_financial_data = FinancialData.objects.filter(project=project)

        # Aggregate revenue, direct costs, allocated overhead
        # This assumes you have ChartOfAccount categories defined for these
        # For example, 'Revenue', 'Direct Cost', 'Allocated Overhead'
        revenue = project_financial_data.filter(
            chart_of_account__category='Revenue'
        ).aggregate(Sum('ptd_value'))['ptd_value__sum'] or 0

        direct_costs = project_financial_data.filter(
            chart_of_account__category='Direct Cost'
        ).aggregate(Sum('ptd_value'))['ptd_value__sum'] or 0

        allocated_overhead = project_financial_data.filter(
            chart_of_account__account_number__startswith='ALLOCATED_'
        ).aggregate(Sum('ptd_value'))['ptd_value__sum'] or 0

        gross_profit = revenue - direct_costs
        net_profit = gross_profit - allocated_overhead

        profitability_data.append({
            'project': project,
            'revenue': revenue,
            'direct_costs': direct_costs,
            'allocated_overhead': allocated_overhead,
            'gross_profit': gross_profit,
            'net_profit': net_profit,
        })

    context = {
        'profitability_data': profitability_data
    }
    return render(request, 'consolidation_app/project_profitability.html', context)

def upload_budget(request):
    budgets = Budget.objects.all() # Get all budgets for the dropdown

    if request.method == 'POST':
        budget_id = request.POST.get('budget')
        uploaded_file = request.FILES.get('budget_file')

        if not budget_id or not uploaded_file:
            return render(request, 'consolidation_app/upload_budget.html', {
                'budgets': budgets,
                'error_message': 'Please select a budget and upload a file.'
            })

        try:
            budget = Budget.objects.get(id=budget_id)
        except Budget.DoesNotExist:
            return render(request, 'consolidation_app/upload_budget.html', {
                'budgets': budgets,
                'error_message': 'Selected budget does not exist.'
            })

        # Read the file into a pandas DataFrame
        df = None
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file.read())
        elif uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(io.StringIO(uploaded_file.read().decode('utf-8')))
        else:
            return render(request, 'consolidation_app/upload_budget.html', {
                'budgets': budgets,
                'error_message': 'Unsupported file format. Please upload .xlsx, .xls, or .csv.'
            })

        # Assuming GL Account Code is in the first column (index 0 or 'A')
        # and monthly values start from column C (index 2)
        gl_codes_in_file = df.iloc[:, 0].astype(str).unique()

        # Iterate through DataFrame to save budget data
        for index, row in df.iterrows():
            gl_code = str(row.iloc[0])
            try:
                coa_entry = ChartOfAccount.objects.get(account_number=gl_code)
            except ChartOfAccount.DoesNotExist:
                # Handle case where GL code from budget file is not in CoA
                # For now, skip or log. In a real app, you might want to flag this.
                print(f"GL code {gl_codes_in_file} from budget file not found in CoA. Skipping.")
                continue

            # Iterate through monthly columns (assuming they start from index 2)
            for col_idx in range(2, len(row)):
                # Assuming column headers are dates or can be parsed into dates
                # This is a simplification. A robust solution would parse headers carefully.
                try:
                    # Attempt to parse column header as a date (e.g., '2024-01-01')
                    # Or you might have 'Jan-24', 'Feb-24' etc.
                    # For now, let's assume column headers are 'YYYY-MM-DD' or similar
                    # If headers are just month names, you'd need to infer year and day
                    header = df.columns[col_idx]
                    if isinstance(header, datetime):
                        period_date = header.date()
                    else:
                        # Try parsing as string, e.g., '2024-01-01'
                        period_date = datetime.strptime(str(header), '%Y-%m-%d').date()

                    budget_value = row.iloc[col_idx]
                    if pd.isna(budget_value): # Handle NaN values
                        budget_value = 0

                    BudgetFinancialData.objects.update_or_create(
                        budget=budget,
                        chart_of_account=coa_entry,
                        period_date=period_date,
                        defaults={'budget_value': budget_value}
                    )
                except (ValueError, TypeError) as e:
                    print(f"Skipping column {df.columns[col_idx]} for GL {gl_code} due to date/value parsing error: {e}")
                    continue

        context = {
            'budgets': budgets,
            'success_message': f'Budget file \'{uploaded_file.name}\' uploaded successfully for {budget.name}. '
                               f'Processed {len(gl_codes_in_file)} GL codes.'
        }

        return render(request, 'consolidation_app/upload_budget.html', context)

    return render(request, 'consolidation_app/upload_budget.html', {'budgets': budgets})

class CompanyList(generics.ListAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

class ChartOfAccountList(generics.ListAPIView):
    queryset = ChartOfAccount.objects.all()
    serializer_class = ChartOfAccountSerializer

class ProjectList(generics.ListAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

class FinancialDataList(generics.ListAPIView):
    queryset = FinancialData.objects.all()
    serializer_class = FinancialDataSerializer

class CompanyListCreateView(generics.ListCreateAPIView):
    queryset = Company.objects.all().order_by("id")
    serializer_class = CompanySerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["name"]
    search_fields = ["name"]
    ordering_fields = ["id", "name"]

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500

class ChartOfAccountListCreateView(generics.ListCreateAPIView):
    queryset = ChartOfAccount.objects.all().order_by("id")
    serializer_class = ChartOfAccountSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["account_number", "account_name", "account_type", "category"]
    search_fields = ["account_number", "account_name", "category"]
    ordering_fields = ["id", "account_number", "account_name"]

class ProjectListCreateView(generics.ListCreateAPIView):
    queryset = Project.objects.all().order_by("id")
    serializer_class = ProjectSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["name"]
    search_fields = ["name"]
    ordering_fields = ["id", "name"]

class FinancialDataListCreateView(generics.ListCreateAPIView):
    queryset = FinancialData.objects.all().order_by("id")
    serializer_class = FinancialDataSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["company", "chart_of_account", "period_date", "project", "is_pnl"]
    search_fields = ["company__name", "chart_of_account__account_name", "project__name"]
    ordering_fields = ["id", "period_date", "company", "chart_of_account"]

class BudgetListCreateView(generics.ListCreateAPIView):
    queryset = Budget.objects.all().order_by("id")
    serializer_class = BudgetSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["name", "company", "project"]
    search_fields = ["name", "company__name", "project__name"]
    ordering_fields = ["id", "name"]

class BudgetFinancialDataListCreateView(generics.ListCreateAPIView):
    queryset = BudgetFinancialData.objects.all().order_by("id")
    serializer_class = BudgetFinancialDataSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["budget", "chart_of_account", "period_date"]
    search_fields = ["budget__name", "chart_of_account__account_name"]
    ordering_fields = ["id", "period_date", "budget", "chart_of_account"]

class AllocationRuleListCreateView(generics.ListCreateAPIView):
    queryset = AllocationRule.objects.all().order_by("id")
    serializer_class = AllocationRuleSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["name", "company", "source_account"]
    search_fields = ["name", "company__name", "source_account__account_name"]
    ordering_fields = ["id", "name", "company"]
