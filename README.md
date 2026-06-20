# Control Almacén — Documentación del proyecto

Sistema de **control de almacén, stock de camiones, pedidos, devoluciones, inventarios,
consumos y liquidaciones** para una empresa contratista (ENCOSSA). Está compuesto por dos
piezas que se comunican vía API REST:

| Proyecto | Carpeta | Stack | Rol |
|----------|---------|-------|-----|
| **Backend** | `Control_almacen/` | Django 5 + DRF | API REST + panel admin + datos |
| **App móvil** | `../app_movil/` | Flutter (Dart) | Cliente para personal de campo |

> La documentación de la app móvil está en `../app_movil/README.md`.

---

## 1. Stack tecnológico

- **Django 5** + **Django REST Framework**
- **Autenticación JWT** con `djangorestframework-simplejwt`, sobre un modelo `Usuario` propio
  (no se usa `django.contrib.auth.User`).
- **CORS** habilitado (`django-cors-headers`).
- **Base de datos**: SQLite en desarrollo (`db.sqlite3`), PostgreSQL en producción
  (`psycopg2-binary` + `dj-database-url`).
- **Archivos estáticos** servidos con `whitenoise`.
- **Configuración por entorno** con `python-decouple`.
- **Notificaciones push** con `firebase-admin` (FCM).
- **Generación de PDF** con `reportlab`.
- **Importación de Excel** con `openpyxl`.
- **Despliegue**: Render (`Procfile` + `build.sh`), servido con `gunicorn`.

---

## 2. Estructura del repositorio

```
Control_almacen/
├── config/                 # Proyecto Django (settings, urls, wsgi/asgi)
│   ├── settings.py
│   └── urls.py
├── core/                   # App principal (toda la lógica de negocio)
│   ├── models.py           # ~30 modelos de dominio
│   ├── views.py            # ViewSets DRF (~1200 líneas)
│   ├── serializers.py      # Serializers DRF
│   ├── urls.py             # Router con todos los endpoints /api/
│   ├── authentication.py   # LoginView / RefreshView (JWT)
│   ├── backends.py         # Backend de autenticación personalizado
│   ├── security.py         # Permisos / control de acceso
│   ├── admin.py            # Panel de administración Django
│   ├── serializers.py
│   ├── fcm.py              # Envío de notificaciones push (Firebase)
│   ├── pdf_inventario.py   # Exportación de inventarios a PDF
│   ├── portal_views.py     # Vistas del portal web
│   ├── management/         # Comandos personalizados (ej. seed)
│   ├── migrations/
│   └── templates/
├── manage.py
├── requirements.txt
├── build.sh                # Script de build para Render
├── Procfile                # web: gunicorn config.wsgi
└── db.sqlite3              # BD de desarrollo
```

---

## 3. Roles y permisos

Los roles están codificados en `core/models.py` (modelo `Rol`):

| ID | Rol | Capacidades principales |
|----|-----|--------------------------|
| 1 | **SuperAdmin** | Acceso total; no pertenece a ninguna empresa |
| 2 | **Admin Empresa** | Gestiona su empresa |
| 3 | **Encargado** | Crea pedidos y devoluciones |
| 4 | **Capataz** | Crea pedidos y devoluciones |
| 5 | **Liquidador** | Sube consumos, liquida suministros |
| 6 | **Encargado Almacén** | Aprueba pedidos/devoluciones, inventarios, ingresos/transferencias |

Las reglas de negocio viven como métodos del modelo `Usuario`
(`puede_hacer_pedido`, `puede_aprobar_pedido`, `puede_hacer_inventario`, etc.) y se validan
también dentro de `clean()` de cada modelo.

---

## 4. Modelo de datos (resumen)

**Organización**
- `Empresa`, `Rol`, `Usuario`, `Almacen`, `Proveedor`

**Flota y asignaciones**
- `Camion`, `UsuarioCamion` (asigna un camión a un usuario por rango de fechas; un camión
  no puede tener dos encargados solapados)

**Catálogos**
- `Material`, `ManoDeObra`, `Recupero`, `Actividad`, `TipoTrabajo`

**Stock**
- `StockCamion` (cantidad decimal), `StockAlmacen` (cantidad entera)
- Ambos exponen `agregar()` / `descontar()` con validación de stock insuficiente

**Movimientos de almacén** (cada uno con su tabla de detalle)
- `IngresoTecsur` → sube stock de almacén
- `DevolucionTecsur` → baja stock de almacén
- `MaterialMalogrado` → registra material dañado con costo
- `TransferenciaAlmacen` → mueve stock entre almacenes

**Pedidos y devoluciones** (camión ↔ almacén)
- `Pedido` / `DetallePedido` — flujo: pendiente → aprobado/rechazado
- `Devolucion` / `DetalleDevolucion` — mismo flujo de aprobación

**Consumos**
- `UploadConsumo` (carga por SST, normalmente desde Excel) → `Consumo` → `DetalleConsumo`
  La aprobación descuenta `StockCamion`.

**Inventarios**
- `Inventario` (de un camión **o** un almacén, por mes/año) / `DetalleInventario`
  (calcula `diferencia = física − teórica` automáticamente)

