from rest_framework import serializers
from .models import (
    Empresa, Rol, Usuario, Camion, UsuarioCamion, SST,
    Material, StockCamion, Almacen, StockAlmacen, Proveedor,
    IngresoTecsur, DetalleIngresoTecsur,
    DevolucionTecsur, DetalleDevolucionTecsur,
    MaterialMalogrado, DetalleMaterialMalogrado,
    TransferenciaAlmacen, DetalleTransferencia,
    Pedido, DetallePedido,
    Devolucion, DetalleDevolucion,
    UploadConsumo, Consumo, DetalleConsumo,
    Inventario, DetalleInventario,
    Suministro, ManoDeObra, TipoTrabajo, SuministroTipoTrabajo,
    SuministroManoDeObra, Recupero, SuministroRecupero,
    LiquidacionSuministro, LiquidacionPartida,
)


# ── Empresa ─────────────────────────────────────
class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Empresa
        fields = '__all__'


# ── Rol ─────────────────────────────────────────
class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Rol
        fields = '__all__'


# ── Usuario ─────────────────────────────────────
class UsuarioSerializer(serializers.ModelSerializer):
    rol_descripcion    = serializers.CharField(source='rol.descripcion', read_only=True)
    empresa_nombre     = serializers.CharField(source='empresa.nombre',  read_only=True)

    class Meta:
        model  = Usuario
        fields = [
            'id_usuario','nombre','email','telefono',
            'rol','rol_descripcion','empresa','empresa_nombre',
            'activo','fecha_creacion','ultimo_acceso',
        ]
        # clave nunca se expone en lectura
        extra_kwargs = {'clave': {'write_only': True}}

class UsuarioCreateSerializer(serializers.ModelSerializer):
    """Para crear/actualizar usuario con clave en texto plano (se hashea en el signal)."""
    class Meta:
        model  = Usuario
        fields = ['nombre','email','telefono','rol','empresa','clave','activo']

    def create(self, validated_data):
        import hashlib
        clave = validated_data.pop('clave')
        usuario = Usuario(**validated_data)
        usuario.clave = hashlib.sha256(clave.encode()).hexdigest()
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        import hashlib
        if 'clave' in validated_data:
            instance.clave = hashlib.sha256(validated_data.pop('clave').encode()).hexdigest()
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ── Camion ──────────────────────────────────────
class CamionSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    class Meta:
        model  = Camion
        fields = '__all__'


# ── UsuarioCamion ────────────────────────────────
class UsuarioCamionSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.nombre', read_only=True)
    camion_placa   = serializers.CharField(source='camion.placa',   read_only=True)
    class Meta:
        model  = UsuarioCamion
        fields = '__all__'


# ── SST ─────────────────────────────────────────
class SSTSerializer(serializers.ModelSerializer):
    empresa_nombre   = serializers.CharField(source='empresa.nombre',   read_only=True)
    actividad_nombre = serializers.CharField(source='actividad.nombre', read_only=True, default='', allow_null=True)
    class Meta:
        model  = SST
        fields = '__all__'


# ── Material ─────────────────────────────────────
class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Material
        fields = '__all__'


# ── StockCamion ──────────────────────────────────
class StockCamionSerializer(serializers.ModelSerializer):
    camion_placa       = serializers.CharField(source='camion.placa',       read_only=True)
    material_descripcion = serializers.CharField(source='material.descripcion', read_only=True)
    material_matricula   = serializers.CharField(source='material.matricula',   read_only=True)
    class Meta:
        model  = StockCamion
        fields = '__all__'


# ── Almacen ──────────────────────────────────────
class AlmacenSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    class Meta:
        model  = Almacen
        fields = '__all__'


# ── StockAlmacen ─────────────────────────────────
class StockAlmacenSerializer(serializers.ModelSerializer):
    almacen_nombre       = serializers.CharField(source='almacen.nombre',       read_only=True)
    material_descripcion = serializers.CharField(source='material.descripcion', read_only=True)
    material_matricula   = serializers.CharField(source='material.matricula',   read_only=True)
    class Meta:
        model  = StockAlmacen
        fields = '__all__'


# ── Proveedor ────────────────────────────────────
class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Proveedor
        fields = '__all__'


