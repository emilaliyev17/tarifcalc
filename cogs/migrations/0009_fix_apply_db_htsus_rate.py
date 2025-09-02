from django.db import migrations, models

def check_and_add_column(apps, schema_editor):
    """Only add column if it doesn't exist"""
    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='cogs_invoice' 
                AND column_name='apply_db_htsus_rate'
                """
            )
            if not cursor.fetchone():
                # Column doesn't exist, add it
                cursor.execute(
                    """
                    ALTER TABLE cogs_invoice 
                    ADD COLUMN apply_db_htsus_rate BOOLEAN DEFAULT TRUE
                    """
                )

class Migration(migrations.Migration):
    dependencies = [
        ('cogs', '0008_add_country_origin_to_invoice'),
    ]

    operations = [
        migrations.RunPython(check_and_add_column, migrations.RunPython.noop),
    ]
