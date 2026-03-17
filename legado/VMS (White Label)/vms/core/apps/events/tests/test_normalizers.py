"""Testes unitários para normalizers de ALPR."""
from datetime import datetime

import pytest

from apps.events.normalizers import (
    UnsupportedManufacturerError,
    normalize_alpr_payload,
)
from apps.events.services import ALPRDetectionInput


@pytest.mark.unit
class TestNormalizeAlprPayload:
    """Testes do dispatcher de normalização."""

    def test_unsupported_manufacturer_raises_error(self):
        """Erro para fabricante não suportado."""
        with pytest.raises(UnsupportedManufacturerError) as exc_info:
            normalize_alpr_payload("samsung", 1, {})

        assert "samsung" in str(exc_info.value)

    def test_returns_alpr_detection_input(self):
        """Retorna instância de ALPRDetectionInput."""
        payload = {
            "PlateResult": {
                "plate_number": "ABC-1D23",
                "confidence": 0.92,
                "capture_time": "2026-03-13 10:30:00",
                "channel": 1,
            },
        }

        result = normalize_alpr_payload("intelbras", 5, payload)

        assert isinstance(result, ALPRDetectionInput)


@pytest.mark.unit
class TestHikvisionNormalizer:
    """Testes do normalizer Hikvision."""

    def setup_method(self):
        """Payload Hikvision típico."""
        self.camera_id = 10
        self.raw_payload = {
            "EventNotificationAlert": {
                "channelID": "1",
                "dateTime": "2026-03-13T10:30:00-03:00",
                "ANPR": {
                    "licensePlate": "ABC1D23",
                    "confidenceLevel": 95,
                    "pictureURL": "http://cam.local/snapshot.jpg",
                },
            },
        }

    def test_extracts_plate(self):
        """Extrai placa do payload Hikvision."""
        result = normalize_alpr_payload(
            "hikvision", self.camera_id, self.raw_payload,
        )

        assert result.plate == "ABC1D23"

    def test_extracts_confidence_as_decimal(self):
        """Converte confiança de 0-100 para 0.0-1.0."""
        result = normalize_alpr_payload(
            "hikvision", self.camera_id, self.raw_payload,
        )

        assert result.confidence == 0.95

    def test_parses_timestamp_as_datetime(self):
        """Converte timestamp ISO para datetime."""
        result = normalize_alpr_payload(
            "hikvision", self.camera_id, self.raw_payload,
        )

        assert isinstance(result.timestamp, datetime)
        assert result.timestamp.year == 2026
        assert result.timestamp.month == 3
        assert result.timestamp.day == 13

    def test_extracts_image_url(self):
        """Extrai URL da imagem quando presente."""
        result = normalize_alpr_payload(
            "hikvision", self.camera_id, self.raw_payload,
        )

        assert result.image_url == "http://cam.local/snapshot.jpg"

    def test_image_url_none_when_missing(self):
        """image_url é None quando não presente no payload."""
        del self.raw_payload["EventNotificationAlert"]["ANPR"]["pictureURL"]

        result = normalize_alpr_payload(
            "hikvision", self.camera_id, self.raw_payload,
        )

        assert result.image_url is None

    def test_uses_provided_camera_id(self):
        """Usa camera_id passado como parâmetro, não do payload."""
        result = normalize_alpr_payload(
            "hikvision", 42, self.raw_payload,
        )

        assert result.camera_id == 42


@pytest.mark.unit
class TestIntelbrasNormalizer:
    """Testes do normalizer Intelbras."""

    def setup_method(self):
        """Payload Intelbras típico."""
        self.camera_id = 20
        self.raw_payload = {
            "PlateResult": {
                "plate_number": "ABC-1D23",
                "confidence": 0.92,
                "capture_time": "2026-03-13 10:30:00",
                "channel": 1,
                "picture_url": "http://cam.local/plate.jpg",
            },
        }

    def test_extracts_plate(self):
        """Extrai placa do payload Intelbras."""
        result = normalize_alpr_payload(
            "intelbras", self.camera_id, self.raw_payload,
        )

        assert result.plate == "ABC-1D23"

    def test_extracts_confidence(self):
        """Extrai confiança (já em 0.0-1.0)."""
        result = normalize_alpr_payload(
            "intelbras", self.camera_id, self.raw_payload,
        )

        assert result.confidence == 0.92

    def test_parses_timestamp_as_datetime(self):
        """Converte timestamp para datetime."""
        result = normalize_alpr_payload(
            "intelbras", self.camera_id, self.raw_payload,
        )

        assert isinstance(result.timestamp, datetime)
        assert result.timestamp.year == 2026
        assert result.timestamp.hour == 10

    def test_extracts_image_url(self):
        """Extrai URL da imagem quando presente."""
        result = normalize_alpr_payload(
            "intelbras", self.camera_id, self.raw_payload,
        )

        assert result.image_url == "http://cam.local/plate.jpg"

    def test_image_url_none_when_missing(self):
        """image_url é None quando não presente."""
        del self.raw_payload["PlateResult"]["picture_url"]

        result = normalize_alpr_payload(
            "intelbras", self.camera_id, self.raw_payload,
        )

        assert result.image_url is None

    def test_uses_provided_camera_id(self):
        """Usa camera_id passado como parâmetro."""
        result = normalize_alpr_payload(
            "intelbras", 99, self.raw_payload,
        )

        assert result.camera_id == 99

    def test_manufacturer_case_insensitive(self):
        """Aceita nome do fabricante em qualquer case."""
        result = normalize_alpr_payload(
            "Intelbras", self.camera_id, self.raw_payload,
        )

        assert result.plate == "ABC-1D23"


