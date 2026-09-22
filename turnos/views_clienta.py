"""
Vistas del lado de la CLIENTA: consultar servicios, pedir un turno,
consultar "mis turnos". Ninguna de estas vistas requiere haber iniciado
sesión (recordá: la clienta no tiene cuenta, según el relevamiento).

Separamos este archivo de views_panel.py solo para que se entienda mejor
qué es "público" (esto) y qué es "del panel de María" (el otro archivo).
Django funciona exactamente igual si estuviera todo junto: la separación
es una decisión de organización nuestra, no una exigencia del framework.
"""

from datetime import datetime, timedelta, time

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q

from .models import Servicio, Clienta, Turno, DiaNoDisponible


# ---------------------------------------------------------------------------
# HORARIO HABITUAL DE MARÍA
# ---------------------------------------------------------------------------
# El documento dice que esto debería ser configurable por María (RF33),
# pero para no complicar este paso, lo dejamos como una constante fija acá.
# Más adelante, cuando hagamos esa parte del admin, esto se puede
# reemplazar por un modelo "ConfiguracionHorario" en la base de datos.
# Por ahora: Lunes a Viernes 10 a 18, Sábado 10 a 16, Domingo cerrado.
HORA_INICIO_SEMANA = time(10, 0)
HORA_FIN_SEMANA = time(18, 0)
HORA_INICIO_SABADO = time(10, 0)
HORA_FIN_SABADO = time(16, 0)

INTERVALO_MINUTOS = 30  # cada cuántos minutos "probamos" un horario posible


def lista_servicios(request):
    """
    RF01: Consultar servicios (nombre, precio y fotos).
    Nota: a propósito NO le pasamos "duracion_minutos" al template,
    aunque el objeto Servicio lo tenga. La clienta no debe verla.
    """
    servicios = Servicio.objects.filter(activo=True).prefetch_related("fotos")
    # prefetch_related("fotos"): esto trae las fotos de todos los servicios
    # en una sola consulta extra a la base de datos, en vez de hacer una
    # consulta nueva por cada servicio dentro del template. Es una
    # optimización típica cuando vas a recorrer una relación 1-a-muchos.
    return render(request, "turnos/lista_servicios.html", {"servicios": servicios})


def _dia_habilitado(fecha):
    """
    Función interna (empieza con "_") que responde: ¿ese día se puede
    trabajar? Chequea domingo y días marcados como no disponibles.
    Devuelve (habilitado: bool, hora_inicio, hora_fin).
    """
    if fecha.weekday() == 6:  # 6 = domingo en Python (lunes es 0)
        return False, None, None

    if DiaNoDisponible.objects.filter(fecha=fecha).exists():
        return False, None, None

    if fecha.weekday() == 5:  # 5 = sábado
        return True, HORA_INICIO_SABADO, HORA_FIN_SABADO
    return True, HORA_INICIO_SEMANA, HORA_FIN_SEMANA


def _turnos_ocupan_horario(ahora):
    """
    Devuelve un objeto Q (consulta OR de Django) que filtra turnos que
    "cuentan" como ocupando un horario: confirmados, o pendientes cuya
    reserva de 5 minutos todavía no venció.
    Lo separamos en una función aparte solo para que _horarios_disponibles
    no quede tan largo y se entienda mejor cada parte.
    """
    return (
        Q(estado=Turno.Estado.CONFIRMADO)
        | Q(estado=Turno.Estado.PENDIENTE, reservado_hasta__gte=ahora)
    )


def _horarios_disponibles(servicio, fecha):
    """
    RF03 / RF37: calcula los horarios disponibles para un servicio en
    una fecha dada, teniendo en cuenta la duración del servicio y los
    turnos que ya existen ese día.
    """
    habilitado, hora_inicio, hora_fin = _dia_habilitado(fecha)
    if not habilitado:
        return []

    duracion = timedelta(minutes=servicio.duracion_minutos)

    # Traemos los turnos de ESE día que "ocupan" horario: los confirmados,
    # y los pendientes cuya reserva temporal todavía no venció (RF08/RF38).
    ahora = timezone.now()
    turnos_ocupados = Turno.objects.filter(
        fecha=fecha,
    ).exclude(
        estado__in=[Turno.Estado.CANCELADO, Turno.Estado.NO_SHOW, Turno.Estado.LIBERADO]
    ).filter(
        _turnos_ocupan_horario(ahora)
    ).select_related("servicio")

    # Armamos una lista de intervalos ya ocupados: (inicio, fin) en datetime
    ocupados = []
    for t in turnos_ocupados:
        inicio_ocupado = datetime.combine(t.fecha, t.hora)
        fin_ocupado = inicio_ocupado + timedelta(minutes=t.servicio.duracion_minutos)
        ocupados.append((inicio_ocupado, fin_ocupado))

    # Ahora generamos horarios candidatos cada INTERVALO_MINUTOS, y
    # descartamos los que se superpongan con algo ya ocupado, o que
    # terminen después de la hora de cierre.
    disponibles = []
    cursor = datetime.combine(fecha, hora_inicio)
    fin_jornada = datetime.combine(fecha, hora_fin)

    while cursor + duracion <= fin_jornada:
        candidato_inicio = cursor
        candidato_fin = cursor + duracion

        se_superpone = any(
            candidato_inicio < fin_o and candidato_fin > inicio_o
            for (inicio_o, fin_o) in ocupados
        )
        # Esta condición es la fórmula clásica para "dos intervalos se
        # superponen": A empieza antes de que termine B, Y A termina
        # después de que empieza B.

        if not se_superpone:
            disponibles.append(candidato_inicio.time())

        cursor += timedelta(minutes=INTERVALO_MINUTOS)

    return disponibles


