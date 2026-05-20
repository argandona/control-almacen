from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_add_liquidacion_suministro'),
    ]

    operations = [
        migrations.CreateModel(
            name='TipoTrabajoManoDeObra',
            fields=[
                ('id_tipo_trabajo_mano_de_obra', models.AutoField(primary_key=True, serialize=False)),
                ('tipo_trabajo', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='partidas',
                    to='core.tipotrabajo',
                )),
                ('mano_de_obra', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='tipos_trabajo',
                    to='core.manodeobra',
                )),
            ],
            options={'db_table': 'tipo_trabajo_mano_de_obra'},
        ),
        migrations.AlterUniqueTogether(
            name='tipotrabajomanodeobra',
            unique_together={('tipo_trabajo', 'mano_de_obra')},
        ),
    ]
