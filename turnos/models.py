from django.db import models
from django.contrib.auth.models import User  # Django ya trae un modelo de usuario con login, password, etc.
from django.utils import timezone


class Servicio(models.Model):
    """
    Representa un servicio de manicura (ej: Softgel, Acrílico, etc.)
    Corresponde a la clase "Servicio" del UML.
    """
    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    # DecimalField y no FloatField: para dinero siempre usamos Decimal,
    #los float pueden traer errores de redondeo

    duracion_minutos = models.PositiveIntegerField(
        help_text="Duración interna en minutos, usada para calcular disponibilidad."
    )
    # El documento dice: "La clienta no ve la duración". Por eso este campo
    # existe en el modelo (se usa internamente para los cálculos) pero
    # después, en las vistas, simplemente no lo vamos a mostrar a la clienta.
    # La seguridad de "no mostrar" no está en el modelo, está en qué
    # decidimos renderizar en cada vista/template.

    monto_sena = models.DecimalField(max_digits=10, decimal_places=2)

    activo = models.BooleanField(default=True)
    # Este campo no estaba explícito en el UML, pero lo necesitamos por
    # la regla RN18 / RF30: "un servicio con turnos futuros confirmados
    # no puede eliminarse". En vez de borrarlo de la base de datos
    # (lo que rompería el historial de turnos viejos que lo referencian),
    # lo desactivamos. Esto se llama "soft delete" (borrado lógico).

    def __str__(self):
        # Esto define cómo se ve el objeto en el panel de admin de Django.
        return self.nombre


class Foto(models.Model):
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="fotos",
    )
    imagen = models.ImageField(upload_to="servicios/")

    def __str__(self):
        return f"Foto de {self.servicio.nombre}"


class Clienta(models.Model):
    """
    Corresponde a la clase "Clienta" del UML.
    Importante: la clienta NO tiene usuario ni contraseña (así lo pide
    el relevamiento, punto 15: "No hay registro/login para clientas").
    Por eso este modelo no hereda de User ni tiene password.
    """
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, unique=True)
    # unique=True es clave acá: el documento dice (RF40) que el teléfono
    # se usa para reconocer una clienta existente y evitar duplicados.
    # Con unique=True, la base de datos misma nos impide crear dos
    # clientas con el mismo teléfono.

    bloqueada = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.nombre} ({self.telefono})"


class DiaNoDisponible(models.Model):
    """
    es solo una lista de fechas que se consulta aparte
    para calcular disponibilidad.
    """
    fecha = models.DateField(unique=True)
    motivo = models.CharField(max_length=200, blank=True) # "motivo" es opcional

    def __str__(self):
        return str(self.fecha)


class Turno(models.Model):
    # --- Estados posibles del turno ---
    # Uso"choices" en vez de un simple CharField libre, para
    # validar que el estado sea siempre uno de estos valores

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"      # reserva temporal, esperando pago
        CONFIRMADO = "CONFIRMADO", "Confirmado"   # seña pagada
        CANCELADO = "CANCELADO", "Cancelado"
        NO_SHOW = "NO_SHOW", "No se presentó"
        LIBERADO = "LIBERADO", "Liberado"         # se venció la reserva de 5 min sin pago

    clienta = models.ForeignKey(
        Clienta, on_delete=models.CASCADE, related_name="turnos"
    )
    servicio = models.ForeignKey(
        Servicio, on_delete=models.PROTECT, related_name="turnos"
    )
    # on_delete=PROTECT (y no CASCADE) en Servicio: si intenta
    # borrar un Servicio que tiene turnos, Django lo impide directamente
    # a nivel base de datos. 

    fecha = models.DateField()
    hora = models.TimeField()

    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )

    # --- Precios "congelados" al momento de reservar ---
    # Turno tiene SU PROPIO precio y seña, copiados desde el
    # Servicio en el momento de crear el turno.
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    monto_sena = models.DecimalField(max_digits=10, decimal_places=2)

    reservado_hasta = models.DateTimeField(null=True, blank=True)
    # Este campo guarda "hasta qué momento exacto" dura la reserva temporal
    # de 5 minutos (RN03). Cuando el turno pasa a Confirmado o Cancelado,
    # ya no lo necesitamos, por eso puede quedar vacío (null=True).

    creado_por_admin = models.BooleanField(default=False)
    # la manicura puede cargar turnos manualmente y confirmarlos
    # sin pasar por el pago online.

    creado_en = models.DateTimeField(auto_now_add=True)
    # la primera vez que se guarda el turno. Útil para el historial.

    def __str__(self):
        return f"Turno {self.id} - {self.clienta.nombre} - {self.fecha} {self.hora}"

    class Meta:
        # Esto simplemente hace que, por defecto, cuando pidamos una lista
        # de turnos, vengan ordenados por fecha y hora
        ordering = ["fecha", "hora"]


class Sena(models.Model):

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    turno = models.OneToOneField(
        Turno, on_delete=models.CASCADE, related_name="sena"
    )
    # OneToOneField (y no ForeignKey) porque la relación es 1 a 1:
    # cada turno tiene como máximo una seña, no varias.

    fecha = models.DateTimeField(auto_now_add=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )

    # para hacer mas adelante (guardar el ID de pago que nos devuelve su API)
    id_pago_mercadopago = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Seña turno {self.turno_id} - {self.estado}"