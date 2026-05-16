"""
Autenticación JWT personalizada usando la tabla Usuario (no django.auth.User).
El token guarda: id_usuario, email, rol_id, empresa_id.
"""
import hashlib
from datetime import timedelta
from django.conf import settings
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Usuario


def _hash(clave: str) -> str:
    return hashlib.sha256(clave.encode()).hexdigest()


class CustomRefreshToken(RefreshToken):
    """Agrega claims extra al token."""
    @classmethod
    def for_usuario(cls, usuario: Usuario):
        token = cls()
        token['id_usuario']  = usuario.id_usuario
        token['email']       = usuario.email
        token['nombre']      = usuario.nombre
        token['rol_id']      = usuario.rol_id
        token['empresa_id']  = usuario.empresa_id
        return token


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    clave = serializers.CharField(write_only=True)


class LoginView(APIView):
    """POST /api/auth/login/  →  { access, refresh, usuario }"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        clave = serializer.validated_data['clave']

        try:
            usuario = Usuario.objects.select_related('rol','empresa').get(
                email=email, clave=_hash(clave), activo=True
            )
        except Usuario.DoesNotExist:
            return Response({'detail': 'Credenciales inválidas.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Actualizar último acceso
        from django.utils import timezone
        usuario.ultimo_acceso = timezone.now()
        usuario.save(update_fields=['ultimo_acceso'])

        refresh = CustomRefreshToken.for_usuario(usuario)
        return Response({
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
            'usuario': {
                'id_usuario':  usuario.id_usuario,
                'nombre':      usuario.nombre,
                'email':       usuario.email,
                'rol_id':      usuario.rol_id,
                'rol':         usuario.rol.descripcion,
                'empresa_id':  usuario.empresa_id,
                'empresa':     usuario.empresa.nombre if usuario.empresa else None,
            }
        })


class RefreshView(APIView):
    """POST /api/auth/refresh/  →  { access }"""
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'detail': 'refresh requerido.'}, status=400)
        try:
            token  = CustomRefreshToken(refresh_token)
            access = str(token.access_token)
            return Response({'access': access})
        except Exception:
            return Response({'detail': 'Token inválido o expirado.'}, status=401)



