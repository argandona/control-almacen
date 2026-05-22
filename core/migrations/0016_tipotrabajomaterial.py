from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_consumo_material_suministro'),
    ]

    operations = [
        migrations.CreateModel(
            name='TipoTrabajoMaterial',
            fields=[
                ('id_tipo_trabajo_material', models.AutoField(primary_key=True, serialize=False)),
                ('cantidad', models.DecimalField(
                    max_digits=10, decimal_places=2,
                    validators=[django.core.validators.MinValueValidator(0)],
                )),
                ('material', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='tipos_trabajo',
                    to='core.material',
                )),
                ('tipo_trabajo', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='materiales',
                    to='core.tipotrabajo',
                )),
            ],
            options={
                'db_table': 'tipo_trabajo_material',
                'unique_together': {('tipo_trabajo', 'material')},
            },
        ),
    ]
