from django.core.management.base import BaseCommand
from django.apps import apps

class Command(BaseCommand):
    help = 'Clears all data from specified models in the cogs app.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('This will delete ALL data from the cogs app models.'))
        self.stdout.write(self.style.WARNING('Are you sure you want to proceed? (yes/no)'))
        
        confirmation = input()

        if confirmation.lower() != 'yes':
            self.stdout.write(self.style.SUCCESS('Operation cancelled.'))
            return

        models_to_clear = [
            'AllocatedCost',
            'CostPool',
            'InvoiceLine',
            'Invoice',
            'Container',
            'SKU',
            'HSUSCode',
        ]

        for model_name in models_to_clear:
            try:
                model = apps.get_model('cogs', model_name)
                count, _ = model.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} {model_name} objects.'))
            except LookupError:
                self.stdout.write(self.style.ERROR(f'Model {model_name} not found.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error deleting {model_name}: {e}'))

        self.stdout.write(self.style.SUCCESS('Database clear operation completed.'))
