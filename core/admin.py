import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse

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


# ── Mixin Excel ───────────────────────────────────────────────────────────────
class ExcelImportMixin:
    """
    Añade dos botones al listado del admin:
      • Importar Excel  → sube un .xlsx y crea/actualiza registros
      • Descargar Plantilla → descarga un .xlsx con los encabezados correctos

    Subclases deben definir:
      excel_fields = [("campo_modelo", "Encabezado Excel"), ...]
    e implementar:
      def import_row(self, data: dict): ...
    """
    excel_fields: list = []
    change_list_template = "admin/excel_changelist.html"

    def get_urls(self):
        from django.urls import path
        mn = self.model._meta.model_name
        return [
            path("import-excel/",      self.admin_site.admin_view(self.import_excel_view),      name=f"{mn}_import_excel"),
            path("download-template/", self.admin_site.admin_view(self.download_template_view), name=f"{mn}_download_template"),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        mn  = self.model._meta.model_name
        ctx = extra_context or {}
        ctx["import_excel_url"]      = reverse(f"admin:{mn}_import_excel")
        ctx["download_template_url"] = reverse(f"admin:{mn}_download_template")
        return super().changelist_view(request, extra_context=ctx)

    # ── Descarga de plantilla ─────────────────────────────────────────────────
    def download_template_view(self, request):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Datos"
        headers = [label for _, label in self.excel_fields]
        ws.append(headers)
        for col, cell in enumerate(ws[1], 1):
            cell.font      = Font(bold=True, color="FFFFFF")
            cell.fill      = PatternFill("solid", fgColor="2563EB")
            cell.alignment = Alignment(horizontal="center")
            ws.column_dimensions[cell.column_letter].width = max(16, len(headers[col - 1]) + 4)
        ws.freeze_panes = "A2"

        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        mn = self.model._meta.model_name
        response["Content-Disposition"] = f'attachment; filename="plantilla_{mn}.xlsx"'
        wb.save(response)
        return response

    # ── Importación desde Excel ───────────────────────────────────────────────
    def import_excel_view(self, request):
        if request.method == "POST":
            archivo = request.FILES.get("archivo")
            if not archivo:
                messages.error(request, "Selecciona un archivo Excel (.xlsx).")
                return redirect(".")
            try:
                wb   = openpyxl.load_workbook(archivo, data_only=True)
                rows = list(wb.active.iter_rows(values_only=True))
            except Exception as exc:
                messages.error(request, f"Error al leer el archivo: {exc}")
                return redirect(".")
            if len(rows) < 2:
                messages.error(request, "El archivo no contiene datos (solo encabezado).")
                return redirect(".")

            creados = errores = 0
            for num, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                data = {
                    field: (row[i] if i < len(row) else None)
                    for i, (field, _) in enumerate(self.excel_fields)
                }
                try:
                    self.import_row(data)
                    creados += 1
                except Exception as exc:
                    messages.warning(request, f"Fila {num}: {exc}")
                    errores += 1

            if creados:
                messages.success(request, f"{creados} registro(s) importado(s) correctamente.")
            if errores:
                messages.error(request, f"{errores} fila(s) con error — revisa las advertencias.")
            return redirect("..")

        context = {
            **self.admin_site.each_context(request),
            "title":  f"Importar {self.model._meta.verbose_name_plural}",
            "opts":   self.model._meta,
            "fields": self.excel_fields,
        }
        return render(request, "admin/excel_import_form.html", context)

    def import_row(self, data: dict):
        raise NotImplementedError("Implementa import_row() en tu ModelAdmin.")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _str(val, default=""):
    return str(val).strip() if val is not None else default


# ── Empresa ───────────────────────────────────────────────────────────────────
@admin.register(Empresa)
class EmpresaAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display  = ["nombre", "ruc", "activo"]
    search_fields = ["nombre", "ruc"]
    excel_fields  = [
        ("nombre",    "Nombre"),
        ("ruc",       "RUC"),
        ("direccion", "Dirección"),
        ("telefono",  "Teléfono"),
        ("email",     "Email"),
    ]

    def import_row(self, data):
        Empresa.objects.update_or_create(
            ruc=_str(data["ruc"]),
            defaults={
                "nombre":    _str(data["nombre"]),
                "direccion": _str(data.get("direccion")),
                "telefono":  _str(data.get("telefono")),
                "email":     _str(data.get("email")),
            },
        )


# ── Rol ───────────────────────────────────────────────────────────────────────
@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ["id_rol", "descripcion"]


# ── Usuario ───────────────────────────────────────────────────────────────────
@admin.register(Usuario)
class UsuarioAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display  = ["nombre", "email", "rol", "empresa", "activo"]
    list_filter   = ["rol", "activo", "empresa"]
    search_fields = ["nombre", "email"]
    excel_fields  = [
        ("nombre",   "Nombre completo"),
        ("email",    "Email"),
        ("clave",    "Contraseña"),
        ("rol",      "Rol (ej: Capataz)"),
        ("empresa",  "Empresa (nombre)"),
        ("telefono", "Teléfono"),
    ]

    def import_row(self, data):
        from django.contrib.auth.hashers import make_password
        rol = Rol.objects.get(descripcion__icontains=_str(data["rol"]))
        empresa = None
        if data.get("empresa") and _str(data["empresa"]):
            empresa = Empresa.objects.get(nombre__icontains=_str(data["empresa"]))
        Usuario.objects.update_or_create(
            email=_str(data["email"]),
            defaults={
                "nombre":   _str(data["nombre"]),
                "clave":    make_password(_str(data["clave"])),
                "rol":      rol,
                "empresa":  empresa,
                "telefono": _str(data.get("telefono")),
            },
        )


# ── Camion ────────────────────────────────────────────────────────────────────
@admin.register(Camion)
class CamionAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display = ["placa", "empresa", "activo"]
    excel_fields = [
        ("empresa",     "Empresa (nombre)"),
        ("placa",       "Placa"),
        ("descripcion", "Descripción"),
    ]

    def import_row(self, data):
        empresa = Empresa.objects.get(nombre__icontains=_str(data["empresa"]))
        Camion.objects.update_or_create(
            placa=_str(data["placa"]),
            defaults={
                "empresa":     empresa,
                "descripcion": _str(data.get("descripcion")),
            },
        )


# ── UsuarioCamion ─────────────────────────────────────────────────────────────
@admin.register(UsuarioCamion)
class UsuarioCamionAdmin(admin.ModelAdmin):
    list_display = ["usuario", "camion", "fecha_inicio", "fecha_fin", "activo"]


# ── SST ───────────────────────────────────────────────────────────────────────
@admin.register(SST)
class SSTAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display  = ["codigo", "distrito", "actividad", "empresa"]
    search_fields = ["codigo", "distrito"]
    excel_fields  = [
        ("empresa",   "Empresa (nombre)"),
        ("codigo",    "Código SST"),
        ("distrito",  "Distrito"),
        ("actividad", "Actividad"),
    ]

    def import_row(self, data):
        empresa = Empresa.objects.get(nombre__icontains=_str(data["empresa"]))
        SST.objects.update_or_create(
            codigo=_str(data["codigo"]),
            empresa=empresa,
            defaults={
                "distrito":  _str(data["distrito"]),
                "actividad": _str(data["actividad"]),
            },
        )


# ── Material ──────────────────────────────────────────────────────────────────
@admin.register(Material)
class MaterialAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display  = ["matricula", "descripcion", "precio"]
    search_fields = ["matricula", "descripcion"]
    excel_fields  = [
        ("matricula",   "Matrícula"),
        ("descripcion", "Descripción"),
        ("precio",      "Precio"),
    ]

    def import_row(self, data):
        Material.objects.update_or_create(
            matricula=_str(data["matricula"]),
            defaults={
                "descripcion": _str(data["descripcion"]),
                "precio":      data["precio"],
            },
        )


# ── StockCamion ───────────────────────────────────────────────────────────────
@admin.register(StockCamion)
class StockCamionAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display = ["camion", "material", "cantidad"]
    excel_fields = [
        ("camion",   "Camión (placa)"),
        ("material", "Material (matrícula)"),
        ("cantidad", "Cantidad"),
    ]

    def import_row(self, data):
        camion   = Camion.objects.get(placa=_str(data["camion"]))
        material = Material.objects.get(matricula=_str(data["material"]))
        StockCamion.objects.update_or_create(
            camion=camion, material=material,
            defaults={"cantidad": int(data["cantidad"])},
        )


# ── Almacen ───────────────────────────────────────────────────────────────────
@admin.register(Almacen)
class AlmacenAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display = ["nombre", "empresa", "activo"]
    excel_fields = [
        ("empresa",   "Empresa (nombre)"),
        ("nombre",    "Nombre del almacén"),
        ("direccion", "Dirección"),
    ]

    def import_row(self, data):
        empresa = Empresa.objects.get(nombre__icontains=_str(data["empresa"]))
        Almacen.objects.update_or_create(
            nombre=_str(data["nombre"]), empresa=empresa,
            defaults={"direccion": _str(data.get("direccion"))},
        )


# ── StockAlmacen ──────────────────────────────────────────────────────────────
@admin.register(StockAlmacen)
class StockAlmacenAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display = ["almacen", "material", "cantidad"]
    excel_fields = [
        ("almacen",  "Almacén (nombre)"),
        ("material", "Material (matrícula)"),
        ("cantidad", "Cantidad"),
    ]

    def import_row(self, data):
        almacen  = Almacen.objects.get(nombre__icontains=_str(data["almacen"]))
        material = Material.objects.get(matricula=_str(data["material"]))
        StockAlmacen.objects.update_or_create(
            almacen=almacen, material=material,
            defaults={"cantidad": int(data["cantidad"])},
        )


# ── Proveedor ─────────────────────────────────────────────────────────────────
@admin.register(Proveedor)
class ProveedorAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display  = ["nombre", "ruc", "activo"]
    search_fields = ["nombre", "ruc"]
    excel_fields  = [
        ("nombre",   "Nombre"),
        ("ruc",      "RUC"),
        ("direccion","Dirección"),
        ("telefono", "Teléfono"),
        ("email",    "Email"),
        ("contacto", "Contacto"),
    ]

    def import_row(self, data):
        Proveedor.objects.update_or_create(
            ruc=_str(data["ruc"]),
            defaults={
                "nombre":    _str(data["nombre"]),
                "direccion": _str(data.get("direccion")),
                "telefono":  _str(data.get("telefono")),
                "email":     _str(data.get("email")),
                "contacto":  _str(data.get("contacto")),
            },
        )


# ── IngresoTecsur ─────────────────────────────────────────────────────────────
class DetalleIngresoInline(admin.TabularInline):
    model = DetalleIngresoTecsur
    extra = 0

@admin.register(IngresoTecsur)
class IngresoTecsurAdmin(admin.ModelAdmin):
    list_display = ["folio", "almacen", "proveedor", "fecha"]
    inlines      = [DetalleIngresoInline]


# ── DevolucionTecsur ──────────────────────────────────────────────────────────
class DetalleDevTecsurInline(admin.TabularInline):
    model = DetalleDevolucionTecsur
    extra = 0

@admin.register(DevolucionTecsur)
class DevolucionTecsurAdmin(admin.ModelAdmin):
    list_display = ["folio", "almacen", "proveedor", "fecha"]
    inlines      = [DetalleDevTecsurInline]


# ── MaterialMalogrado ─────────────────────────────────────────────────────────
class DetalleMalogradoInline(admin.TabularInline):
    model = DetalleMaterialMalogrado
    extra = 0

@admin.register(MaterialMalogrado)
class MaterialMalogradoAdmin(admin.ModelAdmin):
    list_display = ["folio_factura", "almacen", "fecha"]
    inlines      = [DetalleMalogradoInline]


# ── TransferenciaAlmacen ──────────────────────────────────────────────────────
class DetalleTransferenciaInline(admin.TabularInline):
    model = DetalleTransferencia
    extra = 0

@admin.register(TransferenciaAlmacen)
class TransferenciaAlmacenAdmin(admin.ModelAdmin):
    list_display = ["almacen_origen", "almacen_destino", "fecha"]
    inlines      = [DetalleTransferenciaInline]


# ── Pedido ────────────────────────────────────────────────────────────────────
class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ["id_pedido", "camion", "usuario", "estado", "fecha"]
    list_filter  = ["estado"]
    inlines      = [DetallePedidoInline]


# ── Devolucion ────────────────────────────────────────────────────────────────
class DetalleDevolucionInline(admin.TabularInline):
    model = DetalleDevolucion
    extra = 0

@admin.register(Devolucion)
class DevolucionAdmin(admin.ModelAdmin):
    list_display = ["id_devolucion", "camion", "usuario", "estado", "fecha"]
    list_filter  = ["estado"]
    inlines      = [DetalleDevolucionInline]


# ── UploadConsumo ─────────────────────────────────────────────────────────────
@admin.register(UploadConsumo)
class UploadConsumoAdmin(admin.ModelAdmin):
    list_display = ["sst", "usuario", "estado", "fecha_upload"]
    list_filter  = ["estado"]


# ── Inventario ────────────────────────────────────────────────────────────────
@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display = ["id_inventario", "camion", "almacen", "mes", "anio", "estado"]
    list_filter  = ["estado"]
