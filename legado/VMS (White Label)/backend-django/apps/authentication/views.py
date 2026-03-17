from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string
from apps.auth_app.models import User
from apps.authentication.permissions import RolePermission
from .serializers import (
    LoginSerializer, PasswordResetSerializer,
    PasswordResetConfirmSerializer, UserSerializer, UserCreateSerializer,
)


class CityAdminPermission(RolePermission):
    allowed_roles = ['city_admin', 'reseller_admin', 'super_admin']


class AuthViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @action(detail=False, methods=['post'])
    def login(self, request):
        """POST /api/v1/auth/login/"""
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Gera tokens JWT
        refresh = RefreshToken.for_user(user)
        
        # Adiciona claims customizados
        refresh['user_id'] = str(user.id)
        refresh['tenant_id'] = str(user.tenant_id) if user.tenant_id else None
        refresh['role'] = user.role
        refresh['reseller_id'] = str(request.reseller_id) if hasattr(request, 'reseller_id') else None
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """POST /api/v1/auth/logout/"""
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                # Adiciona token à blacklist no Redis
                cache.set(f'blacklist:{refresh_token}', '1', 60 * 60 * 24 * 7)  # 7 dias
            return Response({'detail': 'Logout realizado com sucesso.'})
        except Exception:
            return Response({'detail': 'Token inválido.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='password-reset')
    def password_reset(self, request):
        """POST /api/v1/auth/password-reset/"""
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email, active=True)
            
            # Gera token de reset
            token = get_random_string(64)
            cache.set(f'password_reset:{token}', str(user.id), 3600)  # 1 hora
            
            # Envia email com tema do reseller
            reseller = request.reseller if hasattr(request, 'reseller') else None
            
            context = {
                'user': user,
                'token': token,
                'reseller': reseller,
            }
            
            html_message = render_to_string('emails/password_reset.html', context)
            
            send_mail(
                subject=f'Recuperação de senha - {reseller.name if reseller else "Sistema"}',
                message='',
                from_email='noreply@example.com',
                recipient_list=[email],
                html_message=html_message,
            )
        except User.DoesNotExist:
            pass  # Não revela se email existe
        
        return Response({'detail': 'Se o email existir, você receberá instruções de recuperação.'})

    @action(detail=False, methods=['post'], url_path='password-reset/confirm')
    def password_reset_confirm(self, request):
        """POST /api/v1/auth/password-reset/confirm/"""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        password = serializer.validated_data['password']
        
        user_id = cache.get(f'password_reset:{token}')
        
        if not user_id:
            return Response({'detail': 'Token inválido ou expirado.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
            user.set_password(password)
            user.save()
            
            # Invalida token
            cache.delete(f'password_reset:{token}')
            
            return Response({'detail': 'Senha alterada com sucesso.'})
        except User.DoesNotExist:
            return Response({'detail': 'Usuário não encontrado.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """GET /api/v1/auth/me/"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    # ── Users CRUD ────────────────────────────────────────────────────────────

    @action(
        detail=False, methods=['get'],
        permission_classes=[IsAuthenticated, CityAdminPermission],
        url_path='users',
    )
    def users_list(self, request):
        """GET /api/v1/auth/users/"""
        from rest_framework.pagination import PageNumberPagination
        tenant_id = getattr(request, 'tenant_id', None)
        qs = User.objects.filter(tenant_id=tenant_id).order_by('email')

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        serializer = UserSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(
        detail=False, methods=['post'],
        permission_classes=[IsAuthenticated, CityAdminPermission],
        url_path='users/create',
    )
    def users_create(self, request):
        """POST /api/v1/auth/users/create/"""
        tenant_id = getattr(request, 'tenant_id', None)
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(tenant_id=tenant_id)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(
        detail=False, methods=['patch'],
        permission_classes=[IsAuthenticated, CityAdminPermission],
        url_path=r'users/(?P<user_id>[^/.]+)/update',
    )
    def users_update(self, request, user_id=None):
        """PATCH /api/v1/auth/users/{id}/update/"""
        tenant_id = getattr(request, 'tenant_id', None)
        try:
            user = User.objects.get(id=user_id, tenant_id=tenant_id)
        except User.DoesNotExist:
            return Response({'detail': 'Não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        password = data.pop('password', None)

        serializer = UserSerializer(user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()

        if password:
            updated_user.set_password(password)
            updated_user.save()

        return Response(UserSerializer(updated_user).data)

    @action(
        detail=False, methods=['delete'],
        permission_classes=[IsAuthenticated, CityAdminPermission],
        url_path=r'users/(?P<user_id>[^/.]+)/delete',
    )
    def users_delete(self, request, user_id=None):
        """DELETE /api/v1/auth/users/{id}/delete/"""
        tenant_id = getattr(request, 'tenant_id', None)
        if str(request.user.id) == str(user_id):
            return Response({'detail': 'Não é possível excluir o próprio usuário.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(id=user_id, tenant_id=tenant_id)
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except User.DoesNotExist:
            return Response({'detail': 'Não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    @action(
        detail=False, methods=['patch'],
        permission_classes=[IsAuthenticated],
        url_path='users/me/update',
    )
    def me_update(self, request):
        """PATCH /api/v1/auth/users/me/update/ — atualiza o próprio perfil"""
        data = request.data.copy()
        password = data.pop('new_password', None)
        current_password = data.pop('current_password', None)

        if password:
            if not current_password or not request.user.check_password(current_password):
                return Response({'detail': 'Senha atual incorreta.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = UserSerializer(request.user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        if password:
            user.set_password(password)
            user.save()

        return Response(UserSerializer(user).data)
