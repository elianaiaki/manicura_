"""
Vistas del PANEL DE MARÍA (administradora). A diferencia de
views_clienta.py, acá TODAS las funciones están protegidas con
@login_required: nadie puede ejecutarlas sin haber iniciado sesión.

Cumple RF16 en adelante (agenda, turno manual, cancelar, no-show,
bloquear/desbloquear clienta).
"""

from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Servicio, Clienta, Turno


@login_required
def panel_agenda(request):
    """
    RF17: agenda de María, por día y ordenada por horario.
    Si no se especifica fecha por GET, muestra la de hoy.
    """
    fecha_str = request.GET.get("fecha")
    if fecha_str:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    else:
        fecha = timezone.now().date()

    # El modelo Turno ya tiene ordering = ["fecha", "hora"] en su Meta,
    # así que no hace falta pedir explícitamente el orden acá.
    turnos = Turno.objects.filter(fecha=fecha).exclude(
        estado=Turno.Estado.LIBERADO
    ).select_related("clienta", "servicio")

    return render(request, "turnos/panel_agenda.html", {"turnos": turnos, "fecha": fecha})


@login_required
def panel_turno_nuevo(request):
    """
    RF18 / RF19 / RN21: María crea un turno manualmente (por ejemplo,
    porque se lo pidieron por WhatsApp) y queda CONFIRMADO directamente,
    sin pasar por el pago online.
    """
    servicios = Servicio.objects.filter(activo=True)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        servicio_id = request.POST.get("servicio")
        fecha_post = request.POST.get("fecha")
        hora_post = request.POST.get("hora")

        if not all([nombre, telefono, servicio_id, fecha_post, hora_post]):
            messages.error(request, "Faltan datos obligatorios.")
            return redirect("panel_turno_nuevo")

        servicio = get_object_or_404(Servicio, pk=servicio_id)
        clienta, _ = Clienta.objects.get_or_create(
            telefono=telefono, defaults={"nombre": nombre}
        )

        Turno.objects.create(
            clienta=clienta,
            servicio=servicio,
            fecha=datetime.strptime(fecha_post, "%Y-%m-%d").date(),
            hora=datetime.strptime(hora_post, "%H:%M").time(),
            estado=Turno.Estado.CONFIRMADO,  # María confirma directo, sin pago online
            precio=servicio.precio,
            monto_sena=servicio.monto_sena,
            creado_por_admin=True,
        )
        messages.success(request, "Turno creado y confirmado.")
        return redirect("panel_agenda")

    return render(request, "turnos/panel_turno_nuevo.html", {"servicios": servicios})


@login_required
def panel_turno_cambiar_estado(request, turno_id):
    """
    RF21 (cancelar) y RF22 (registrar no-show). Recibe el nuevo estado
    por POST, con un botón por cada opción en el template.
    """
    turno = get_object_or_404(Turno, pk=turno_id)

    if request.method == "POST":
        nuevo_estado = request.POST.get("estado")
        # Solo permitimos que este formulario mueva el turno a estos dos
        # estados. Esto evita que alguien mande, por ejemplo, "PENDIENTE"
        # a mano y rompa el flujo normal del turno.
        if nuevo_estado in [Turno.Estado.CANCELADO, Turno.Estado.NO_SHOW]:
            turno.estado = nuevo_estado
            turno.save()
            # RF24: notificar a la clienta cuando María cancela.
            # (La notificación interna real se implementará en un paso
            # posterior; acá dejamos el punto exacto donde se dispararía.)
            messages.success(request, "Turno actualizado.")
        else:
            messages.error(request, "Estado no válido.")

    return redirect("panel_agenda")


@login_required
def panel_clienta_bloqueo(request, clienta_id):
    """
    RF26 / RF27: bloquear o desbloquear una clienta desde el panel
    (además de poder hacerlo desde /admin/, ya configurado en el paso 2).
    """
    clienta = get_object_or_404(Clienta, pk=clienta_id)

    if request.method == "POST":
        clienta.bloqueada = not clienta.bloqueada
        clienta.save()
        estado = "bloqueada" if clienta.bloqueada else "desbloqueada"
        messages.success(request, f"Clienta {estado}.")

    return redirect("panel_agenda")