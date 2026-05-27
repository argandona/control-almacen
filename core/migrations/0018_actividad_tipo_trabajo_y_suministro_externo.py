from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_quitar_cantidad_tipotrabajomaterial'),
    ]

    operations = [
        # ActividadTipoTrabajo
        migrations.CreateModel(
            name='ActividadTipoTrabajo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('actividad',    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tipos_trabajo', to='core.actividad')),
                ('tipo_trabajo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='actividades',   to='core.tipotrabajo')),
            ],
            options={'db_table': 'actividad_tipo_trabajo', 'unique_together': {('actividad', 'tipo_trabajo')}},
        ),

        # LiquidacionSuministro: suministro nullable + campos externos
        migrations.AlterField(
            model_name='liquidacionsuministro',
            name='suministro',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='liquidaciones',
                to='core.suministro',
            ),
        ),
        migrations.AddField(
            model_name='liquidacionsuministro',
            name='suministro_externo',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='liquidacionsuministro',
            name='sst_externo',
            field=models.CharField(blank=True, max_length=20),
        ),

        # ConsumoMaterialSuministro: suministro nullable + campo externo
        migrations.AlterField(
            model_name='consumomaterialsuministro',
            name='suministro',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='consumos_material',
                to='core.suministro',
            ),
        ),
        migrations.AddField(
            model_name='consumomaterialsuministro',
            name='suministro_externo',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
