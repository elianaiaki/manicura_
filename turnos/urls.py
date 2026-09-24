from django.urls import path
from django.contrib.auth import views as auth_views

# Importamos los dos archivos de vistas SIN abreviar. Es un poco más
# largo de escribir en cada línea de abajo, pero se lee sin ninguna
# ambigüedad: queda clarísimo de qué archivo viene cada vista.
from . import views_clienta
from . import views_panel

# Le ponemos "name" a cada URL para poder referenciarla en los templates
# y en las vistas con redirect("nombre") en vez de escribir la ruta a
# mano. Así, si el día de mañana cambiamos "/turnos/" por otra cosa,
# no hay que salir a buscar y reemplazar en todos lados.
urlpatterns = [
    # --- Público (views_clienta.py) ---
    path("", views_clienta.lista_servicios, name="lista_servicios"),
    path("solicitar/<int:servicio_id>/", views_clienta.solicitar_turno, name="solicitar_turno"),
    path("reservado/<int:turno_id>/", views_clienta.turno_reservado, name="turno_reservado"),
    path("mis-turnos/", views_clienta.mis_turnos, name="mis_turnos"),

    # --- Login / logout de María (RF16) ---
    # LoginView y LogoutView son vistas que Django ya trae hechas,
    # probadas y seguras (manejan el hasheo de contraseña, los intentos
    # fallidos, la sesión, el token CSRF, etc). Solo le decimos qué
    # template usar para el formulario de login.
    path("panel/login/", auth_views.LoginView.as_view(
        template_name="turnos/panel_login.html"
    ), name="panel_login"),
    path("panel/logout/", auth_views.LogoutView.as_view(
        next_page="lista_servicios"
    ), name="panel_logout"),

    # --- Panel de María (views_panel.py) ---
    path("panel/", views_panel.panel_agenda, name="panel_agenda"),
    path("panel/turno/nuevo/", views_panel.panel_turno_nuevo, name="panel_turno_nuevo"),
    path("panel/turno/<int:turno_id>/estado/", views_panel.panel_turno_cambiar_estado,
         name="panel_turno_cambiar_estado"),
    path("panel/clienta/<int:clienta_id>/bloqueo/", views_panel.panel_clienta_bloqueo,
         name="panel_clienta_bloqueo"),
]