from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_sst_agrega_codigo'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='fcm_token',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
