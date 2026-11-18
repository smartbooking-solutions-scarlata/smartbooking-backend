import logging

from rest_framework import permissions

logger = logging.getLogger('security')


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        es_admin = bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "rol", None) == 'administrador'
        )
        # Autenticado pero sin rol de administrador: se deniega (403) y se registra
        if not es_admin and request.user and request.user.is_authenticated:
            logger.warning(
                'Acceso denegado (403) | usuario=%s | accion=%s | recurso=%s | resultado=DENEGADO',
                request.user.id_usuario, request.method, request.path
            )
        return es_admin


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if getattr(request.user, 'rol', None) == 'administrador':
            return True
        return obj.id_usuario == request.user