# ── IngresoTecsur ────────────────────────────────
class DetalleIngresoTecsurSerializer(serializers.ModelSerializer):
    material_descripcion = serializers.CharField(source='material.descripcion', read_only=True)
    class Meta:
        model  = DetalleIngresoTecsur
        fields = '__all__'

class IngresoTecsurSerializer(serializers.ModelSerializer):
    detalles          = DetalleIngresoTecsurSerializer(many=True, read_only=True)
    almacen_nombre    = serializers.CharField(source='almacen.nombre',    read_only=True)
    proveedor_nombre  = serializers.CharField(source='proveedor.nombre',  read_only=True)
    usuario_nombre    = serializers.CharField(source='usuario.nombre',    read_only=True)
    class Meta:
        model  = IngresoTecsur
        fields = '__all__'

class IngresoTecsurCreateSerializer(serializers.ModelSerializer):
    detalles = DetalleIngresoTecsurSerializer(many=True)
    class Meta:
        model  = IngresoTecsur
        fields = ['almacen','proveedor','usuario','folio','fecha','observacion','detalles']

    def create(self, validated_data):
        from django.db import transaction
        detalles_data = validated_data.pop('detalles')
        with transaction.atomic():
            ingreso = IngresoTecsur.objects.create(**validated_data)
            for d in detalles_data:
                det = DetalleIngresoTecsur.objects.create(ingreso=ingreso, **d)
                # Actualizar stock almacen
                stock, _ = StockAlmacen.objects.get_or_create(
                    almacen=ingreso.almacen, material=det.material,
                    defaults={'cantidad': 0}
                )
                stock.agregar(det.cantidad)
        return ingreso


# ── DevolucionTecsur ─────────────────────────────
class DetalleDevolucionTecsurSerializer(serializers.ModelSerializer):
    material_descripcion = serializers.CharField(source='material.descripcion', read_only=True)
    class Meta:
        model  = DetalleDevolucionTecsur
        fields = '__all__'

