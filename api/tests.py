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

class ReservasReglasTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.usuario = crear_usuario('reglas@test.com')
        self.client.force_authenticate(user=self.usuario)
        self.fecha = (date.today() + timedelta(days=30)).isoformat()

    def _reserva(self, inicio, fin):
        return self.client.post('/api/reservas/', {
            'fecha': self.fecha, 'hora_inicio': inicio,
            'hora_fin': fin, 'motivo': 'Prueba',
        }, format='json')

    def test_aut_api_05_crear_reserva_valida(self):
        r = self._reserva('10:00', '12:00')
        self.assertEqual(r.status_code, 201)

    def test_aut_api_06_rn01_rechaza_reserva_superpuesta(self):
        self._reserva('10:00', '12:00')
        r = self._reserva('11:00', '13:00')
        self.assertEqual(r.status_code, 400)

    def test_aut_api_07_rn02_rechaza_fecha_pasada(self):
        r = self.client.post('/api/reservas/', {
            'fecha': (date.today() - timedelta(days=1)).isoformat(),
            'hora_inicio': '10:00', 'hora_fin': '12:00', 'motivo': 'Pasada',
        }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_aut_api_08_rn03_fin_debe_ser_posterior_al_inicio(self):
        r = self._reserva('15:00', '14:00')
        self.assertEqual(r.status_code, 400)
        self.assertIn('hora_fin', r.data)

    def test_aut_api_09_reservas_consecutivas_no_se_superponen(self):
        self._reserva('10:00', '12:00')
        r = self._reserva('12:00', '14:00')
        self.assertEqual(r.status_code, 201)
