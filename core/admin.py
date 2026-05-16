from django.contrib import admin
from .models import (
    Empresa, Rol, Usuario, Camion, UsuarioCamion, SST,
    Material, StockCamion, Almacen, StockAlmacen, Proveedor,
    IngresoTecsur, DetalleIngresoTecsur,
    DevolucionTecsur, DetalleDevolucionTecsur,
    MaterialMalogrado, DetalleMaterialMalogrado,
    TransferenciaAlmacen, DetalleTransferencia,
    Pedido, DetallePedido, Devolucion, DetalleDevolucion,
    UploadConsumo, Consumo, DetalleConsumo,
    Inventario, DetalleInventario,
)

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ['nombre','ruc','activo']
    search_fields = ['nombre','ruc']

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ['id_rol','descripcion']

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ['nombre','email','rol','empresa','activo']
    list_filter  = ['rol','activo','empresa']
    search_fields = ['nombre','email']

@admin.register(Camion)
class CamionAdmin(admin.ModelAdmin):
    list_display = ['placa','empresa','activo']

@admin.register(UsuarioCamion)
class UsuarioCamionAdmin(admin.ModelAdmin):
    list_display = ['usuario','camion','fecha_inicio','fecha_fin','activo']

@admin.register(SST)
class SSTAdmin(admin.ModelAdmin):
    list_display = ['distrito','actividad','empresa']

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display  = ['matricula','descripcion','precio']
    search_fields = ['matricula','descripcion']

admin.register(StockCamion)(type('StockCamionAdmin', (admin.ModelAdmin,), {'list_display': ['camion','material','cantidad']}))
admin.register(Almacen)(type('AlmacenAdmin', (admin.ModelAdmin,), {'list_display': ['nombre','empresa','activo']}))
admin.register(StockAlmacen)(type('StockAlmacenAdmin', (admin.ModelAdmin,), {'list_display': ['almacen','material','cantidad']}))
admin.register(Proveedor)(type('ProveedorAdmin', (admin.ModelAdmin,), {'list_display': ['nombre','ruc','activo']}))

class DetalleIngresoInline(admin.TabularInline):
    model = DetalleIngresoTecsur; extra = 0
@admin.register(IngresoTecsur)
class IngresoTecsurAdmin(admin.ModelAdmin):
    list_display = ['folio','almacen','proveedor','fecha']
    inlines = [DetalleIngresoInline]

class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido; extra = 0
@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ['id_pedido','camion','usuario','estado','fecha']
    list_filter  = ['estado']
    inlines = [DetallePedidoInline]

class DetalleDevolucionInline(admin.TabularInline):
    model = DetalleDevolucion; extra = 0
@admin.register(Devolucion)
class DevolucionAdmin(admin.ModelAdmin):
    list_display = ['id_devolucion','camion','usuario','estado','fecha']
    list_filter  = ['estado']
    inlines = [DetalleDevolucionInline]

admin.register(UploadConsumo)(type('UploadConsumoAdmin', (admin.ModelAdmin,), {'list_display': ['sst','usuario','estado','fecha_upload']}))
admin.register(Inventario)(type('InventarioAdmin', (admin.ModelAdmin,), {'list_display': ['id_inventario','camion','almacen','mes','anio','estado']}))