class DevolucionTecsurSerializer(serializers.ModelSerializer):
    detalles = DetalleDevolucionTecsurSerializer(many=True, read_only=True)
    almacen_nombre   = serializers.CharField(source='almacen.nombre',   read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    usuario_nombre   = serializers.CharField(source='usuario.nombre',   read_only=True)
    class Meta:
        model  = DevolucionTecsur
        fields = '__all__'

class DevolucionTecsurCreateSerializer(serializers.ModelSerializer):
    detalles = DetalleDevolucionTecsurSerializer(many=True)
    class Meta:
        model  = DevolucionTecsur
        fields = ['almacen','proveedor','usuario','folio','fecha','observacion','detalles']

    def create(self, validated_data):
        from django.db import transaction
        detalles_data = validated_data.pop('detalles')
        with transaction.atomic():
            devolucion = DevolucionTecsur.objects.create(**validated_data)
            for d in detalles_data:
                det = DetalleDevolucionTecsur.objects.create(devolucion_tecsur=devolucion, **d)
                stock = StockAlmacen.objects.get(almacen=devolucion.almacen, material=det.material)
                stock.descontar(det.cantidad)
        return devolucion


# ── MaterialMalogrado ────────────────────────────
class DetalleMaterialMalogradoSerializer(serializers.ModelSerializer):
    material_descripcion = serializers.CharField(source='material.descripcion', read_only=True)
    costo_total          = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    class Meta:
        model  = DetalleMaterialMalogrado
        fields = '__all__'

class MaterialMalogradoSerializer(serializers.ModelSerializer):
    detalles = DetalleMaterialMalogradoSerializer(many=True, read_only=True)
    almacen_nombre   = serializers.CharField(source='almacen.nombre',   read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    usuario_nombre   = serializers.CharField(source='usuario.nombre',   read_only=True)
    class Meta:
        model  = MaterialMalogrado
        fields = '__all__'

class MaterialMalogradoCreateSerializer(serializers.ModelSerializer):
    detalles = DetalleMaterialMalogradoSerializer(many=True)
    class Meta:
        model  = MaterialMalogrado
        fields = ['almacen','proveedor','usuario','folio_factura','fecha','observacion','detalles']

    def create(self, validated_data):
        from django.db import transaction
        detalles_data = validated_data.pop('detalles')
        with transaction.atomic():
            malogrado = MaterialMalogrado.objects.create(**validated_data)
            for d in detalles_data:
                det = DetalleMaterialMalogrado.objects.create(malogrado=malogrado, **d)
                stock = StockAlmacen.objects.get(almacen=malogrado.almacen, material=det.material)
                stock.descontar(det.cantidad)
        return malogrado


# ── TransferenciaAlmacen ─────────────────────────
class DetalleTransferenciaSerializer(serializers.ModelSerializer):
    material_descripcion = serializers.CharField(source='material.descripcion', read_only=True)
    class Meta:
        model  = DetalleTransferencia
        fields = '__all__'

class TransferenciaAlmacenSerializer(serializers.ModelSerializer):
    detalles               = DetalleTransferenciaSerializer(many=True, read_only=True)
    almacen_origen_nombre  = serializers.CharField(source='almacen_origen.nombre',  read_only=True)
    almacen_destino_nombre = serializers.CharField(source='almacen_destino.nombre', read_only=True)
    usuario_nombre         = serializers.CharField(source='usuario.nombre',          read_only=True)
    class Meta:
        model  = TransferenciaAlmacen
        fields = '__all__'

class TransferenciaAlmacenCreateSerializer(serializers.ModelSerializer):
    detalles = DetalleTransferenciaSerializer(many=True)
    class Meta:
        model  = TransferenciaAlmacen
        fields = ['almacen_origen','almacen_destino','usuario','fecha','observacion','detalles']

    def create(self, validated_data):
        from django.db import transaction
        detalles_data = validated_data.pop('detalles')
        with transaction.atomic():
            transferencia = TransferenciaAlmacen.objects.create(**validated_data)
            for d in detalles_data:
                det = DetalleTransferencia.objects.create(transferencia=transferencia, **d)
                origen  = StockAlmacen.objects.get(almacen=transferencia.almacen_origen,  material=det.material)
                destino, _ = StockAlmacen.objects.get_or_create(almacen=transferencia.almacen_destino, material=det.material, defaults={'cantidad':0})
                origen.descontar(det.cantidad)
                destino.agregar(det.cantidad)
        return transferencia


# ── Pedido ───────────────────────────────────────
class DetallePedidoSerializer(serializers.ModelSerializer):
    material_descripcion = serializers.CharField(source='material.descripcion', read_only=True)
    material_matricula   = serializers.CharField(source='material.matricula',   read_only=True)
    class Meta:
        model  = DetallePedido
        fields = '__all__'
        extra_kwargs = {'pedido': {'read_only': True}}

class PedidoSerializer(serializers.ModelSerializer):
    detalles        = DetallePedidoSerializer(many=True, read_only=True)
    usuario_nombre  = serializers.CharField(source='usuario.nombre', read_only=True)
    camion_placa    = serializers.CharField(source='camion.placa',   read_only=True)
    almacen_nombre  = serializers.CharField(source='almacen.nombre', read_only=True)
    class Meta:
        model  = Pedido
        fields = '__all__'

class PedidoCreateSerializer(serializers.ModelSerializer):
    detalles = DetallePedidoSerializer(many=True)
    class Meta:
        model  = Pedido
        fields = ['camion','usuario','observacion','detalles']

    def create(self, validated_data):
        from django.db import transaction
        detalles_data = validated_data.pop('detalles')
        with transaction.atomic():
            pedido = Pedido.objects.create(**validated_data)
            for d in detalles_data:
                DetallePedido.objects.create(pedido=pedido, material=d['material'], cantidad_solicitada=d['cantidad_solicitada'])
        return pedido

class PedidoAprobarSerializer(serializers.Serializer):
    """Body para aprobar o rechazar un pedido."""
    accion          = serializers.ChoiceField(choices=['aprobar','rechazar'])
    usuario_aprueba = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all())
    almacen         = serializers.PrimaryKeyRelatedField(queryset=Almacen.objects.all(), required=False)
    observacion     = serializers.CharField(required=False, allow_blank=True)
    detalles        = DetallePedidoSerializer(many=True, required=False)


# ── Devolucion ───────────────────────────────────
class DetalleDevolucionSerializer(serializers.ModelSerializer):
    material_descripcion = serializers.CharField(source='material.descripcion', read_only=True)
    material_matricula   = serializers.CharField(source='material.matricula',   read_only=True)
    class Meta:
        model  = DetalleDevolucion
        fields = '__all__'
        extra_kwargs = {'devolucion': {'read_only': True}}

class DevolucionSerializer(serializers.ModelSerializer):
    detalles       = DetalleDevolucionSerializer(many=True, read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.nombre', read_only=True)
    camion_placa   = serializers.CharField(source='camion.placa',   read_only=True)
    class Meta:
        model  = Devolucion
        fields = '__all__'

class DevolucionCreateSerializer(serializers.ModelSerializer):
    detalles = DetalleDevolucionSerializer(many=True)
    class Meta:
        model  = Devolucion
        fields = ['camion','usuario','observacion','detalles']

    def validate(self, data):
        from django.db.models import Sum
        camion   = data.get('camion')
        detalles = data.get('detalles', [])
        errores  = []
        for det in detalles:
            material        = det['material']
            cant_solicitada = det['cantidad_solicitada']
            try:
                stock_actual = StockCamion.objects.get(camion=camion, material=material).cantidad
            except StockCamion.DoesNotExist:
                errores.append(f'{material.matricula}: sin stock registrado en este camión.')
                continue
            pendiente = (DetalleDevolucion.objects
                         .filter(devolucion__camion=camion,
                                 devolucion__estado='pendiente',
                                 material=material)
                         .aggregate(total=Sum('cantidad_solicitada'))['total'] or 0)
            disponible = stock_actual - pendiente
            if cant_solicitada > disponible:
                errores.append(
                    f'{material.matricula}: solicitás {cant_solicitada} pero solo hay '
                    f'{disponible} disponible (stock {stock_actual}, en trámite {pendiente}).'
                )
        if errores:
            raise serializers.ValidationError({'detalles': errores})
        return data

    def create(self, validated_data):
        from django.db import transaction
        detalles_data = validated_data.pop('detalles')
        with transaction.atomic():
            devolucion = Devolucion.objects.create(**validated_data)
            for d in detalles_data:
                DetalleDevolucion.objects.create(devolucion=devolucion, material=d['material'], cantidad_solicitada=d['cantidad_solicitada'])
        return devolucion

class DevolucionAprobarSerializer(serializers.Serializer):
    accion          = serializers.ChoiceField(choices=['aprobar','rechazar'])
    usuario_aprueba = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all())
    almacen_destino = serializers.PrimaryKeyRelatedField(queryset=Almacen.objects.all(), required=False)
    observacion     = serializers.CharField(required=False, allow_blank=True)
    detalles        = DetalleDevolucionSerializer(many=True, required=False)


# ── UploadConsumo / Consumo ──────────────────────
class DetalleConsumoSerializer(serializers.ModelSerializer):
    material_descripcion = serializers.CharField(source='material.descripcion', read_only=True)
    class Meta:
        model  = DetalleConsumo
        fields = '__all__'

class ConsumoSerializer(serializers.ModelSerializer):
    detalles        = DetalleConsumoSerializer(many=True, read_only=True)
    usuario_nombre  = serializers.CharField(source='usuario_consume.nombre', read_only=True)
    camion_placa    = serializers.CharField(source='camion.placa', read_only=True)
    class Meta:
        model  = Consumo
        fields = '__all__'

class UploadConsumoSerializer(serializers.ModelSerializer):
    consumos       = ConsumoSerializer(many=True, read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.nombre', read_only=True)
    sst_actividad  = serializers.CharField(source='sst.actividad.nombre', read_only=True, default='', allow_null=True)
    class Meta:
        model  = UploadConsumo
        fields = '__all__'


# ── Inventario ───────────────────────────────────
class DetalleInventarioSerializer(serializers.ModelSerializer):
    material_descripcion = serializers.CharField(source='material.descripcion', read_only=True)
    material_matricula   = serializers.CharField(source='material.matricula',   read_only=True)
    class Meta:
        model  = DetalleInventario
        fields = '__all__'

class InventarioSerializer(serializers.ModelSerializer):
    detalles       = DetalleInventarioSerializer(many=True, read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.nombre', read_only=True)
    camion_placa   = serializers.CharField(source='camion.placa',   read_only=True)
    almacen_nombre = serializers.CharField(source='almacen.nombre', read_only=True)
    class Meta:
        model  = Inventario
        fields = '__all__'

class InventarioCreateSerializer(serializers.ModelSerializer):
    detalles = DetalleInventarioSerializer(many=True)
    class Meta:
        model  = Inventario
        fields = ['camion','almacen','usuario','mes','anio','observacion','detalles']

    def create(self, validated_data):
        from django.db import transaction
        detalles_data = validated_data.pop('detalles')
        with transaction.atomic():
            inventario = Inventario.objects.create(**validated_data)
            for d in detalles_data:
                DetalleInventario.objects.create(inventario=inventario, **d)
        return inventario


# ── Suministro ──────────────────────────────────────────────────────────────
class SuministroSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Suministro
        fields = '__all__'


# ── ManoDeObra ──────────────────────────────────────────────────────────────
class ManoDeObraSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ManoDeObra
        fields = '__all__'


# ── TipoTrabajo ─────────────────────────────────────────────────────────────
class TipoTrabajoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TipoTrabajo
        fields = '__all__'


# ── SuministroManoDeObra ─────────────────────────────────────────────────────
class SuministroManoDeObraSerializer(serializers.ModelSerializer):
    partida     = serializers.CharField(source='mano_de_obra.partida',     read_only=True)
    descripcion = serializers.CharField(source='mano_de_obra.descripcion', read_only=True)
    precio      = serializers.DecimalField(source='mano_de_obra.precio',
                                           max_digits=12, decimal_places=2, read_only=True)
    class Meta:
        model  = SuministroManoDeObra
        fields = ['id_suministro_mano_de_obra', 'mano_de_obra', 'partida', 'descripcion', 'precio']


# ── Recupero ─────────────────────────────────────────────────────────────────
class RecuperoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Recupero
        fields = '__all__'


# ── SuministroRecupero ───────────────────────────────────────────────────────
class SuministroRecuperoSerializer(serializers.ModelSerializer):
    matricula   = serializers.CharField(source='recupero.matricula',   read_only=True)
    descripcion = serializers.CharField(source='recupero.descripcion', read_only=True)
    class Meta:
        model  = SuministroRecupero
        fields = ['id_suministro_recupero', 'suministro', 'recupero',
                  'matricula', 'descripcion', 'cantidad', 'fecha']


# ── Liquidacion Suministro ───────────────────────────────────────────────────
class LiquidacionPartidaSerializer(serializers.ModelSerializer):
    partida     = serializers.CharField(source='mano_de_obra.partida',     read_only=True)
    descripcion = serializers.CharField(source='mano_de_obra.descripcion', read_only=True)
    class Meta:
        model  = LiquidacionPartida
        fields = ['id_liquidacion_partida', 'mano_de_obra', 'partida', 'descripcion', 'cantidad']

class LiquidacionSuministroSerializer(serializers.ModelSerializer):
    numero_suministro  = serializers.CharField(source='suministro.numero_suministro', read_only=True)
    usuario_nombre     = serializers.CharField(source='usuario.nombre',               read_only=True)
    tipo_trabajo_nombre = serializers.CharField(source='tipo_trabajo.nombre',         read_only=True)
    partidas           = LiquidacionPartidaSerializer(many=True, read_only=True)
    class Meta:
        model  = LiquidacionSuministro
        fields = [
            'id_liquidacion', 'suministro', 'numero_suministro',
            'usuario', 'usuario_nombre', 'tipo_trabajo', 'tipo_trabajo_nombre',
            'fecha', 'observacion', 'partidas',
        ]

class LiquidacionPartidaCreateSerializer(serializers.Serializer):
    mano_de_obra = serializers.PrimaryKeyRelatedField(queryset=ManoDeObra.objects.all())
    cantidad     = serializers.DecimalField(max_digits=10, decimal_places=2)

class LiquidacionSuministroCreateSerializer(serializers.Serializer):
    suministro   = serializers.PrimaryKeyRelatedField(queryset=Suministro.objects.all())
    usuario      = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all())
    tipo_trabajo = serializers.PrimaryKeyRelatedField(queryset=TipoTrabajo.objects.all())
    observacion  = serializers.CharField(required=False, allow_blank=True, default='')
    partidas     = LiquidacionPartidaCreateSerializer(many=True)

    def create(self, validated_data):
        from django.db import transaction
        partidas_data = validated_data.pop('partidas')
        with transaction.atomic():
            liq = LiquidacionSuministro.objects.create(**validated_data)
            for p in partidas_data:
                LiquidacionPartida.objects.create(liquidacion=liq, **p)
            # Cambiar estado del suministro a ejecutado
            liq.suministro.estado = 'ejecutado'
            liq.suministro.save(update_fields=['estado'])
        return liq
