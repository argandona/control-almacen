from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core import portal_views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='portal_consumos', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    # Portal web para Liquidadores / Encargados de Almacén
    path('portal/login/',                      portal_views.portal_login,          name='portal_login'),
    path('portal/logout/',                     portal_views.portal_logout,         name='portal_logout'),
    path('portal/',                            portal_views.portal_consumos,       name='portal_consumos'),
    path('portal/plantilla/',                  portal_views.portal_plantilla,      name='portal_plantilla'),
    # Enc. Almacén — pedidos, devoluciones, matriz
    path('portal/pedidos/',                             portal_views.portal_pedidos,             name='portal_pedidos'),
    path('portal/pedidos/excel/',                       portal_views.portal_pedidos_excel,       name='portal_pedidos_excel'),
    path('portal/pedidos/<int:pedido_id>/aprobar/',     portal_views.portal_aprobar_pedido,      name='portal_aprobar_pedido'),
    path('portal/pedidos/<int:pedido_id>/rechazar/',    portal_views.portal_rechazar_pedido,     name='portal_rechazar_pedido'),
    path('portal/devoluciones/',                        portal_views.portal_devoluciones,        name='portal_devoluciones'),
    path('portal/devoluciones/<int:dev_id>/aprobar/',   portal_views.portal_aprobar_devolucion,  name='portal_aprobar_devolucion'),
    path('portal/devoluciones/<int:dev_id>/rechazar/',  portal_views.portal_rechazar_devolucion, name='portal_rechazar_devolucion'),
    path('portal/matriz/',                     portal_views.portal_matriz,         name='portal_matriz'),
    # SuperAdmin — gestión de usuarios
    path('portal/usuarios/',                   portal_views.portal_usuarios,       name='portal_usuarios'),
    path('portal/usuarios/nuevo/',             portal_views.portal_crear_usuario,  name='portal_crear_usuario'),
    path('portal/usuarios/<int:uid>/toggle/',  portal_views.portal_toggle_usuario, name='portal_toggle_usuario'),
    # SuperAdmin — asignación SST / suministros
    path('portal/sst/',                                                  portal_views.portal_sst_lista,              name='portal_sst_lista'),
    path('portal/sst/<int:sst_id>/',                                     portal_views.portal_sst_detalle,            name='portal_sst_detalle'),
    path('portal/sst/<int:sst_id>/encargado/agregar/',                   portal_views.portal_sst_agregar_encargado,  name='portal_sst_agregar_encargado'),
    path('portal/sst/<int:sst_id>/encargado/<int:enc_id>/quitar/',       portal_views.portal_sst_quitar_encargado,   name='portal_sst_quitar_encargado'),
    path('portal/sst/<int:sst_id>/suministro/agregar/',                  portal_views.portal_sst_agregar_suministro, name='portal_sst_agregar_suministro'),
    path('portal/sst/<int:sst_id>/suministro/<int:ss_id>/quitar/',       portal_views.portal_sst_quitar_suministro,  name='portal_sst_quitar_suministro'),
    path('portal/sst/<int:sst_id>/suministro/<int:ss_id>/asignado/',     portal_views.portal_sst_cambiar_asignado,   name='portal_sst_cambiar_asignado'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
