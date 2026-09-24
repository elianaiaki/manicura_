from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # include() delega todo lo que empiece con "turnos/" al archivo
    # turnos/urls.py que acabamos de crear. Así cada app maneja sus
    # propias rutas, y el proyecto principal solo las "conecta".
    path('turnos/', include('turnos.urls')),
]

# Esto le dice a Django cómo servir las fotos subidas (media/) mientras
# estamos en desarrollo (DEBUG=True). En un servidor real de producción
# esto lo haría otro programa (ej. Nginx), no Django directamente.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)