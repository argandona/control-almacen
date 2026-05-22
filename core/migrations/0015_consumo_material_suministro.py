from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_tipotrabajomanodeobra'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsumoMaterialSuministro',
            fields=[
                ('id_consumo_material', models.AutoField(primary_key=True, serialize=False)),
                ('cantidad', models.DecimalField(
                    max_digits=10, decimal_places=2,
                    validators=[django.core.validators.MinValueValidator(0)],
                )),
                ('fecha', models.DateField(auto_now_add=True)),
                ('liquidacion', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='materiales_consumidos',
                    to='core.liquidacionsuministro',
                )),
                ('material', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='consumos_suministro',
                    to='core.material',
                )),
                ('suministro', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='consumos_material',
                    to='core.suministro',
                )),
                ('usuario', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='consumos_suministro',
                    to='core.usuario',
                )),
            ],
            options={'db_table': 'consumo_material_suministro'},
        ),
    ]
