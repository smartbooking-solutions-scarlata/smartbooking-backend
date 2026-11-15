import re
from datetime import datetime

from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import Usuario, Reserva


class UsuarioSerializer(serializers.ModelSerializer):
    # Perfil propio: no permite cambiar rol ni activo
    class Meta:
        model = Usuario
        fields = ['id_usuario', 'nombre', 'apellido', 'email', 'rol']
        read_only_fields = ['id_usuario', 'rol']


class UsuarioAdminSerializer(serializers.ModelSerializer):
    # Solo para el administrador: puede cambiar rol y activo
    class Meta:
        model = Usuario
        fields = ['id_usuario', 'nombre', 'apellido', 'email', 'rol', 'activo']
        read_only_fields = ['id_usuario', 'email']


class UsuarioCreateSerializer(serializers.ModelSerializer):
    # Registro: acepta la contraseña en texto plano y la guarda hasheada
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = Usuario
        fields = ['id_usuario', 'nombre', 'apellido', 'email', 'password', 'password_confirm']

    def validate_email(self, value):
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError('El email ya está registrado.')
        return value

    def validate_password(self, value):
        try:
            django_validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))

        if not re.search(r'[A-Za-z]', value) or not re.search(r'\d', value):
            raise serializers.ValidationError(
                'La contraseña debe ser alfanumérica (incluir letras y números).'
            )

        if not re.search(r'[^A-Za-z0-9]', value):
            raise serializers.ValidationError(
                'La contraseña debe incluir al menos un carácter especial.'
            )

        return value

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password': 'Las contraseñas no coinciden.'})
        return data

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class ReservaSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Reserva
        fields = ['id_reserva', 'id_usuario', 'usuario_nombre',
                  'fecha', 'hora_inicio', 'hora_fin', 'motivo']
        read_only_fields = ['id_reserva', 'id_usuario', 'usuario_nombre']

    def get_usuario_nombre(self, obj):
        return f'{obj.id_usuario.nombre} {obj.id_usuario.apellido}'

    def validate(self, data):
        # En una edición parcial (PATCH) faltan campos: se toman de la instancia
        inst = self.instance
        fecha = data.get('fecha', inst.fecha if inst else None)
        hora_inicio = data.get('hora_inicio', inst.hora_inicio if inst else None)
        hora_fin = data.get('hora_fin', inst.hora_fin if inst else None)

        # RN03: la hora de fin debe ser posterior a la de inicio
        if hora_fin <= hora_inicio:
            raise serializers.ValidationError(
                {'hora_fin': ['La hora de fin debe ser posterior a la hora de inicio.']}
            )

        # RN02: no se puede reservar en fechas u horarios pasados
        inicio = timezone.make_aware(datetime.combine(fecha, hora_inicio))
        if inicio < timezone.now():
            raise serializers.ValidationError(
                {'fecha': ['No se puede reservar en una fecha u horario pasado.']}
            )

        # RN01: no puede haber dos reservas superpuestas en la sala
        solapadas = Reserva.objects.filter(
            fecha=fecha,
            hora_inicio__lt=hora_fin,
            hora_fin__gt=hora_inicio,
        )
        if inst:
            solapadas = solapadas.exclude(pk=inst.pk)
        if solapadas.exists():
            raise serializers.ValidationError(
                {'detail': 'Ya existe una reserva en ese horario.'}
            )

        return data


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()