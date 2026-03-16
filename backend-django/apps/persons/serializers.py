from rest_framework import serializers
from .models import KnownPerson, PersonPhoto


class PersonPhotoSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = PersonPhoto
        fields = ['id', 'photo', 'photo_url', 'label', 'created_at']
        read_only_fields = ['id', 'created_at', 'photo_url']
        extra_kwargs = {'photo': {'write_only': True}}

    def get_photo_url(self, obj):
        request = self.context.get('request')
        if obj.photo and request:
            return request.build_absolute_uri(obj.photo.url)
        return None


class KnownPersonSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    extra_photos = PersonPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = KnownPerson
        fields = ['id', 'name', 'photo', 'photo_url', 'extra_photos', 'notes',
                  'active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'photo_url']
        extra_kwargs = {'photo': {'write_only': True}}

    def get_photo_url(self, obj):
        request = self.context.get('request')
        if obj.photo and request:
            return request.build_absolute_uri(obj.photo.url)
        return None


class PersonPhotoInternalSerializer(serializers.ModelSerializer):
    photo_path = serializers.SerializerMethodField()

    class Meta:
        model = PersonPhoto
        fields = ['photo_path', 'label']

    def get_photo_path(self, obj):
        if obj.photo:
            return obj.photo.path
        return None


class KnownPersonInternalSerializer(serializers.ModelSerializer):
    """Usado pelo Facial Worker para carregar pessoas com caminhos de todas as fotos."""
    tenant_id = serializers.UUIDField()
    photo_path = serializers.SerializerMethodField()
    extra_photos = PersonPhotoInternalSerializer(many=True, read_only=True)

    class Meta:
        model = KnownPerson
        fields = ['id', 'name', 'tenant_id', 'photo_path', 'extra_photos']

    def get_photo_path(self, obj):
        if obj.photo:
            return obj.photo.path
        return None
