from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import portal_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    # Portal web para Liquidadores / Encargados de Almacén
    path('portal/login/',     portal_views.portal_login,     name='portal_login'),
    path('portal/logout/',    portal_views.portal_logout,    name='portal_logout'),
    path('portal/',           portal_views.portal_consumos,  name='portal_consumos'),
    path('portal/plantilla/', portal_views.portal_plantilla, name='portal_plantilla'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
