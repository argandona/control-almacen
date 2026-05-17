from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_usuario_fcm_token'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='inventario',
            unique_together=set(),
        ),
    ]
