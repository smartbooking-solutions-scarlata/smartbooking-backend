import logging

from django.contrib.auth.hashers import check_password
from django.http import Http404
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import Usuario, Reserva, TokenBloqueado
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
# REFRESH
class RefreshView(APIView):
    # POST /api/auth/refresh/  (público: se valida el refresh que viene en el body)
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get('refresh')
        if not token_str:
            return Response({'refresh': ['Este campo es obligatorio.']},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            refresh = RefreshToken(token_str)
        except TokenError:
            return Response({'detail': 'Token inválido o expirado.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        if TokenBloqueado.objects.filter(jti=refresh['jti']).exists():
            logger.warning(
                'Refresh con token bloqueado | ip=%s | resultado=DENEGADO',
                request.META.get('REMOTE_ADDR')
            )
            return Response({'detail': 'Token inválido o expirado.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        usuario = Usuario.objects.filter(pk=refresh.get('user_id')).first()
        if not usuario or not usuario.activo:
            return Response({'detail': 'Token inválido o expirado.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        # Rotación: el refresh usado queda bloqueado y se entrega uno nuevo
        TokenBloqueado.objects.get_or_create(jti=refresh['jti'])
        nuevo = RefreshToken.for_user(usuario)
        nuevo['rol'] = usuario.rol
        nuevo['email'] = usuario.email
        return Response({
            'access': str(nuevo.access_token),
            'refresh': str(nuevo),
        }, status=status.HTTP_200_OK)
# LOGOUT
class LogoutView(APIView):
    # POST /api/auth/logout/  (usuario autenticado)
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token_str = request.data.get('refresh')
        if not token_str:
            return Response({'refresh': ['Este campo es obligatorio.']},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            refresh = RefreshToken(token_str)
        except TokenError:
            return Response({'detail': 'Token inválido o expirado.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Solo se puede cerrar la sesión propia
        if str(refresh.get('user_id')) != str(request.user.id_usuario):
            logger.warning(
                'Logout con refresh ajeno | usuario=%s | resultado=DENEGADO',
                request.user.id_usuario
            )
            return Response({'detail': 'El token no pertenece a este usuario.'},
                            status=status.HTTP_403_FORBIDDEN)

        TokenBloqueado.objects.get_or_create(jti=refresh['jti'])
        return Response({'mensaje': 'Sesión cerrada correctamente.'},
                        status=status.HTTP_200_OK)


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
    def perform_update(self, serializer):
        antes = {'rol': serializer.instance.rol, 'activo': serializer.instance.activo}
        usuario = serializer.save()
        logger.info(
            'Modificacion administrativa | admin=%s | accion=PATCH | recurso=usuario/%s | '
            'rol: %s->%s | activo: %s->%s | resultado=OK',
            self.request.user.id_usuario, usuario.id_usuario,
            antes['rol'], usuario.rol, antes['activo'], usuario.activo
        )


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