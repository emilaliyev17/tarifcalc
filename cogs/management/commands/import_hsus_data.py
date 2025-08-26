import csv
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from cogs.models import HSUSCode, SKU

class Command(BaseCommand):
    help = 'Imports HSUSCode and SKU data from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The path to the CSV file to import.')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']

        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    hsus_code_str = row.get('HSUS_Code')
                    hsus_description = row.get('HSUS_Description', '')
                    hsus_rate_pct_str = row.get('HSUS_Rate_Pct')
                    sku_str = row.get('SKU')
                    sku_name = row.get('SKU_Name', '')
                    sku_hsus_rate_pct_str = row.get('SKU_HSUS_Rate_Pct')

                    if not hsus_code_str or not hsus_rate_pct_str or not sku_str:
                        self.stdout.write(self.style.WARNING(f"Skipping row due to missing required data: {row}"))
                        continue

                    try:
                        hsus_rate_pct = Decimal(hsus_rate_pct_str)
                    except Exception:
                        self.stdout.write(self.style.ERROR(f"Invalid HSUS_Rate_Pct for HSUS_Code {hsus_code_str}: {hsus_rate_pct_str}"))
                        continue

                    hsus_obj, created = HSUSCode.objects.update_or_create(
                        code=hsus_code_str,
                        defaults={
                            'description': hsus_description,
                            'rate_pct': hsus_rate_pct
                        }
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"Created HSUSCode: {hsus_obj.code}"))
                    else:
                        self.stdout.write(self.style.SUCCESS(f"Updated HSUSCode: {hsus_obj.code}"))

                    sku_defaults = {
                        'name': sku_name,
                        'hsus_code': hsus_obj
                    }
                    if sku_hsus_rate_pct_str:
                        try:
                            sku_defaults['hsus_rate_pct'] = Decimal(sku_hsus_rate_pct_str)
                        except Exception:
                            self.stdout.write(self.style.ERROR(f"Invalid SKU_HSUS_Rate_Pct for SKU {sku_str}: {sku_hsus_rate_pct_str}"))
                            continue
                    else:
                        sku_defaults['hsus_rate_pct'] = None # Ensure it's set to None if not provided

                    sku_obj, created = SKU.objects.update_or_create(
                        sku=sku_str,
                        defaults=sku_defaults
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"Created SKU: {sku_obj.sku}"))
                    else:
                        self.stdout.write(self.style.SUCCESS(f"Updated SKU: {sku_obj.sku}"))

        except FileNotFoundError:
            raise CommandError(f'File "{csv_file_path}" does not exist.')
        except Exception as e:
            raise CommandError(f'Error importing data: {e}')

        self.stdout.write(self.style.SUCCESS('Successfully imported HSUSCode and SKU data.'))