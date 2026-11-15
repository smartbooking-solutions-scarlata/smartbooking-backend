from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    RegistroView,
    LoginView,
    RefreshView,
    LogoutView,
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
    path('auth/refresh/', RefreshView.as_view()),
    path('auth/logout/', LogoutView.as_view()),
    path('perfil/', PerfilView.as_view()),
    path('', include(router.urls)),
]