@pytest.mark.unit
class TestGenericNormalizer:
    """Testes do normalizer genérico (fallback)."""

    def setup_method(self):
        """Payload genérico típico."""
        self.camera_id = 30
        self.raw_payload = {
            "plate": "XYZ9A87",
            "confidence": 0.88,
            "timestamp": "2026-03-13T10:30:00Z",
            "image_url": "http://cam.local/snap.jpg",
        }

    def test_extracts_plate(self):
        """Extrai placa do payload genérico."""
        result = normalize_alpr_payload(
            "generic", self.camera_id, self.raw_payload,
        )

        assert result.plate == "XYZ9A87"

    def test_extracts_confidence(self):
        """Extrai confiança."""
        result = normalize_alpr_payload(
            "generic", self.camera_id, self.raw_payload,
        )

        assert result.confidence == 0.88

    def test_parses_timestamp_as_datetime(self):
        """Converte timestamp ISO para datetime."""
        result = normalize_alpr_payload(
            "generic", self.camera_id, self.raw_payload,
        )

        assert isinstance(result.timestamp, datetime)
        assert result.timestamp.year == 2026

    def test_extracts_image_url(self):
        """Extrai URL da imagem quando presente."""
        result = normalize_alpr_payload(
            "generic", self.camera_id, self.raw_payload,
        )

        assert result.image_url == "http://cam.local/snap.jpg"

    def test_image_url_none_when_missing(self):
        """image_url é None quando não presente."""
        del self.raw_payload["image_url"]

        result = normalize_alpr_payload(
            "generic", self.camera_id, self.raw_payload,
        )

        assert result.image_url is None

    def test_uses_provided_camera_id(self):
        """Usa camera_id passado como parâmetro."""
        result = normalize_alpr_payload(
            "generic", 77, self.raw_payload,
        )

        assert result.camera_id == 77

    def test_timestamp_defaults_to_now_when_missing(self):
        """Timestamp usa datetime.now quando não presente."""
        del self.raw_payload["timestamp"]

        result = normalize_alpr_payload(
            "generic", self.camera_id, self.raw_payload,
        )

        assert isinstance(result.timestamp, datetime)
        assert result.timestamp.tzinfo is not None

    def test_confidence_coerced_to_float(self):
        """Confidence é convertida para float mesmo se vier como int."""
        self.raw_payload["confidence"] = 1

        result = normalize_alpr_payload(
            "generic", self.camera_id, self.raw_payload,
        )

        assert result.confidence == 1.0
        assert isinstance(result.confidence, float)


@pytest.mark.unit
class TestNormalizerInvalidPayloads:
    """Testes de payloads inválidos para cada fabricante."""

    def test_hikvision_missing_anpr_key_raises(self):
        """Hikvision sem chave ANPR levanta KeyError."""
        payload = {"EventNotificationAlert": {"channelID": "1"}}

        with pytest.raises(KeyError):
            normalize_alpr_payload("hikvision", 1, payload)

    def test_hikvision_empty_payload_raises(self):
        """Hikvision com payload vazio levanta KeyError."""
        with pytest.raises(KeyError):
            normalize_alpr_payload("hikvision", 1, {})

    def test_intelbras_missing_plate_result_raises(self):
        """Intelbras sem chave PlateResult levanta KeyError."""
        with pytest.raises(KeyError):
            normalize_alpr_payload("intelbras", 1, {})

    def test_generic_missing_plate_raises(self):
        """Genérico sem campo plate levanta KeyError."""
        with pytest.raises(KeyError):
            normalize_alpr_payload("generic", 1, {"confidence": 0.9})

    def test_generic_missing_confidence_raises(self):
        """Genérico sem campo confidence levanta KeyError."""
        with pytest.raises(KeyError):
            normalize_alpr_payload("generic", 1, {"plate": "ABC1234"})
