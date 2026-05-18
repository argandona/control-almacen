import datetime
import openpyxl
from django.utils import timezone
from django.db import transaction
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from .models import (
    Empresa, Rol, Usuario, Camion, UsuarioCamion, SST,
    Material, StockCamion, Almacen, StockAlmacen, Proveedor,
    IngresoTecsur, DevolucionTecsur, MaterialMalogrado, TransferenciaAlmacen,
    Pedido, DetallePedido, Devolucion, DetalleDevolucion,
    UploadConsumo, Consumo, DetalleConsumo,
    Inventario, DetalleInventario,
)
from .serializers import (
    EmpresaSerializer, RolSerializer,
    UsuarioSerializer, UsuarioCreateSerializer,
    CamionSerializer, UsuarioCamionSerializer, SSTSerializer,
    MaterialSerializer, StockCamionSerializer, AlmacenSerializer, StockAlmacenSerializer,
    ProveedorSerializer,
    IngresoTecsurSerializer, IngresoTecsurCreateSerializer,
    DevolucionTecsurSerializer, DevolucionTecsurCreateSerializer,
    MaterialMalogradoSerializer, MaterialMalogradoCreateSerializer,
    TransferenciaAlmacenSerializer, TransferenciaAlmacenCreateSerializer,
    PedidoSerializer, PedidoCreateSerializer, PedidoAprobarSerializer,
    DevolucionSerializer, DevolucionCreateSerializer, DevolucionAprobarSerializer,
    UploadConsumoSerializer,
    InventarioSerializer, InventarioCreateSerializer,
)


# ── Helper: retorna queryset filtrado por empresa del usuario autenticado ──
def qs_empresa(qs, request, campo='empresa'):
    """
    Si el usuario autenticado es SuperAdmin ve todo.
    Cualquier otro rol solo ve registros de su empresa.
    """
    user = request.user
    # Usamos el usuario de nuestra tabla (no el auth de Django).
    # La autenticación JWT guarda el id_usuario en el token.
    try:
        usuario_obj = Usuario.objects.get(pk=user.id_usuario)
        if not usuario_obj.es_superadmin() and usuario_obj.empresa_id:
            return qs.filter(**{campo: usuario_obj.empresa_id})
    except (AttributeError, Usuario.DoesNotExist):
        pass
    return qs


# ── Empresa ─────────────────────────────────────────────────────────────────
class EmpresaViewSet(viewsets.ModelViewSet):
    serializer_class   = EmpresaSerializer
    queryset           = Empresa.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return qs_empresa(super().get_queryset(), self.request, 'id_empresa')


# ── Rol ─────────────────────────────────────────────────────────────────────
class RolViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class   = RolSerializer
    queryset           = Rol.objects.all()
    permission_classes = [permissions.IsAuthenticated]


