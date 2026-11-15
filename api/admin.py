from django.contrib import admin

from .models import Usuario, Reserva


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('id_usuario', 'nombre', 'apellido', 'email', 'rol', 'activo')
    list_filter = ('rol', 'activo')
    search_fields = ('email', 'nombre', 'apellido')
    readonly_fields = ('password',)


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ('id_reserva', 'id_usuario', 'fecha', 'hora_inicio', 'hora_fin')
    list_filter = ('fecha',)