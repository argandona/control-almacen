import hashlib
import datetime

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST

from .models import (
    Usuario, Rol, Material, StockCamion,
    UploadConsumo, Consumo, DetalleConsumo,
    SST, UsuarioCamion,
)


# ── Auth helpers ──────────────────────────────────────────────────────────────

ROLES_PERMITIDOS = (Rol.LIQUIDADOR, Rol.ENCARGADO_ALMACEN, Rol.SUPERADMIN)


def _usuario_session(request):
    uid = request.session.get('portal_uid')
    if not uid:
        return None
    try:
        return Usuario.objects.select_related('rol', 'empresa').get(pk=uid, activo=True)
    except Usuario.DoesNotExist:
        return None


def _login_required(view_fn):
    def wrapper(request, *args, **kwargs):
        if not _usuario_session(request):
            return redirect('portal_login')
        return view_fn(request, *args, **kwargs)
    wrapper.__name__ = view_fn.__name__
    return wrapper


# ── Vistas ────────────────────────────────────────────────────────────────────

def portal_login(request):
    if _usuario_session(request):
        return redirect('portal_consumos')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        clave = request.POST.get('clave', '').strip()
        clave_hash = hashlib.sha256(clave.encode()).hexdigest()
        try:
            usuario = Usuario.objects.select_related('rol').get(
                email=email, clave=clave_hash, activo=True
            )
            if usuario.rol_id not in ROLES_PERMITIDOS:
                messages.error(request, 'Tu rol no tiene acceso al portal de consumos.')
            else:
                request.session['portal_uid'] = usuario.id_usuario
                request.session.set_expiry(28800)  # 8 horas
                return redirect('portal_consumos')
        except Usuario.DoesNotExist:
            messages.error(request, 'Correo o contraseña incorrectos.')

    return render(request, 'portal/login.html')


def portal_logout(request):
    request.session.flush()
    return redirect('portal_login')


@_login_required
def portal_consumos(request):
    usuario  = _usuario_session(request)
    resultado = None

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if not archivo:
            messages.error(request, 'Selecciona un archivo Excel (.xlsx).')
        elif not archivo.name.endswith('.xlsx'):
            messages.error(request, 'Solo se aceptan archivos .xlsx')
        else:
            resultado = _procesar_y_aprobar(request, archivo, usuario)

    return render(request, 'portal/consumos.html', {
        'usuario':   usuario,
        'resultado': resultado,
    })