# ── Usuario ─────────────────────────────────────────────────────────────────
class UsuarioViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return UsuarioCreateSerializer
        return UsuarioSerializer

    def get_queryset(self):
        return qs_empresa(Usuario.objects.select_related('rol','empresa'), self.request)

    @action(detail=False, methods=['post'])
    def fcm_token(self, request):
        """POST /api/usuarios/fcm_token/ — guarda el token FCM del usuario autenticado."""
        token = request.data.get('token')
        if not token:
            return Response({'detail': 'token requerido'}, status=400)
        Usuario.objects.filter(pk=request.user.id_usuario).update(fcm_token=token)
        return Response({'status': 'ok'})

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Devuelve los datos del usuario autenticado."""
        try:
            usuario = Usuario.objects.select_related('rol','empresa').get(pk=request.user.id_usuario)
            serializer = UsuarioSerializer(usuario)
            return Response(serializer.data)
        except Usuario.DoesNotExist:
            return Response({'detail': 'No encontrado.'}, status=404)


# ── Camion ──────────────────────────────────────────────────────────────────
class CamionViewSet(viewsets.ModelViewSet):
    serializer_class   = CamionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return qs_empresa(Camion.objects.select_related('empresa'), self.request)


# ── UsuarioCamion ────────────────────────────────────────────────────────────
class UsuarioCamionViewSet(viewsets.ModelViewSet):
    serializer_class   = UsuarioCamionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UsuarioCamion.objects.select_related('camion','usuario').all()

    @action(detail=False, methods=['get'])
    def camion_activo(self, request):
        """GET /api/usuario-camion/camion_activo/?usuario=<id>"""
        usuario_id = request.query_params.get('usuario')
        if not usuario_id:
            return Response({'detail': 'Parámetro usuario requerido.'}, status=400)
        try:
            usuario = Usuario.objects.get(pk=usuario_id)
        except Usuario.DoesNotExist:
            return Response({'detail': 'Usuario no encontrado.'}, status=404)
        camion = UsuarioCamion.camion_activo_de_usuario(usuario)
        if camion:
            return Response(CamionSerializer(camion).data)
        return Response({'detail': 'Sin camión asignado.'}, status=404)


# ── SST ─────────────────────────────────────────────────────────────────────
class SSTViewSet(viewsets.ModelViewSet):
    serializer_class   = SSTSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return qs_empresa(SST.objects.select_related('empresa'), self.request)


# ── Material ─────────────────────────────────────────────────────────────────
class MaterialViewSet(viewsets.ModelViewSet):
    serializer_class   = MaterialSerializer
    queryset           = Material.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(descripcion__icontains=q) | qs.filter(matricula__icontains=q)
        return qs

    @action(detail=False, methods=['get'])
    def resumen_stock(self, request):
        """
        GET /api/materiales/resumen_stock/
        Saldo real desde StockCamion (fuente de verdad, se actualiza al cerrar inventario).
        Los conteos de pedidos/consumos/devoluciones son informativos históricos.
        """
        from django.db.models import Sum, Q, IntegerField
        from django.db.models.functions import Coalesce
        from django.db.models import Value

        try:
            usr = Usuario.objects.get(pk=request.user.id_usuario)
            empresa_id = usr.empresa_id
        except (AttributeError, Usuario.DoesNotExist):
            empresa_id = None

        # Saldo real = suma de StockCamion por material (actualizado con inventarios físicos)
        stock_filter = Q(camion__empresa_id=empresa_id) if empresa_id else Q()
        stock_map = {
            row['material_id']: row['total']
            for row in (StockCamion.objects
                        .filter(stock_filter)
                        .values('material_id')
                        .annotate(total=Sum('cantidad')))
        }

        if not stock_map:
            return Response([])

        # Conteos históricos informativos para el modal de detalle
        eq_p = Q(detalles_pedido__pedido__camion__empresa_id=empresa_id) if empresa_id else Q()
        eq_d = Q(detalles_devolucion__devolucion__camion__empresa_id=empresa_id) if empresa_id else Q()
        eq_c = Q(detalles_consumo__consumo__camion__empresa_id=empresa_id) if empresa_id else Q()

        out = IntegerField()
        materiales = Material.objects.filter(id_material__in=stock_map.keys()).annotate(
            total_pedidos=Coalesce(
                Sum('detalles_pedido__cantidad_aprobada',
                    filter=Q(detalles_pedido__pedido__estado='aprobado') & eq_p),
                Value(0), output_field=out,
            ),
            total_devoluciones=Coalesce(
                Sum('detalles_devolucion__cantidad_aprobada',
                    filter=Q(detalles_devolucion__devolucion__estado='aprobado') & eq_d),
                Value(0), output_field=out,
            ),
            total_consumos=Coalesce(
                Sum('detalles_consumo__cantidad',
                    filter=Q(detalles_consumo__consumo__upload__estado='aprobado') & eq_c),
                Value(0), output_field=out,
            ),
        ).order_by('matricula')

        data = []
        for m in materiales:
            saldo = stock_map.get(m.id_material, 0)
            if saldo > 0:
                data.append({
                    'id_material':        m.id_material,
                    'matricula':          m.matricula,
                    'descripcion':        m.descripcion,
                    'total_pedidos':      m.total_pedidos,
                    'total_devoluciones': m.total_devoluciones,
                    'total_consumos':     m.total_consumos,
                    'saldo_actual':       saldo,
                })
        return Response(data)


# ── StockCamion ──────────────────────────────────────────────────────────────
class StockCamionViewSet(viewsets.ModelViewSet):
    serializer_class   = StockCamionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = StockCamion.objects.select_related('camion','material')
        camion_id = self.request.query_params.get('camion')
        if camion_id:
            qs = qs.filter(camion_id=camion_id)
        return qs

    @action(detail=False, methods=['get'])
    def por_camion(self, request):
        """
        GET /api/stock-camion/por_camion/
        Devuelve camiones agrupados con sus materiales en stock (cantidad > 0).
        ?usuario=<id>  → solo camiones asignados a ese usuario
        """
        from datetime import date
        from django.db.models import Q

        usuario_id = request.query_params.get('usuario')

        # Encargado ve solo materiales con stock > 0 (su vista no muestra negativos).
        # Enc. almacén (sin usuario_id) ve todo, incluyendo negativos.
        if usuario_id:
            ids = UsuarioCamion.objects.filter(
                usuario_id=usuario_id
            ).values_list('camion_id', flat=True).distinct()
            qs = StockCamion.objects.filter(
                cantidad__gt=0, camion_id__in=ids
            ).select_related('camion', 'material').order_by('material__matricula')
        else:
            qs = (StockCamion.objects.exclude(cantidad=0)
                  .select_related('camion', 'material')
                  .order_by('material__matricula'))

        hoy = date.today()
        asignaciones = {
            a.camion_id: a.usuario.nombre
            for a in UsuarioCamion.objects.filter(
                activo=True, fecha_inicio__lte=hoy
            ).filter(
                Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy)
            ).select_related('usuario')
        }

        camiones = {}
        for stock in qs:
            cid = stock.camion_id
            if cid not in camiones:
                camiones[cid] = {
                    'camion_id':      cid,
                    'placa':          stock.camion.placa,
                    'usuario_nombre': asignaciones.get(cid, 'Sin asignar'),
                    'items':          [],
                }
            camiones[cid]['items'].append({
                'material_id': stock.material_id,
                'matricula':   stock.material.matricula,
                'descripcion': stock.material.descripcion,
                'cantidad':    stock.cantidad,
            })

        # Agregar cuánto hay en devoluciones pendientes por (camion, material)
        from django.db.models import Sum as _Sum
        camion_ids = list(camiones.keys())
        pending_map = {}
        for row in (DetalleDevolucion.objects
                    .filter(devolucion__estado='pendiente',
                            devolucion__camion_id__in=camion_ids)
                    .values('devolucion__camion_id', 'material_id')
                    .annotate(total=_Sum('cantidad_solicitada'))):
            pending_map[(row['devolucion__camion_id'], row['material_id'])] = row['total']

        for cid, camion_data in camiones.items():
            for item in camion_data['items']:
                item['pendiente_devolucion'] = pending_map.get((cid, item['material_id']), 0)

        return Response(list(camiones.values()))


# ── Almacen ──────────────────────────────────────────────────────────────────
class AlmacenViewSet(viewsets.ModelViewSet):
    serializer_class   = AlmacenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return qs_empresa(Almacen.objects.select_related('empresa'), self.request)


# ── StockAlmacen ─────────────────────────────────────────────────────────────
class StockAlmacenViewSet(viewsets.ModelViewSet):
    serializer_class   = StockAlmacenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = StockAlmacen.objects.select_related('almacen','material')
        almacen_id = self.request.query_params.get('almacen')
        if almacen_id:
            qs = qs.filter(almacen_id=almacen_id)
        return qs


# ── Proveedor ─────────────────────────────────────────────────────────────────
class ProveedorViewSet(viewsets.ModelViewSet):
    serializer_class   = ProveedorSerializer
    queryset           = Proveedor.objects.all()
    permission_classes = [permissions.IsAuthenticated]


# ── IngresoTecsur ─────────────────────────────────────────────────────────────
class IngresoTecsurViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return IngresoTecsurCreateSerializer
        return IngresoTecsurSerializer

    def get_queryset(self):
        return IngresoTecsur.objects.prefetch_related('detalles__material').select_related('almacen','proveedor','usuario')


# ── DevolucionTecsur ──────────────────────────────────────────────────────────
class DevolucionTecsurViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return DevolucionTecsurCreateSerializer
        return DevolucionTecsurSerializer

    def get_queryset(self):
        return DevolucionTecsur.objects.prefetch_related('detalles__material').select_related('almacen','proveedor','usuario')


# ── MaterialMalogrado ─────────────────────────────────────────────────────────
class MaterialMalogradoViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return MaterialMalogradoCreateSerializer
        return MaterialMalogradoSerializer

    def get_queryset(self):
        return MaterialMalogrado.objects.prefetch_related('detalles__material').select_related('almacen','proveedor','usuario')


# ── TransferenciaAlmacen ──────────────────────────────────────────────────────
class TransferenciaAlmacenViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return TransferenciaAlmacenCreateSerializer
        return TransferenciaAlmacenSerializer

    def get_queryset(self):
        return TransferenciaAlmacen.objects.prefetch_related('detalles__material').select_related('almacen_origen','almacen_destino','usuario')


# ── Pedido ────────────────────────────────────────────────────────────────────
class PedidoViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return PedidoCreateSerializer
        if self.action == 'aprobar':
            return PedidoAprobarSerializer
        return PedidoSerializer

    def perform_create(self, serializer):
        from .fcm import send_notification
        pedido = serializer.save()
        empresa_id = pedido.usuario.empresa_id
        tokens = list(
            Usuario.objects.filter(rol_id=Rol.ENCARGADO_ALMACEN, empresa_id=empresa_id, activo=True)
            .exclude(fcm_token__isnull=True).exclude(fcm_token='')
            .values_list('fcm_token', flat=True)
        )
        send_notification(
            tokens,
            title='Nuevo pedido por despachar',
            body=f'{pedido.usuario.nombre} solicitó materiales para el camión {pedido.camion.placa}.',
            data={'tipo': 'pedido_nuevo', 'pedido_id': str(pedido.pk)},
        )

    def get_queryset(self):
        qs = Pedido.objects.prefetch_related('detalles__material').select_related('camion','usuario','almacen','usuario_aprueba')
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        camion = self.request.query_params.get('camion')
        if camion:
            qs = qs.filter(camion_id=camion)
        try:
            usr = Usuario.objects.get(pk=self.request.user.id_usuario)
            if usr.rol_id in (Rol.ENCARGADO, Rol.CAPATAZ):
                qs = qs.filter(usuario_id=usr.pk)
        except (AttributeError, Usuario.DoesNotExist):
            pass
        return qs

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        """
        POST /api/pedidos/<id>/aprobar/
        Body: { accion, usuario_aprueba, almacen, observacion, detalles:[{material,cantidad_aprobada}] }
        """
        pedido = self.get_object()
        serializer = PedidoAprobarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if pedido.estado != 'pendiente':
            return Response({'detail': 'Solo se puede procesar pedidos pendientes.'}, status=400)

        with transaction.atomic():
            if data['accion'] == 'rechazar':
                pedido.estado          = 'rechazado'
                pedido.usuario_aprueba = data['usuario_aprueba']
                pedido.observacion     = data.get('observacion', pedido.observacion)
                pedido.fecha_aprobacion = timezone.now().date()
                pedido.save()
                from .fcm import send_notification
                token = pedido.usuario.fcm_token
                if token:
                    send_notification([token], title='Pedido rechazado',
                        body=f'Tu pedido para el camión {pedido.camion.placa} fue rechazado.',
                        data={'tipo': 'pedido_rechazado', 'pedido_id': str(pedido.pk)})
                return Response({'detail': 'Pedido rechazado.'})

            # Aprobar
            almacen = data.get('almacen')
            if not almacen:
                return Response({'detail': 'Se requiere almacen para aprobar.'}, status=400)

            for det_data in data.get('detalles', []):
                det = DetallePedido.objects.get(pedido=pedido, material=det_data['material'])
                cant_aprobada = det_data.get('cantidad_aprobada', 0)
                # Validar stock
                try:
                    stock = StockAlmacen.objects.get(almacen=almacen, material=det.material)
                    stock.descontar(cant_aprobada)
                except StockAlmacen.DoesNotExist:
                    return Response({'detail': f'Sin stock de {det.material} en el almacén.'}, status=400)
                # Subir stock camion
                stock_camion, _ = StockCamion.objects.get_or_create(
                    camion=pedido.camion, material=det.material, defaults={'cantidad': 0}
                )
                stock_camion.agregar(cant_aprobada)
                det.cantidad_aprobada = cant_aprobada
                det.save()

            pedido.estado           = 'aprobado'
            pedido.almacen          = almacen
            pedido.usuario_aprueba  = data['usuario_aprueba']
            pedido.fecha_aprobacion = timezone.now().date()
            pedido.observacion      = data.get('observacion', pedido.observacion)
            pedido.save()

        from .fcm import send_notification
        token = pedido.usuario.fcm_token
        if token:
            send_notification([token], title='Pedido despachado',
                body=f'Tu pedido para el camión {pedido.camion.placa} fue aprobado.',
                data={'tipo': 'pedido_aprobado', 'pedido_id': str(pedido.pk)})
        return Response(PedidoSerializer(pedido).data)


# ── Devolucion ────────────────────────────────────────────────────────────────
class DevolucionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return DevolucionCreateSerializer
        if self.action == 'aprobar':
            return DevolucionAprobarSerializer
        return DevolucionSerializer

    def perform_create(self, serializer):
        from .fcm import send_notification
        devolucion = serializer.save()
        empresa_id = devolucion.usuario.empresa_id
        tokens = list(
            Usuario.objects.filter(rol_id=Rol.ENCARGADO_ALMACEN, empresa_id=empresa_id, activo=True)
            .exclude(fcm_token__isnull=True).exclude(fcm_token='')
            .values_list('fcm_token', flat=True)
        )
        send_notification(
            tokens,
            title='Nueva devolución por aprobar',
            body=f'{devolucion.usuario.nombre} devuelve materiales del camión {devolucion.camion.placa}.',
            data={'tipo': 'devolucion_nueva', 'devolucion_id': str(devolucion.pk)},
        )

    def get_queryset(self):
        qs = Devolucion.objects.prefetch_related('detalles__material').select_related('camion','usuario','almacen_destino','usuario_aprueba')
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        try:
            usr = Usuario.objects.get(pk=self.request.user.id_usuario)
            if usr.rol_id in (Rol.ENCARGADO, Rol.CAPATAZ):
                qs = qs.filter(usuario_id=usr.pk)
        except (AttributeError, Usuario.DoesNotExist):
            pass
        return qs

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        """
        POST /api/devoluciones/<id>/aprobar/
        Body: { accion, usuario_aprueba, almacen_destino, observacion, detalles }
        """
        devolucion = self.get_object()
        serializer = DevolucionAprobarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if devolucion.estado != 'pendiente':
            return Response({'detail': 'Solo se puede procesar devoluciones pendientes.'}, status=400)

        with transaction.atomic():
            if data['accion'] == 'rechazar':
                devolucion.estado           = 'rechazado'
                devolucion.usuario_aprueba  = data['usuario_aprueba']
                devolucion.observacion      = data.get('observacion', devolucion.observacion)
                devolucion.fecha_aprobacion = timezone.now().date()
                devolucion.save()
                from .fcm import send_notification
                token = devolucion.usuario.fcm_token
                if token:
                    send_notification([token], title='Devolución rechazada',
                        body=f'Tu devolución del camión {devolucion.camion.placa} fue rechazada.',
                        data={'tipo': 'devolucion_rechazada', 'devolucion_id': str(devolucion.pk)})
                return Response({'detail': 'Devolución rechazada.'})

            almacen_destino = data.get('almacen_destino')
            if not almacen_destino:
                return Response({'detail': 'Se requiere almacen_destino para aprobar.'}, status=400)

            for det_data in data.get('detalles', []):
                det = DetalleDevolucion.objects.get(devolucion=devolucion, material=det_data['material'])
                cant_aprobada = det_data.get('cantidad_aprobada', 0)
                # Descontar del camion
                try:
                    stock_camion = StockCamion.objects.get(camion=devolucion.camion, material=det.material)
                    stock_camion.descontar(cant_aprobada)
                except StockCamion.DoesNotExist:
                    return Response({'detail': f'Sin stock de {det.material} en el camión.'}, status=400)
                # Subir al almacén
                stock_alm, _ = StockAlmacen.objects.get_or_create(
                    almacen=almacen_destino, material=det.material, defaults={'cantidad': 0}
                )
                stock_alm.agregar(cant_aprobada)
                det.cantidad_aprobada = cant_aprobada
                det.save()

            devolucion.estado           = 'aprobado'
            devolucion.almacen_destino  = almacen_destino
            devolucion.usuario_aprueba  = data['usuario_aprueba']
            devolucion.fecha_aprobacion = timezone.now().date()
            devolucion.observacion      = data.get('observacion', devolucion.observacion)
            devolucion.save()
        from .fcm import send_notification
        token = devolucion.usuario.fcm_token
        if token:
            send_notification([token], title='Devolución aprobada',
                body=f'Tu devolución del camión {devolucion.camion.placa} fue aprobada.',
                data={'tipo': 'devolucion_aprobada', 'devolucion_id': str(devolucion.pk)})
        return Response(DevolucionSerializer(devolucion).data)


# ── UploadConsumo ─────────────────────────────────────────────────────────────
class UploadConsumoViewSet(viewsets.ModelViewSet):
    serializer_class   = UploadConsumoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UploadConsumo.objects.prefetch_related('consumos__detalles__material').select_related('sst','usuario')

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        """POST /api/uploads-consumo/<id>/aprobar/ — descuenta StockCamion por cada DetalleConsumo."""
        upload = self.get_object()
        if upload.estado != 'pendiente':
            return Response({'detail': 'Solo se puede aprobar uploads pendientes.'}, status=400)
        with transaction.atomic():
            for consumo in upload.consumos.prefetch_related('detalles__material'):
                for det in consumo.detalles.all():
                    try:
                        stock = StockCamion.objects.get(camion=consumo.camion, material=det.material)
                        stock.descontar(det.cantidad)
                    except StockCamion.DoesNotExist:
                        return Response({'detail': f'Sin stock de {det.material} en camión {consumo.camion}.'}, status=400)
            upload.estado = 'aprobado'
            upload.save()
        return Response({'detail': 'Consumo aprobado y stock descontado.'})

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        upload = self.get_object()
        if upload.estado != 'pendiente':
            return Response({'detail': 'Solo se puede rechazar uploads pendientes.'}, status=400)
        upload.estado = 'rechazado'
        upload.save()
        return Response({'detail': 'Consumo rechazado.'})

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser])
    def procesar_excel(self, request):
        """
        POST /api/uploads-consumo/procesar_excel/
        Multipart: archivo (xlsx), usuario (id)

        Columnas esperadas:
          SST | SUMINISTRO | FECHA EJECUCION | TECNICO_EMPLEADO | MAT1 | MAT2 | ...
        """
        archivo    = request.FILES.get('archivo')
        usuario_id = request.data.get('usuario')

        if not archivo:
            return Response({'detail': 'Se requiere el archivo Excel.'}, status=400)
        if not usuario_id:
            return Response({'detail': 'Se requiere el parámetro usuario.'}, status=400)

        try:
            usuario_upload = Usuario.objects.get(pk=usuario_id)
        except Usuario.DoesNotExist:
            return Response({'detail': 'Usuario no encontrado.'}, status=404)

        # ── Leer Excel ────────────────────────────────────────────────────────
        try:
            wb   = openpyxl.load_workbook(archivo, data_only=True)
            ws   = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception as exc:
            return Response({'detail': f'Error al leer el archivo: {exc}'}, status=400)

        if len(rows) < 2:
            return Response({'detail': 'El archivo no contiene datos.'}, status=400)

        header             = rows[0]
        matriculas_excel   = [str(h).strip() for h in header[4:] if h is not None]

        # Precargar materiales por matrícula
        materiales = {
            m.matricula: m
            for m in Material.objects.filter(matricula__in=matriculas_excel)
        }

        # ── Obtener SST desde la primera fila de datos ────────────────────────
        codigo_sst = str(rows[1][0]).strip() if rows[1][0] is not None else ''
        try:
            sst = SST.objects.get(codigo=codigo_sst)
        except SST.DoesNotExist:
            return Response({'detail': f'SST con código "{codigo_sst}" no existe en el sistema.'}, status=404)

        errores  = []
        creados  = 0

        with transaction.atomic():
            upload, _ = UploadConsumo.objects.get_or_create(
                sst=sst,
                defaults={
                    'usuario':        usuario_upload,
                    'nombre_archivo': archivo.name,
                    'estado':         'pendiente',
                }
            )

            if upload.estado == 'aprobado':
                return Response({'detail': 'Este SST ya tiene un consumo aprobado.'}, status=400)

            for num_fila, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue

                suministro   = str(row[1]).strip() if row[1] is not None else ''
                fecha_raw    = row[2]
                tecnico_str  = str(row[3]).strip().upper() if row[3] is not None else ''
                cantidades   = row[4:]

                # Parsear fecha
                if isinstance(fecha_raw, (datetime.date, datetime.datetime)):
                    fecha = fecha_raw if isinstance(fecha_raw, datetime.date) else fecha_raw.date()
                else:
                    try:
                        fecha = datetime.datetime.strptime(str(fecha_raw).strip(), '%d/%m/%Y').date()
                    except ValueError:
                        errores.append(f'Fila {num_fila}: fecha inválida "{fecha_raw}".')
                        continue

                # Buscar técnico por nombre (contiene apellido)
                qs_tecnico = Usuario.objects.filter(nombre__icontains=tecnico_str)
                if not qs_tecnico.exists():
                    errores.append(f'Fila {num_fila}: técnico "{tecnico_str}" no encontrado.')
                    continue
                if qs_tecnico.count() > 1:
                    errores.append(f'Fila {num_fila}: técnico "{tecnico_str}" es ambiguo ({qs_tecnico.count()} coincidencias).')
                    continue
                tecnico = qs_tecnico.first()

                # Buscar camión activo del técnico en esa fecha
                camion = UsuarioCamion.camion_activo_de_usuario(tecnico, fecha)
                if not camion:
                    errores.append(f'Fila {num_fila}: "{tecnico_str}" no tiene camión asignado el {fecha}.')
                    continue

                consumo, nuevo = Consumo.objects.get_or_create(
                    upload=upload,
                    usuario_consume=tecnico,
                    camion=camion,
                    suministro=suministro,
                    fecha=fecha,
                )

                # Registrar materiales con cantidad > 0
                for i, cantidad in enumerate(cantidades):
                    if i >= len(matriculas_excel):
                        break
                    if not cantidad or int(cantidad) == 0:
                        continue
                    material = materiales.get(matriculas_excel[i])
                    if not material:
                        errores.append(f'Fila {num_fila}: material "{matriculas_excel[i]}" no existe.')
                        continue
                    DetalleConsumo.objects.get_or_create(
                        consumo=consumo,
                        material=material,
                        defaults={'cantidad': int(cantidad)},
                    )

                if nuevo:
                    creados += 1

        return Response({
            'upload_id':       upload.id_upload,
            'sst':             codigo_sst,
            'archivo':         archivo.name,
            'consumos_creados': creados,
            'errores':         errores,
        }, status=201 if not errores else 207)


# ── Inventario ────────────────────────────────────────────────────────────────
class InventarioViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return InventarioCreateSerializer
        return InventarioSerializer

    def get_queryset(self):
        qs = Inventario.objects.prefetch_related('detalles__material').select_related('camion','almacen','usuario')
        camion  = self.request.query_params.get('camion')
        almacen = self.request.query_params.get('almacen')
        mes     = self.request.query_params.get('mes')
        anio    = self.request.query_params.get('anio')
        if camion:  qs = qs.filter(camion_id=camion)
        if almacen: qs = qs.filter(almacen_id=almacen)
        if mes:     qs = qs.filter(mes=mes)
        if anio:    qs = qs.filter(anio=anio)
        return qs

    @action(detail=False, methods=['post'])
    def iniciar_o_continuar(self, request):
        """
        POST /api/inventarios/iniciar_o_continuar/
        Body: {camion: id, usuario: id}
        Devuelve borrador del mes actual si existe, o crea uno nuevo
        con el stock teórico pre-cargado desde StockCamion.
        """
        from datetime import date as _date
        camion_id  = request.data.get('camion')
        usuario_id = request.data.get('usuario')
        if not camion_id or not usuario_id:
            return Response({'detail': 'Se requiere camion y usuario.'}, status=400)
        try:
            camion  = Camion.objects.get(pk=camion_id)
            usuario = Usuario.objects.get(pk=usuario_id)
        except (Camion.DoesNotExist, Usuario.DoesNotExist):
            return Response({'detail': 'Camión o usuario no encontrado.'}, status=404)

        hoy  = _date.today()
        mes  = hoy.month
        anio = hoy.year

        existente = (Inventario.objects
                     .prefetch_related('detalles__material')
                     .filter(camion=camion, mes=mes, anio=anio, estado='borrador')
                     .first())
        if existente:
            return Response(InventarioSerializer(existente).data)

        with transaction.atomic():
            inventario = Inventario.objects.create(
                camion=camion, usuario=usuario, mes=mes, anio=anio, estado='borrador')
            for sc in StockCamion.objects.filter(camion=camion, cantidad__gt=0).select_related('material').order_by('material__matricula'):
                DetalleInventario.objects.create(
                    inventario=inventario,
                    material=sc.material,
                    cantidad_teorica=sc.cantidad,
                    cantidad_fisica=sc.cantidad,
                    diferencia=0,
                )
        inventario = (Inventario.objects
                      .prefetch_related('detalles__material')
                      .get(pk=inventario.pk))
        return Response(InventarioSerializer(inventario).data, status=201)

    @action(detail=True, methods=['patch'])
    def guardar_conteo(self, request, pk=None):
        """
        PATCH /api/inventarios/{id}/guardar_conteo/
        Body: {detalles: [{id_detalle_inventario: x, cantidad_fisica: y}, ...]}
        """
        inventario = self.get_object()
        if inventario.estado == 'cerrado':
            return Response({'detail': 'No se puede editar un inventario cerrado.'}, status=400)
        with transaction.atomic():
            for d in request.data.get('detalles', []):
                try:
                    det = DetalleInventario.objects.get(
                        pk=d['id_detalle_inventario'], inventario=inventario)
                    det.cantidad_fisica = d.get('cantidad_fisica', det.cantidad_fisica)
                    det.save()
                except DetalleInventario.DoesNotExist:
                    pass
        inventario = (Inventario.objects
                      .prefetch_related('detalles__material')
                      .get(pk=inventario.pk))
        return Response(InventarioSerializer(inventario).data)

    @action(detail=True, methods=['post'])
    def cerrar(self, request, pk=None):
        inventario = self.get_object()
        if inventario.estado == 'cerrado':
            return Response({'detail': 'Ya está cerrado.'}, status=400)

        with transaction.atomic():
            inventario = (Inventario.objects
                          .prefetch_related('detalles__material')
                          .select_related('camion','usuario')
                          .get(pk=inventario.pk))

            # Sincronizar StockCamion con el conteo físico
            if inventario.camion_id:
                for det in inventario.detalles.all():
                    StockCamion.objects.filter(
                        camion=inventario.camion, material=det.material
                    ).update(cantidad=det.cantidad_fisica)

            inventario.estado = 'cerrado'
            inventario.save()

        # Notificar al encargado del camión con las diferencias
        if inventario.camion_id:
            from datetime import date as _date
            from django.db.models import Q as _Q
            from .fcm import send_notification

            hoy = _date.today()
            asignacion = UsuarioCamion.objects.filter(
                camion=inventario.camion,
                activo=True,
                fecha_inicio__lte=hoy,
            ).filter(
                _Q(fecha_fin__isnull=True) | _Q(fecha_fin__gte=hoy)
            ).select_related('usuario').first()

            if asignacion and asignacion.usuario.fcm_token:
                diffs = [d for d in inventario.detalles.all() if d.diferencia != 0]
                if diffs:
                    lineas = ', '.join(
                        f'{d.material.matricula}: {d.diferencia:+d}' for d in diffs[:5]
                    )
                    if len(diffs) > 5:
                        lineas += f' y {len(diffs)-5} más'
                    body = f'Inventario cerrado. Diferencias: {lineas}'
                else:
                    body = 'Inventario cerrado. Sin diferencias.'
                send_notification(
                    [asignacion.usuario.fcm_token],
                    title=f'Inventario camión {inventario.camion.placa} cerrado',
                    body=body,
                    data={'tipo': 'inventario_cerrado', 'inventario_id': str(inventario.pk)},
                )

        # Enviar PDF por correo al encargado del camión y al enc. almacén
        from .pdf_inventario import enviar_pdf_inventario
        encargado = asignacion.usuario if (inventario.camion_id and asignacion) else None
        enviar_pdf_inventario(inventario, encargado_camion=encargado)

        return Response({'detail': 'Inventario cerrado.'})

    @action(detail=True, methods=['get'])
    def descargar_pdf(self, request, pk=None):
        """GET /api/inventarios/{id}/descargar_pdf/ — retorna el PDF del acta."""
        from django.http import HttpResponse
        from .pdf_inventario import generar_pdf_inventario
        from datetime import date as _date
        from django.db.models import Q as _Q

        inventario = (Inventario.objects
                      .prefetch_related('detalles__material')
                      .select_related('camion', 'usuario__empresa')
                      .get(pk=pk))

        encargado = None
        if inventario.camion_id:
            hoy = _date.today()
            asig = UsuarioCamion.objects.filter(
                camion=inventario.camion, activo=True, fecha_inicio__lte=hoy,
            ).filter(
                _Q(fecha_fin__isnull=True) | _Q(fecha_fin__gte=hoy)
            ).select_related('usuario').first()
            if asig:
                encargado = asig.usuario

        pdf_bytes = generar_pdf_inventario(inventario, encargado_camion=encargado)
        placa = inventario.camion.placa if inventario.camion_id else 'almacen'
        filename = f'inventario_{placa}_{inventario.mes}_{inventario.anio}.pdf'

        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