def solicitar_turno(request, servicio_id):
    """
    Vista principal del flujo de reserva: RF02, RF03, RF04, RF05, RF06.
    - Si viene por GET con ?fecha=..., muestra los horarios de esa fecha.
    - Si viene por POST, procesa la solicitud del turno.
    """
    servicio = get_object_or_404(Servicio, pk=servicio_id, activo=True)

    horarios = []
    fecha_elegida = request.GET.get("fecha")

    if fecha_elegida:
        fecha_obj = datetime.strptime(fecha_elegida, "%Y-%m-%d").date()
        horarios = _horarios_disponibles(servicio, fecha_obj)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        fecha_post = request.POST.get("fecha")
        hora_post = request.POST.get("hora")

        # RF06: validar los datos obligatorios.
        if not nombre or not telefono or not fecha_post or not hora_post:
            messages.error(request, "Faltan datos obligatorios.")
            return redirect("solicitar_turno", servicio_id=servicio.id)

        # RF40: reconocer clienta existente por teléfono, o crearla si es nueva.
        clienta, creada = Clienta.objects.get_or_create(
            telefono=telefono, defaults={"nombre": nombre}
        )

        # RF41: una clienta bloqueada no puede solicitar turnos.
        if clienta.bloqueada:
            messages.error(request, "No es posible registrar el turno. Por favor, contactate con María.")
            return redirect("lista_servicios")

        fecha_obj = datetime.strptime(fecha_post, "%Y-%m-%d").date()
        hora_obj = datetime.strptime(hora_post, "%H:%M").time()

        # Volvemos a calcular los horarios disponibles justo antes de
        # crear el turno (no confiamos en lo que mandó el formulario):
        # esto es lo que evita RF38 (superposición), incluso si dos
        # personas están mirando la misma fecha al mismo tiempo.
        disponibles_ahora = _horarios_disponibles(servicio, fecha_obj)
        if hora_obj not in disponibles_ahora:
            messages.error(request, "Ese horario ya no está disponible. Elegí otro.")
            return redirect(f"/turnos/solicitar/{servicio.id}/?fecha={fecha_post}")

        # Creamos el turno en estado PENDIENTE con la reserva temporal
        # de 5 minutos (RN03/RF08), congelando precio y seña (RN17).
        turno = Turno.objects.create(
            clienta=clienta,
            servicio=servicio,
            fecha=fecha_obj,
            hora=hora_obj,
            estado=Turno.Estado.PENDIENTE,
            precio=servicio.precio,
            monto_sena=servicio.monto_sena,
            reservado_hasta=timezone.now() + timedelta(minutes=5),
        )

        return redirect("turno_reservado", turno_id=turno.id)

    return render(
        request,
        "turnos/solicitar_turno.html",
        {"servicio": servicio, "fecha_elegida": fecha_elegida, "horarios": horarios},
    )


def turno_reservado(request, turno_id):
    """
    Pantalla intermedia: el turno ya está PENDIENTE, reservado por 5
    minutos. Acá, en el paso siguiente, va a ir el botón real de pago
    con Mercado Pago (RF07). Por ahora mostramos los datos y un aviso.
    """
    turno = get_object_or_404(Turno, pk=turno_id)
    return render(request, "turnos/turno_reservado.html", {"turno": turno})


def mis_turnos(request):
    """
    RF12: la clienta consulta todos sus futuros turnos confirmados,
    identificándose solo por su teléfono (no hay login de clienta).
    """
    turnos = None
    telefono = request.GET.get("telefono")

    if telefono:
        hoy = timezone.now().date()
        turnos = Turno.objects.filter(
            clienta__telefono=telefono,
            estado=Turno.Estado.CONFIRMADO,
            fecha__gte=hoy,
        ).select_related("servicio")

    return render(request, "turnos/mis_turnos.html", {"turnos": turnos, "telefono": telefono})