**SST y suministros (liquidación)**
- `SST`, `SSTEncargado`, `Suministro`, `SSTSuministro`, `SSTSuministro`
- `TipoTrabajo` con sus `TipoTrabajoManoDeObra` y `TipoTrabajoMaterial`
- `LiquidacionSuministro` / `LiquidacionPartida` / `ConsumoMaterialSuministro`
- Soporta suministros/SST **externos** (consumidos desde una API en Render por código)

**Planos por SST**
- `PlanoSST` — plano/croquis editable, **1 por SST por empresa**. Se identifica por
  `sst_codigo` (string de Render, igual que `sst_externo`) y guarda el dibujo en un
  `JSONField elementos` (lista de `{assetId, x, y, escala, rotacion, z}`).

---

## 5. Autenticación

```
POST /api/auth/login/      { email, clave }   → { access, refresh, usuario }
POST /api/auth/refresh/    { refresh }          → { access }
```

Todas las peticiones autenticadas usan el header:

```
Authorization: Bearer <access_token>
```

---

## 6. Endpoints principales

Todos cuelgan de `/api/` (ver `core/urls.py`). Son `ViewSet`s DRF (CRUD estándar + acciones).

### CRUD / catálogos
```
/api/empresas/      /api/roles/        /api/usuarios/   (+ /usuarios/me/)
/api/camiones/      /api/usuario-camion/  (+ /camion_activo/?usuario=)
/api/almacenes/     /api/materiales/?q=  /api/proveedores/   /api/ssts/
/api/stock-camion/?camion=1     /api/stock-almacen/?almacen=1
```

### Pedidos
```
POST /api/pedidos/                    # Encargado/Capataz crea
GET  /api/pedidos/?estado=pendiente&camion=1
POST /api/pedidos/<id>/aprobar/       # Encargado Almacén aprueba/rechaza
```
Body de aprobación:
```json
{
  "accion": "aprobar",
  "usuario_aprueba": 6,
  "almacen": 1,
  "detalles": [{ "material": 1, "cantidad_aprobada": 5 }]
}
```

### Devoluciones
```
POST /api/devoluciones/
POST /api/devoluciones/<id>/aprobar/
```

### Movimientos de almacén
```
POST /api/ingresos-tecsur/          # sube stock
POST /api/devoluciones-tecsur/      # baja stock
POST /api/materiales-malogrados/
POST /api/transferencias/           # mueve stock entre almacenes
```

### Consumos
```
POST /api/uploads-consumo/
POST /api/uploads-consumo/<id>/aprobar/    # descuenta StockCamion
POST /api/uploads-consumo/<id>/rechazar/
```

### Inventarios
```
POST /api/inventarios/
POST /api/inventarios/<id>/cerrar/
GET  /api/inventarios/?camion=1&mes=5&anio=2026
```

### Suministros y liquidaciones
```
/api/suministros/
/api/liquidaciones/
/api/liquidaciones/semana_trabajo/   # consume API externa (Render) por actividad
```

### Planos por SST
```
POST /api/planos/                    # upsert del plano por (empresa, sst_codigo)
GET  /api/planos/?sst_codigo=XXX     # plano de un SST (o elementos vacíos)
GET  /api/planos/semana_sst/?usuario=<id>   # SSTs de la semana (Render) por fecha,
                                            # deduplicados, con flag tiene_plano
```
Body de upsert:
```json
{
  "sst_codigo": "12345",
  "usuario": 3,
  "elementos": [
    { "assetId": "poste", "x": 120, "y": 80, "escala": 1.2, "rotacion": 0.3, "z": 1 }
  ]
}
```

---

## 7. Instalación y ejecución (desarrollo)

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Migrar la base de datos
python manage.py migrate

# 3. (Opcional) Cargar datos demo: roles, usuarios y catálogos
python manage.py seed

# 4. Levantar el servidor
python manage.py runserver
```

API disponible en `http://localhost:8000/api/`
Panel admin en `http://localhost:8000/admin/`

### Usuarios de prueba (tras `seed`)

| Email | Clave | Rol |
|-------|-------|-----|
| super@admin.com | admin123 | SuperAdmin |
| admin@demo.com | demo123 | Admin Empresa |
| encargado@demo.com | demo123 | Encargado |
| capataz@demo.com | demo123 | Capataz |
| liquidador@demo.com | demo123 | Liquidador |
| almacen@demo.com | demo123 | Encargado Almacén |

---

## 8. Despliegue (Render)

- `build.sh` → instala dependencias, `collectstatic` y `migrate`.
- `Procfile` → `web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`.
- Producción real desplegada en: `https://control-almacen-n56o.onrender.com/api/`
  (es la URL base por defecto que consume la app móvil).

### Checklist de producción
1. `DEBUG = False` y `SECRET_KEY` desde variable de entorno.
2. `DATABASES` → PostgreSQL (vía `DATABASE_URL`).
3. `CORS_ALLOWED_ORIGINS` con las URLs reales.
4. `ALLOWED_HOSTS` con el dominio real.
5. Credenciales de Firebase (FCM) configuradas como variable de entorno.

---

## 9. Notas

- El backend está pensado como **API headless** para la app Flutter, más un **panel admin**
  Django para gestión interna.
- Existe integración con una **API externa en Render** para liquidaciones por suministro/SST
  (campos `suministro_externo` / `sst_externo`).
- Las notificaciones push (FCM) se envían al `fcm_token` guardado en cada `Usuario`
  (por ejemplo, al aprobar pedidos/devoluciones).
