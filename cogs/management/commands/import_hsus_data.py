import csv
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from cogs.models import HTSUSCode, SKU

class Command(BaseCommand):
    help = 'Imports HTSUSCode and SKU data from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The path to the CSV file to import.')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']

        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    htsus_code_str = row.get('HTSUS_Code')
                    htsus_description = row.get('HTSUS_Description', '')
                    htsus_rate_pct_str = row.get('HTSUS_Rate_Pct')
                    sku_str = row.get('SKU')
                    sku_name = row.get('SKU_Name', '')
                    sku_htsus_rate_pct_str = row.get('SKU_HTSUS_Rate_Pct')

                    if not htsus_code_str or not htsus_rate_pct_str or not sku_str:
                        self.stdout.write(self.style.WARNING(f"Skipping row due to missing required data: {row}"))
                        continue

                    try:
                        htsus_rate_pct = Decimal(htsus_rate_pct_str)
                    except Exception:
                        self.stdout.write(self.style.ERROR(f"Invalid HTSUS_Rate_Pct for HTSUS_Code {htsus_code_str}: {htsus_rate_pct_str}"))
                        continue

                    htsus_obj, created = HTSUSCode.objects.update_or_create(
                        code=htsus_code_str,
                        defaults={
                            'description': htsus_description,
                            'rate_pct': htsus_rate_pct
                        }
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"Created HTSUSCode: {htsus_obj.code}"))
                    else:
                        self.stdout.write(self.style.SUCCESS(f"Updated HTSUSCode: {htsus_obj.code}"))

                    sku_defaults = {
                        'name': sku_name,
                        'htsus_code': htsus_obj
                    }
                    if sku_htsus_rate_pct_str:
                        try:
                            sku_defaults['htsus_rate_pct'] = Decimal(sku_htsus_rate_pct_str)
                        except Exception:
                            self.stdout.write(self.style.ERROR(f"Invalid SKU_HTSUS_Rate_Pct for SKU {sku_str}: {sku_htsus_rate_pct_str}"))
                            continue
                    else:
                        sku_defaults['htsus_rate_pct'] = None # Ensure it's set to None if not provided

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

        self.stdout.write(self.style.SUCCESS('Successfully imported HTSUSCode and SKU data.'))