def portal_plantilla(request):
    """Descarga plantilla Excel con todas las matrículas de materiales como columnas."""
    materiales = list(
        Material.objects.order_by('matricula').values_list('matricula', flat=True)
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Consumos'

    header_font  = Font(bold=True, color='FFFFFF', size=10)
    header_fill  = PatternFill('solid', fgColor='1D6A3A')
    mat_fill     = PatternFill('solid', fgColor='155724')
    center       = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin         = Side(style='thin', color='CCCCCC')
    borde        = Border(left=thin, right=thin, top=thin, bottom=thin)

    fixed = ['SST', 'SUMINISTRO', 'FECHA EJECUCION\n(dd/mm/aaaa)', 'TECNICO_EMPLEADO\n(Apellido Nombre)']
    all_headers = fixed + list(materiales)

    ws.row_dimensions[1].height = 36
    for col, h in enumerate(all_headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font      = header_font
        cell.fill      = header_fill if col <= 4 else mat_fill
        cell.alignment = center
        cell.border    = borde
        ws.column_dimensions[cell.column_letter].width = max(13, len(h.split('\n')[0]) + 4)

    # Fila de ejemplo
    ejemplo = ['SST-001', 'S-12345', '15/05/2026', 'GARCIA LOPEZ JUAN'] + [0] * len(materiales)
    for col, val in enumerate(ejemplo, 1):
        cell = ws.cell(row=2, column=col, value=val)
        cell.border    = borde
        cell.alignment = Alignment(horizontal='center')

    # Nota al pie
    ws.cell(row=4, column=1,
            value='⚠ Todas las filas deben pertenecer al mismo código SST. '
                  'Ingresar 0 si no se usó el material.')

    ws.freeze_panes = 'E2'

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="plantilla_consumos.xlsx"'
    wb.save(response)
    return response


# ── Lógica de procesamiento ───────────────────────────────────────────────────

def _procesar_y_aprobar(request, archivo, usuario_upload):
    """
    1. Parsea el Excel y crea/actualiza registros UploadConsumo + Consumo + DetalleConsumo.
    2. Si no hay errores de parseo, intenta aprobar (descontar StockCamion).
    Devuelve un dict con el resultado para mostrar en el template.
    """
    try:
        wb   = openpyxl.load_workbook(archivo, data_only=True)
        rows = list(wb.active.iter_rows(values_only=True))
    except Exception as exc:
        messages.error(request, f'Error al leer el archivo: {exc}')
        return None

    if len(rows) < 2:
        messages.error(request, 'El archivo no contiene datos (solo la fila de encabezado).')
        return None

    header           = rows[0]
    matriculas_excel = [str(h).strip() for h in header[4:] if h is not None]

    materiales_map = {
        m.matricula: m
        for m in Material.objects.filter(matricula__in=matriculas_excel)
    }

    # El SST se lee de la primera fila de datos
    codigo_sst = str(rows[1][0]).strip() if rows[1][0] is not None else ''
    try:
        sst = SST.objects.get(codigo=codigo_sst)
    except SST.DoesNotExist:
        messages.error(request, f'El código SST "{codigo_sst}" no existe en el sistema.')
        return None

    errores_parseo = []
    creados        = 0
    upload         = None

    # ── Paso 1: Crear registros ───────────────────────────────────────────────
    try:
        with transaction.atomic():
            upload, _ = UploadConsumo.objects.get_or_create(
                sst=sst,
                defaults={
                    'usuario':        usuario_upload,
                    'nombre_archivo': archivo.name,
                    'estado':         'pendiente',
                },
            )

            if upload.estado == 'aprobado':
                return {
                    'ya_aprobado': True,
                    'sst':         codigo_sst,
                    'upload':      upload,
                }

            for num_fila, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue

                suministro  = str(row[1]).strip() if row[1] is not None else ''
                fecha_raw   = row[2]
                tecnico_str = str(row[3]).strip().upper() if row[3] is not None else ''
                cantidades  = row[4:]

                # Parsear fecha
                if isinstance(fecha_raw, (datetime.date, datetime.datetime)):
                    fecha = fecha_raw if isinstance(fecha_raw, datetime.date) else fecha_raw.date()
                else:
                    try:
                        fecha = datetime.datetime.strptime(str(fecha_raw).strip(), '%d/%m/%Y').date()
                    except ValueError:
                        errores_parseo.append(f'Fila {num_fila}: fecha inválida "{fecha_raw}" (usa dd/mm/aaaa).')
                        continue

                # Buscar técnico
                qs_tec = Usuario.objects.filter(nombre__icontains=tecnico_str)
                if not qs_tec.exists():
                    errores_parseo.append(f'Fila {num_fila}: técnico "{tecnico_str}" no encontrado.')
                    continue
                if qs_tec.count() > 1:
                    nombres = ', '.join(qs_tec.values_list('nombre', flat=True)[:3])
                    errores_parseo.append(
                        f'Fila {num_fila}: "{tecnico_str}" coincide con varios usuarios ({nombres}…).')
                    continue
                tecnico = qs_tec.first()

                # Buscar camión activo
                camion = UsuarioCamion.camion_activo_de_usuario(tecnico, fecha)
                if not camion:
                    errores_parseo.append(
                        f'Fila {num_fila}: "{tecnico.nombre}" no tiene camión asignado el {fecha:%d/%m/%Y}.')
                    continue

                consumo, nuevo = Consumo.objects.get_or_create(
                    upload=upload,
                    usuario_consume=tecnico,
                    camion=camion,
                    suministro=suministro,
                    fecha=fecha,
                )

                for i, cantidad in enumerate(cantidades):
                    if i >= len(matriculas_excel):
                        break
                    try:
                        qty = int(cantidad) if cantidad not in (None, '') else 0
                    except (TypeError, ValueError):
                        qty = 0
                    if qty == 0:
                        continue
                    material = materiales_map.get(matriculas_excel[i])
                    if not material:
                        errores_parseo.append(
                            f'Fila {num_fila}: matrícula "{matriculas_excel[i]}" no existe.')
                        continue
                    DetalleConsumo.objects.get_or_create(
                        consumo=consumo,
                        material=material,
                        defaults={'cantidad': qty},
                    )

                if nuevo:
                    creados += 1

            if errores_parseo:
                # Si hay errores de parseo abortamos todo para no dejar datos a medias
                raise _ParseError('rollback por errores de parseo')

    except _ParseError:
        return {
            'aprobado':      False,
            'sst':           codigo_sst,
            'archivo':       archivo.name,
            'creados':       0,
            'errores':       errores_parseo,
            'errores_stock': [],
        }
    except Exception as exc:
        messages.error(request, f'Error inesperado al procesar: {exc}')
        return None

    # ── Paso 2: Aprobar y descontar stock ─────────────────────────────────────
    errores_stock = []
    try:
        with transaction.atomic():
            upload.refresh_from_db()
            for consumo in upload.consumos.prefetch_related('detalles__material').select_related('camion'):
                for det in consumo.detalles.all():
                    try:
                        stock = StockCamion.objects.select_for_update().get(
                            camion=consumo.camion, material=det.material
                        )
                        stock.descontar(det.cantidad)
                    except StockCamion.DoesNotExist:
                        errores_stock.append(
                            f'{det.material.matricula} no tiene stock en camión {consumo.camion.placa}.')
                        raise _StockError()
                    except Exception as exc:
                        errores_stock.append(str(exc))
                        raise _StockError()
            upload.estado = 'aprobado'
            upload.save()
    except _StockError:
        pass  # upload queda en 'pendiente', errores_stock describe el problema

    return {
        'aprobado':      upload.estado == 'aprobado',
        'sst':           codigo_sst,
        'archivo':       archivo.name,
        'creados':       creados,
        'errores':       [],
        'errores_stock': errores_stock,
        'upload':        upload,
    }


class _ParseError(Exception):
    pass

class _StockError(Exception):
    pass
