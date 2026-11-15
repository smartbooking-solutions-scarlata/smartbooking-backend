import logging

from django.contrib.auth.hashers import check_password
from django.http import Http404
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Usuario, Reserva
from .permissions import IsAdminRole, IsOwnerOrAdmin
from .serializers import (
    UsuarioSerializer,
    UsuarioAdminSerializer,
    UsuarioCreateSerializer,
    LoginSerializer,
    ReservaSerializer,
)

logger = logging.getLogger('security')


# REGISTRO
class RegistroView(APIView):
    # POST /api/auth/register/  (público)
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    def post(self, request):
        serializer = UsuarioCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.save()
        return Response({
            'id_usuario': usuario.id_usuario,
            'nombre': usuario.nombre,
            'apellido': usuario.apellido,
            'email': usuario.email,
            'rol': usuario.rol,
            'mensaje': 'Registro exitoso',
        }, status=status.HTTP_201_CREATED)


# LOGIN
class LoginView(APIView):
    # POST /api/auth/login/  (público)
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        ip = request.META.get('REMOTE_ADDR')

        usuario = Usuario.objects.filter(email=email).first()

        # Mismo mensaje si el email no existe o la contraseña está mal
        if not usuario or not check_password(password, usuario.password):
            logger.warning(
                'Login fallido | email=%s | ip=%s | accion=login | resultado=DENEGADO',
                email, ip
            )
            return Response({'detail': 'Credenciales incorrectas.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        if not usuario.activo:
            logger.warning(
                'Login de usuario desactivado | usuario=%s | ip=%s | resultado=DENEGADO',
                usuario.id_usuario, ip
            )
            return Response({'detail': 'Credenciales incorrectas.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(usuario)
        refresh['rol'] = usuario.rol
        refresh['email'] = usuario.email

        return Response({
            'id_usuario': usuario.id_usuario,
            'nombre': usuario.nombre,
            'apellido': usuario.apellido,
            'email': usuario.email,
            'rol': usuario.rol,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'mensaje': 'Login exitoso',
        }, status=status.HTTP_200_OK)


# PERFIL
class PerfilView(APIView):
    # GET / PUT /api/perfil/  (usuario autenticado)
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)

    def put(self, request):
        serializer = UsuarioSerializer(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# USUARIOS (solo administrador)
class UsuarioViewSet(viewsets.ModelViewSet):
    # GET /api/usuarios/  y  GET / PATCH /api/usuarios/{id}/
    permission_classes = [IsAdminRole]
    queryset = Usuario.objects.all()
    serializer_class = UsuarioAdminSerializer
    http_method_names = ['get', 'patch', 'head', 'options']


# RESERVAS
class ReservaViewSet(viewsets.ModelViewSet):
    # GET / POST /api/reservas/  y  GET / PUT / PATCH / DELETE /api/reservas/{id}/
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    queryset = Reserva.objects.select_related('id_usuario')
    serializer_class = ReservaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'rol', None) == 'administrador':
            return qs
        return qs.filter(id_usuario=user)   # RN04 y RN05

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            # Si la reserva existe pero no es suya, queda registrado
            pk = self.kwargs.get('pk')
            if Reserva.objects.filter(pk=pk).exists():
                logger.warning(
                    'Acceso denegado a reserva ajena | usuario=%s | reserva=%s | accion=%s | resultado=DENEGADO',
                    self.request.user.id_usuario, pk, self.action
                )
            raise

    def perform_create(self, serializer):
        serializer.save(id_usuario=self.request.user)