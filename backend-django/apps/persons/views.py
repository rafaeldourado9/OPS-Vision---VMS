import json
import os
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from apps.authentication.permissions import RolePermission
from .models import KnownPerson, PersonPhoto
from .serializers import (
    KnownPersonSerializer,
    KnownPersonInternalSerializer,
    PersonPhotoSerializer,
)


class CityAdminPermission(RolePermission):
    allowed_roles = ['city_admin', 'reseller_admin', 'super_admin']


class KnownPersonViewSet(viewsets.ModelViewSet):
    """CRUD de pessoas cadastradas para reconhecimento facial."""

    serializer_class = KnownPersonSerializer
    permission_classes = [IsAuthenticated, CityAdminPermission]

    def get_queryset(self):
        tenant_id = getattr(self.request, 'tenant_id', None)
        qs = KnownPerson.objects.filter(tenant_id=tenant_id).prefetch_related('extra_photos')

        active = self.request.query_params.get('active')
        if active is not None:
            qs = qs.filter(active=active.lower() == 'true')

        name = self.request.query_params.get('name')
        if name:
            qs = qs.filter(name__icontains=name)

        return qs

    def perform_create(self, serializer):
        tenant_id = self.request.tenant_id
        person = serializer.save(tenant_id=tenant_id)
        self._publish_persons_updated()
        return person

    def perform_update(self, serializer):
        person = serializer.save()
        self._publish_persons_updated()
        return person

    def perform_destroy(self, instance):
        # Remove foto principal e extras do disco
        if instance.photo:
            try:
                os.remove(instance.photo.path)
            except FileNotFoundError:
                pass
        for extra in instance.extra_photos.all():
            try:
                os.remove(extra.photo.path)
            except FileNotFoundError:
                pass
        instance.delete()
        self._publish_persons_updated()

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser], url_path='photos')
    def add_photo(self, request, pk=None):
        """Upload de foto adicional (ângulo diferente) para melhorar reconhecimento."""
        person = self.get_object()
        photo = request.FILES.get('photo')
        if not photo:
            return Response({'detail': 'Campo "photo" obrigatório.'},
                            status=status.HTTP_400_BAD_REQUEST)

        label = request.data.get('label', '')
        extra = PersonPhoto.objects.create(person=person, photo=photo, label=label)
        self._publish_persons_updated()
        return Response(PersonPhotoSerializer(extra, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='photos/(?P<photo_id>[^/.]+)')
    def remove_photo(self, request, pk=None, photo_id=None):
        """Remove foto extra de uma pessoa."""
        person = self.get_object()
        try:
            extra = person.extra_photos.get(id=photo_id)
        except PersonPhoto.DoesNotExist:
            return Response({'detail': 'Foto não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            os.remove(extra.photo.path)
        except FileNotFoundError:
            pass
        extra.delete()
        self._publish_persons_updated()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _publish_persons_updated(self):
        """Notifica o Facial Worker para recarregar embeddings."""
        try:
            import pika
            rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
            connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
            channel = connection.channel()
            channel.queue_declare(queue='persons.updated', durable=True)
            channel.basic_publish(
                exchange='',
                routing_key='persons.updated',
                body=json.dumps({'action': 'reload'}),
            )
            connection.close()
        except Exception as e:
            print(f'[KnownPersonViewSet] Erro ao publicar persons.updated: {e}')


class InternalPersonsView(APIView):
    """
    Endpoint interno usado pelo Facial Worker para buscar todas as pessoas ativas
    com caminhos de todas as fotos (principal + extras).
    Protegido por X-Internal-Key no header.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        expected_key = os.getenv('INTERNAL_API_KEY', 'changeme-internal-key')
        provided_key = request.headers.get('X-Internal-Key', '')

        if provided_key != expected_key:
            return Response({'detail': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        persons = (
            KnownPerson.objects
            .filter(active=True)
            .select_related('tenant')
            .prefetch_related('extra_photos')
        )
        serializer = KnownPersonInternalSerializer(persons, many=True)
        return Response(serializer.data)
