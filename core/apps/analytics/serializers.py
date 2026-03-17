"""Serializers para analytics."""
from rest_framework import serializers

from .models import DwellEvent, FaceDetectionEvent, FaceProfile, RegionOfInterest


class RegionOfInterestSerializer(serializers.ModelSerializer):
    """Serializer completo para ROI."""

    class Meta:
        model = RegionOfInterest
        fields = [
            "id",
            "camera",
            "name",
            "ia_type",
            "polygon_points",
            "config",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RegionOfInterestCreateSerializer(serializers.ModelSerializer):
    """Serializer para criação/atualização de ROI."""

    class Meta:
        model = RegionOfInterest
        fields = [
            "camera",
            "name",
            "ia_type",
            "polygon_points",
            "config",
            "is_active",
        ]


class FaceProfileSerializer(serializers.ModelSerializer):
    """Serializer para FaceProfile.

    O campo ``embedding`` é write-only — nunca exposto na API (dado biométrico).
    """

    embedding = serializers.JSONField(write_only=True)

    class Meta:
        model = FaceProfile
        fields = [
            "id",
            "name",
            "cpf",
            "notes",
            "embedding",
            "photo_path",
            "lgpd_consent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "photo_path", "created_at", "updated_at"]

    def validate_lgpd_consent(self, value: bool) -> bool:
        """Consentimento deve ser True para cadastrar."""
        if not value:
            raise serializers.ValidationError(
                "lgpd_consent deve ser True. Consentimento obrigatório para dados biométricos."
            )
        return value

    def validate_cpf(self, value: str) -> str:
        """Normaliza CPF para formato 000.000.000-00."""
        digits = "".join(c for c in value if c.isdigit())
        if value and len(digits) != 11:
            raise serializers.ValidationError("CPF deve ter 11 dígitos.")
        if digits:
            return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        return value


class FaceDetectionEventSerializer(serializers.ModelSerializer):
    """Serializer somente-leitura para FaceDetectionEvent."""

    camera_name = serializers.CharField(source="camera.name", read_only=True)
    profile_name = serializers.CharField(source="face_profile.name", read_only=True, default=None)
    roi_name = serializers.CharField(source="roi.name", read_only=True, default=None)

    class Meta:
        model = FaceDetectionEvent
        fields = [
            "id",
            "camera",
            "camera_name",
            "roi",
            "roi_name",
            "face_profile",
            "profile_name",
            "confidence",
            "is_unknown",
            "frame_path",
            "created_at",
        ]
        read_only_fields = fields


class DwellEventSerializer(serializers.ModelSerializer):
    """Serializer para DwellEvent."""

    camera_name = serializers.CharField(source="camera.name", read_only=True)
    roi_name = serializers.CharField(source="roi.name", read_only=True, default=None)

    class Meta:
        model = DwellEvent
        fields = [
            "id",
            "camera",
            "camera_name",
            "tenant",
            "roi",
            "roi_name",
            "track_id",
            "entered_at",
            "exited_at",
            "dwell_seconds",
            "frame_path",
            "clip",
            "is_valid",
            "created_at",
        ]
        read_only_fields = ["id", "tenant", "camera_name", "roi_name", "created_at"]
