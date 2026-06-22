"""Cliente mínimo para escribir en el proyecto Render (Encossa).

La lectura de suministros vive en views.py (_render_suministros). Aquí está la
escritura, que usa la liquidación para reflejar en Render el estado del
suministro y la observación del contratista."""
import requests
from django.conf import settings


def _token():
    """Obtiene un access token fresco del proyecto en Render."""
    base = settings.RENDER_API_URL.rstrip('/')
    resp = requests.post(
        f'{base}/api/token/',
        json={
            'username': settings.RENDER_API_USERNAME,
            'password': settings.RENDER_API_PASSWORD,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()['access']


def actualizar_suministro(suministro_id, payload):
    """PATCH /api/suministros/<id>/ en Render.

    payload admite, entre otros: estado_suministro (texto, ej. "EJECUTADO"/
    "DEVUELTO"), observacion_contratista, fecha_ejecucion, ejecutado_por.
    Lanza requests.HTTPError si Render responde error.
    """
    base  = settings.RENDER_API_URL.rstrip('/')
    token = _token()
    resp  = requests.patch(
        f'{base}/api/suministros/{suministro_id}/',
        headers={'Authorization': f'Bearer {token}'},
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()
