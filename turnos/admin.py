from django.contrib import admin
from .models import Servicio, Foto, Clienta, Turno, Sena, DiaNoDisponible


class FotoInline(admin.TabularInline):
    """
    Un "inline" permite editar las Fotos de un Servicio DESDE la misma
    página del Servicio, en vez de tener que ir a una sección aparte.
    Tiene sentido porque en el UML la relación es Servicio 1 —— 0..* Foto:
    las fotos no existen "solas", siempre pertenecen a un servicio.
    """
    model = Foto
    extra = 1  # muestra 1 espacio vacío extra para cargar una foto nueva


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):

    # list_display: qué columnas se ven en la lista de servicios
    list_display = ("nombre", "precio", "monto_sena", "duracion_minutos", "activo")

    # list_filter: agrega un filtro lateral (muy útil para separar
    # servicios activos de los desactivados/eliminados lógicamente)
    list_filter = ("activo",)

    # search_fields: agrega una barra de búsqueda por nombre
    search_fields = ("nombre",)
    
    # inlines: acá "engancho" el FotoInline de arriba, para poder cargar
    # fotos directamente al crear o editar un servicio
    inlines = [FotoInline]


@admin.register(Clienta)
class ClientaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "bloqueada")
    list_filter = ("bloqueada",)
    search_fields = ("nombre", "telefono")

    # actions personalizadas: agregan botones extra en la lista, para
    # bloquear/desbloquear varias clientas a la vez
    actions = ["bloquear_clientas", "desbloquear_clientas"]

    @admin.action(description="Bloquear clientas seleccionadas")
    def bloquear_clientas(self, request, queryset):
        # queryset son todas las filas que María tildó en la lista.
        # .update() las modifica a todas en una sola consulta a la base
        # de datos (más eficiente que un for guardando una por una).
        queryset.update(bloqueada=True)

    @admin.action(description="Desbloquear clientas seleccionadas")
    def desbloquear_clientas(self, request, queryset):
        queryset.update(bloqueada=False)


class SenaInline(admin.StackedInline):
    """
    Igual que FotoInline, pero para mostrar la Seña de un Turno dentro
    de la misma página del Turno (relación Turno 1 —— 1 Seña).
    StackedInline (en vez de Tabular) porque acá hay pocos campos y
    se ve mejor en formato "formulario" que en tabla.
    """
    model = Sena
    extra = 0  # no mostrar un espacio vacío extra (la seña se crea sola
               # cuando se procesa el pago, no la carga María a mano)


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ("id", "clienta", "servicio", "fecha", "hora", "estado", "creado_por_admin")
    # RF17 pide ver la agenda por día y ordenada por horario: el modelo
    # ya tiene ordering = ["fecha", "hora"] en su Meta, así que esto
    # se cumple automáticamente. Acá además dejamos filtrar por fecha/estado.
    
    list_filter = ("estado", "fecha", "creado_por_admin")
    search_fields = ("clienta__nombre", "clienta__telefono")
    # "clienta__nombre" busca en el nombre de la Clienta relacionada
    # (Django permite "cruzar" tablas relacionadas con doble guion bajo).
    date_hierarchy = "fecha"  # agrega una navegación tipo calendario arriba
    inlines = [SenaInline]


@admin.register(DiaNoDisponible)
class DiaNoDisponibleAdmin(admin.ModelAdmin):
    list_display = ("fecha", "motivo")


# Sena no la registramos aparte como su propia sección del menú, porque
# ya se ve/edita como inline dentro de Turno. Registrarla dos veces
# sería redundante para el uso que le va a dar María.