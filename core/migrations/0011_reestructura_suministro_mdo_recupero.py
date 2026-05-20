# Reescrita manualmente: unique_together se elimina ANTES de quitar campos

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_sst_agrega_numero_sst'),
    ]

    operations = [
        # 1. Eliminar unique_together ANTES de tocar los campos que los componen
        migrations.AlterUniqueTogether(name='partidaejecutada',    unique_together=None),
        migrations.AlterUniqueTogether(name='tipotrabajoejecutado', unique_together=None),
        migrations.AlterUniqueTogether(name='tipotrabajopartida',  unique_together=None),
        migrations.AlterUniqueTogether(name='tipotrabajo',         unique_together=set()),

        # 2. Quitar campos de los modelos a eliminar
        migrations.RemoveField(model_name='partidaejecutada',    name='mano_de_obra'),
        migrations.RemoveField(model_name='partidaejecutada',    name='tipo_trabajo_ejecutado'),
        migrations.RemoveField(model_name='tipotrabajoejecutado', name='liquidacion'),
        migrations.RemoveField(model_name='tipotrabajoejecutado', name='tipo_trabajo'),
        migrations.RemoveField(model_name='tipotrabajopartida',  name='mano_de_obra'),
        migrations.RemoveField(model_name='tipotrabajopartida',  name='tipo_trabajo'),

        # 3. Eliminar modelos obsoletos
        migrations.DeleteModel(name='LiquidacionSuministro'),
        migrations.DeleteModel(name='PartidaEjecutada'),
        migrations.DeleteModel(name='TipoTrabajoEjecutado'),
        migrations.DeleteModel(name='TipoTrabajoPartida'),

        # 4. Ajustar TipoTrabajo: quitar FK actividad y hacer nombre unique
        migrations.RemoveField(model_name='tipotrabajo', name='actividad'),
        migrations.AlterField(
            model_name='tipotrabajo',
            name='nombre',
            field=models.CharField(max_length=200, unique=True),
        ),

        # 5. Crear nuevos modelos
        migrations.CreateModel(
            name='Recupero',
            fields=[
                ('id_recupero', models.AutoField(primary_key=True, serialize=False)),
                ('matricula',   models.CharField(max_length=50, unique=True)),
                ('descripcion', models.CharField(max_length=200)),
            ],
            options={'db_table': 'recupero'},
        ),
        migrations.CreateModel(
            name='SuministroManoDeObra',
            fields=[
                ('id_suministro_mano_de_obra', models.AutoField(primary_key=True, serialize=False)),
                ('mano_de_obra', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='suministros', to='core.manodeobra')),
                ('suministro',   models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mano_de_obra', to='core.suministro')),
            ],
            options={
                'db_table': 'suministro_mano_de_obra',
                'unique_together': {('suministro', 'mano_de_obra')},
            },
        ),
        migrations.CreateModel(
            name='SuministroRecupero',
            fields=[
                ('id_suministro_recupero', models.AutoField(primary_key=True, serialize=False)),
                ('cantidad', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('fecha',    models.DateField()),
                ('recupero',    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='suministros', to='core.recupero')),
                ('suministro',  models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='recuperos',   to='core.suministro')),
            ],
            options={'db_table': 'suministro_recupero'},
        ),
    ]
