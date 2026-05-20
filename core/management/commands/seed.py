import hashlib
from django.core.management.base import BaseCommand
from core.models import Rol, Usuario, Empresa, Almacen, Camion, Material, Proveedor, SST, Actividad

def h(clave): return hashlib.sha256(clave.encode()).hexdigest()

ROLES = [
    (1, 'SuperAdmin'), (2, 'Admin Empresa'), (3, 'Encargado'),
    (4, 'Capataz'), (5, 'Liquidador'), (6, 'Encargado de Almacén'),
]

class Command(BaseCommand):
    help = 'Carga datos iniciales de prueba'

    def handle(self, *args, **options):
        for id_rol, desc in ROLES:
            Rol.objects.get_or_create(id_rol=id_rol, defaults={'descripcion': desc})
        self.stdout.write('Roles creados')

        if not Usuario.objects.filter(email='super@admin.com').exists():
            Usuario.objects.create(nombre='SuperAdmin', email='super@admin.com', clave=h('admin123'), rol_id=1, empresa=None, activo=True)
        self.stdout.write('SuperAdmin: super@admin.com / admin123')

        empresa, _ = Empresa.objects.get_or_create(ruc='20123456789', defaults={'nombre': 'Contratista Demo SAC', 'activo': True})

        for nombre, email, rol_id in [
            ('Admin Empresa','admin@demo.com',2), ('Encargado Campo','encargado@demo.com',3),
            ('Capataz Cuadrilla','capataz@demo.com',4), ('Liquidador','liquidador@demo.com',5),
            ('Encargado Almacen','almacen@demo.com',6),
        ]:
            if not Usuario.objects.filter(email=email).exists():
                Usuario.objects.create(nombre=nombre, email=email, clave=h('demo123'), rol_id=rol_id, empresa=empresa, activo=True)
        self.stdout.write('Usuarios demo (clave: demo123)')

        almacen, _ = Almacen.objects.get_or_create(empresa=empresa, nombre='Almacen01_Principal', defaults={'direccion': 'Av. Industrial 123', 'activo': True})
        Camion.objects.get_or_create(placa='ABC-123', defaults={'empresa': empresa, 'descripcion': 'Camion demo', 'activo': True})

        for matricula, desc, precio in [
            ('MAT-001','Cable NYY 2x4mm','12.50'), ('MAT-002','Tubo PVC 3/4"','2.80'),
            ('MAT-003','Cinta aislante','1.50'), ('MAT-004','Conector RJ45','0.90'),
            ('MAT-005','Interruptor bipolar','8.00'),
        ]:
            mat, _ = Material.objects.get_or_create(matricula=matricula, defaults={'descripcion': desc, 'precio': precio})
            from core.models import StockAlmacen
            StockAlmacen.objects.get_or_create(almacen=almacen, material=mat, defaults={'cantidad': 100})

        Proveedor.objects.get_or_create(ruc='20456789012', defaults={'nombre': 'Tecsur SA', 'activo': True})
        actividad, _ = Actividad.objects.get_or_create(nombre='Instalacion electrica')
        SST.objects.get_or_create(empresa=empresa, distrito='Miraflores', defaults={'codigo': '3914707', 'actividad': actividad})

        self.stdout.write(self.style.SUCCESS('Seed completado!'))
