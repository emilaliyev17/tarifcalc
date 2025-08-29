from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('cogs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='apply_db_htsus_rate',
            field=models.BooleanField(default=True, help_text="If False, manual HTSUS rate will be used for this invoice."),
        ),
    ]