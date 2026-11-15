from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegistroView,
    LoginView,
    PerfilView,
    UsuarioViewSet,
    ReservaViewSet,
)

router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet, basename='usuario')
router.register(r'reservas', ReservaViewSet, basename='reserva')

urlpatterns = [
    path('auth/register/', RegistroView.as_view()),
    path('auth/login/', LoginView.as_view()),
    path('auth/refresh/', TokenRefreshView.as_view()),
    path('perfil/', PerfilView.as_view()),
    path('', include(router.urls)),
]