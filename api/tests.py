from datetime import date, time, timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Usuario, Reserva

PASSWORD = 'Coworking2026!'


def crear_usuario(email, rol='usuario'):
    return Usuario.objects.create(
        nombre='Test', apellido='Test', email=email,
        password=make_password(PASSWORD), rol=rol,
    )


class SeguridadAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_aut_api_01_registro_con_password_debil_es_rechazado(self):
        datos = {
            'nombre': 'Ana', 'apellido': 'Perez', 'email': 'ana@test.com',
            'password': '12345678', 'password_confirm': '12345678',
        }
        r = self.client.post('/api/auth/register/', datos, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('password', r.data)

    def test_aut_api_02_reservas_sin_token_devuelve_401(self):
        r = self.client.get('/api/reservas/')
        self.assertEqual(r.status_code, 401)

    def test_aut_api_03_usuario_no_ve_reserva_ajena(self):
        dueno = crear_usuario('dueno@test.com')
        otro = crear_usuario('otro@test.com')
        reserva = Reserva.objects.create(
            id_usuario=dueno,
            fecha=date.today() + timedelta(days=30),
            hora_inicio=time(10, 0), hora_fin=time(12, 0),
            motivo='Reunion',
        )
        self.client.force_authenticate(user=otro)
        r = self.client.get(f'/api/reservas/{reserva.id_reserva}/')
        self.assertEqual(r.status_code, 404)

    def test_aut_api_04_usuario_comun_no_accede_a_usuarios(self):
        comun = crear_usuario('comun@test.com')
        self.client.force_authenticate(user=comun)
        r = self.client.get('/api/usuarios/')
        self.assertEqual(r.status_code, 403)
