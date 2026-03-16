"""Testes para agent/config.py."""
import os
from unittest import mock

import pytest

from agent.config import AgentConfig


class TestAgentConfigFromEnv:
    """Testes para AgentConfig.from_env()."""

    def test_from_env_reads_required_vars(self):
        """Carrega api_url e api_key de variáveis de ambiente."""
        env = {
            "VMS_API_URL": "https://cloud.example.com/api/v1",
            "VMS_API_KEY": "test-key-123",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = AgentConfig.from_env()

        assert config.api_url == "https://cloud.example.com/api/v1"
        assert config.api_key == "test-key-123"

    def test_from_env_uses_defaults(self):
        """Usa valores padrão quando opcionais não estão definidos."""
        env = {
            "VMS_API_URL": "https://cloud.example.com/api/v1",
            "VMS_API_KEY": "test-key-123",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = AgentConfig.from_env()

        assert config.poll_interval == 30
        assert config.heartbeat_interval == 60
        assert config.rtmp_base_url == "rtmp://localhost:1935"
        assert config.log_level == "INFO"
        assert config.request_timeout == 10.0

    def test_from_env_reads_optional_vars(self):
        """Carrega variáveis opcionais corretamente."""
        env = {
            "VMS_API_URL": "https://cloud.example.com/api/v1",
            "VMS_API_KEY": "test-key-123",
            "VMS_RTMP_URL": "rtmp://media.example.com:1935",
            "VMS_POLL_INTERVAL": "15",
            "VMS_HEARTBEAT_INTERVAL": "30",
            "VMS_LOG_LEVEL": "debug",
            "VMS_REQUEST_TIMEOUT": "5",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = AgentConfig.from_env()

        assert config.rtmp_base_url == "rtmp://media.example.com:1935"
        assert config.poll_interval == 15
        assert config.heartbeat_interval == 30
        assert config.log_level == "DEBUG"
        assert config.request_timeout == 5.0

    def test_from_env_strips_trailing_slash(self):
        """Remove barra final de URLs."""
        env = {
            "VMS_API_URL": "https://cloud.example.com/api/v1/",
            "VMS_API_KEY": "test-key-123",
            "VMS_RTMP_URL": "rtmp://media.example.com:1935/",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = AgentConfig.from_env()

        assert config.api_url == "https://cloud.example.com/api/v1"
        assert config.rtmp_base_url == "rtmp://media.example.com:1935"

    def test_from_env_missing_api_url_raises(self):
        """Erro claro se VMS_API_URL ausente."""
        env = {"VMS_API_KEY": "test-key-123"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="VMS_API_URL"):
                AgentConfig.from_env()

    def test_from_env_missing_api_key_raises(self):
        """Erro claro se VMS_API_KEY ausente."""
        env = {"VMS_API_URL": "https://cloud.example.com/api/v1"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="VMS_API_KEY"):
                AgentConfig.from_env()
