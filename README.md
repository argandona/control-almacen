# Backend Django — API REST para Flutter

## Stack
- Django 5 + Django REST Framework
- JWT con simplejwt (tokens personalizados sin django.auth.User)
- CORS habilitado para cualquier origen (ajustar en producción)
- SQLite por defecto (cambiar a PostgreSQL en producción)

## Instalación rápida

```bash
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers pillow
python manage.py migrate
python manage.py seed          # crea roles, usuarios y datos demo
python manage.py runserver
```

## Usuarios de prueba

| Email | Clave | Rol |
|-------|-------|-----|
| super@admin.com | admin123 | SuperAdmin |
| admin@demo.com | demo123 | Admin Empresa |
| encargado@demo.com | demo123 | Encargado |
| capataz@demo.com | demo123 | Capataz |
| liquidador@demo.com | demo123 | Liquidador |
| almacen@demo.com | demo123 | Encargado Almacén |

---

## Endpoints principales

### Autenticación
```
POST /api/auth/login/        { email, clave }  → { access, refresh, usuario }
POST /api/auth/refresh/      { refresh }        → { access }
```
Header en todas las peticiones: `Authorization: Bearer <access_token>`

### CRUD estándar
```
GET/POST        /api/empresas/
GET/PUT/PATCH/DELETE /api/empresas/<id>/

GET/POST        /api/usuarios/
GET             /api/usuarios/me/          ← usuario autenticado

GET/POST        /api/camiones/
GET/POST        /api/almacenes/
GET/POST        /api/materiales/?q=cable   ← búsqueda
GET/POST        /api/ssts/
GET/POST        /api/proveedores/
GET/POST        /api/stock-camion/?camion=1
GET/POST        /api/stock-almacen/?almacen=1
GET/POST        /api/usuario-camion/
GET             /api/usuario-camion/camion_activo/?usuario=3
```

### Pedidos
```
POST /api/pedidos/                         ← Encargado/Capataz crea pedido
GET  /api/pedidos/?estado=pendiente
GET  /api/pedidos/?camion=1
POST /api/pedidos/<id>/aprobar/            ← Enc. Almacén aprueba o rechaza
```
Body aprobar:
```json
{
  "accion": "aprobar",
  "usuario_aprueba": 6,
  "almacen": 1,
  "detalles": [{"material": 1, "cantidad_aprobada": 5}]
}
```

### Devoluciones
```
POST /api/devoluciones/
POST /api/devoluciones/<id>/aprobar/
```

### Ingresos/Devoluciones Tecsur
```
POST /api/ingresos-tecsur/                 ← sube stock almacén
POST /api/devoluciones-tecsur/             ← baja stock almacén
POST /api/materiales-malogrados/
POST /api/transferencias/                  ← mueve stock entre almacenes
```

### Consumo
```
POST /api/uploads-consumo/
POST /api/uploads-consumo/<id>/aprobar/    ← descuenta StockCamion
POST /api/uploads-consumo/<id>/rechazar/
```

### Inventario
```
POST /api/inventarios/
POST /api/inventarios/<id>/cerrar/
GET  /api/inventarios/?camion=1&mes=5&anio=2026
```

---

## Integración Flutter

```dart
// lib/services/api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const baseUrl = 'http://10.0.2.2:8000/api'; // emulador Android
  // static const baseUrl = 'http://localhost:8000/api'; // iOS simulator
  String? _token;

  Future<Map<String, dynamic>> login(String email, String clave) async {
    final res = await http.post(
      Uri.parse('$baseUrl/auth/login/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'clave': clave}),
    );
    final data = jsonDecode(res.body);
    if (res.statusCode == 200) _token = data['access'];
    return data;
  }

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer $_token',
  };

  Future<List> getPedidos({String estado = 'pendiente'}) async {
    final res = await http.get(
      Uri.parse('$baseUrl/pedidos/?estado=$estado'),
      headers: _headers,
    );
    return jsonDecode(res.body)['results'];
  }

  Future<Map> crearPedido(Map body) async {
    final res = await http.post(
      Uri.parse('$baseUrl/pedidos/'),
      headers: _headers,
      body: jsonEncode(body),
    );
    return jsonDecode(res.body);
  }
}
```

## Producción (cambios recomendados)
1. `DEBUG = False` y `SECRET_KEY` desde variable de entorno
2. `DATABASES` → PostgreSQL
3. `CORS_ALLOWED_ORIGINS` con las URLs reales
4. `ALLOWED_HOSTS` con el dominio real
5. Servir con gunicorn + nginx
