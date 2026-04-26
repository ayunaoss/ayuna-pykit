"""
Tests for ayuna_core.settings module.

Tests the settings configuration classes:
- LoggingEnv
- ServerSSLEnv
- ClientSSLEnv
"""

import os
import tempfile

import pytest

from ayuna_core.basetypes import LogLevelName
from ayuna_core.settings import (
    ClientSSLEnv,
    LoggingEnv,
    ServerSSLEnv,
)


class TestLoggingEnv:
    """Tests for LoggingEnv settings class."""

    def test_default_values(self):
        """Test LoggingEnv with default values."""
        env = LoggingEnv()

        assert env.debug is False
        assert env.logs_base_dir == "/tmp/logs"
        assert env.log_level == LogLevelName.INFO
        assert env.enable_file_logging is False
        assert env.log_max_file_bytes == 10 * 1024 * 1024
        assert env.log_max_file_count == 5
        assert env.enable_mproc_logging is False
        assert env.mproc_log_queue_size == 1_000_000

    def test_debug_mode_sets_log_level(self, monkeypatch):
        """Test that DEBUG=true sets log level to DEBUG."""
        monkeypatch.setenv("DEBUG", "true")

        env = LoggingEnv()

        assert env.debug is True
        assert env.log_level == LogLevelName.DEBUG

    def test_log_level_debug_sets_debug_flag(self, monkeypatch):
        """Test that LOG_LEVEL=DEBUG sets debug flag to True."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        env = LoggingEnv()

        assert env.log_level == LogLevelName.DEBUG
        assert env.debug is True

    def test_custom_log_level(self, monkeypatch):
        """Test setting custom log level."""
        monkeypatch.setenv("LOG_LEVEL", "WARNING")

        env = LoggingEnv()

        assert env.log_level == LogLevelName.WARNING

    def test_enable_file_logging(self, monkeypatch):
        """Test enabling file logging."""
        monkeypatch.setenv("ENABLE_FILE_LOGGING", "true")
        monkeypatch.setenv("LOG_MAX_FILE_BYTES", "5242880")
        monkeypatch.setenv("LOG_MAX_FILE_COUNT", "3")

        env = LoggingEnv()

        assert env.enable_file_logging is True
        assert env.log_max_file_bytes == 5242880
        assert env.log_max_file_count == 3

    def test_enable_mproc_logging(self, monkeypatch):
        """Test enabling multiprocess logging."""
        monkeypatch.setenv("ENABLE_MPROC_LOGGING", "true")
        monkeypatch.setenv("MPROC_LOG_QUEUE_SIZE", "500000")

        env = LoggingEnv()

        assert env.enable_mproc_logging is True
        assert env.mproc_log_queue_size == 500000

    def test_custom_logs_base_dir(self, monkeypatch):
        """Test setting custom logs directory."""
        monkeypatch.setenv("LOGS_BASE_DIR", "/var/log/myapp")

        env = LoggingEnv()

        assert env.logs_base_dir == "/var/log/myapp"


class TestServerSSLEnv:
    """Tests for ServerSSLEnv settings class."""

    def test_default_values(self):
        """Test ServerSSLEnv with default values."""
        env = ServerSSLEnv()

        assert env.is_enabled is False
        assert env.ca_file is None
        assert env.cert_file is None
        assert env.key_file is None
        assert env.password is None
        assert env.is_self_signed is True

    def test_is_self_signed_with_ca(self, monkeypatch):
        """Test is_self_signed is False when CA file is provided."""
        # Create temp files
        with tempfile.TemporaryDirectory() as tmpdir:
            ca_file = os.path.join(tmpdir, "ca.pem")
            cert_file = os.path.join(tmpdir, "cert.pem")
            key_file = os.path.join(tmpdir, "key.pem")

            # Create dummy files
            for f in [ca_file, cert_file, key_file]:
                with open(f, "w") as fh:
                    fh.write(
                        "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----"
                    )

            monkeypatch.setenv("SERVER_SSL_ENABLED", "true")
            monkeypatch.setenv("SERVER_SSL_CA_FILE", ca_file)
            monkeypatch.setenv("SERVER_SSL_CERT_FILE", cert_file)
            monkeypatch.setenv("SERVER_SSL_KEY_FILE", key_file)

            env = ServerSSLEnv()

            assert env.is_self_signed is False

    def test_validation_fails_without_cert_when_enabled(self, monkeypatch):
        """Test that validation fails when enabled but cert file missing."""
        monkeypatch.setenv("SERVER_SSL_ENABLED", "true")

        with pytest.raises(ValueError, match="SERVER_SSL_CERT_FILE"):
            ServerSSLEnv()

    def test_disabled_ssl_no_validation(self, monkeypatch):
        """Test that disabled SSL doesn't require cert files."""
        monkeypatch.setenv("SERVER_SSL_ENABLED", "false")

        env = ServerSSLEnv()

        assert env.is_enabled is False


class TestClientSSLEnv:
    """Tests for ClientSSLEnv settings class."""

    def test_default_values(self):
        """Test ClientSSLEnv with default values."""
        env = ClientSSLEnv()

        assert env.is_enabled is False
        assert env.ca_file is None
        assert env.cert_file is None
        assert env.key_file is None
        assert env.password is None
        assert env.is_self_signed is True

    def test_is_self_signed_with_ca(self, monkeypatch):
        """Test is_self_signed is False when CA file is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ca_file = os.path.join(tmpdir, "ca.pem")
            cert_file = os.path.join(tmpdir, "cert.pem")
            key_file = os.path.join(tmpdir, "key.pem")

            # Create dummy files
            for f in [ca_file, cert_file, key_file]:
                with open(f, "w") as fh:
                    fh.write(
                        "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----"
                    )

            monkeypatch.setenv("CLIENT_SSL_ENABLED", "true")
            monkeypatch.setenv("CLIENT_SSL_CA_FILE", ca_file)
            monkeypatch.setenv("CLIENT_SSL_CERT_FILE", cert_file)
            monkeypatch.setenv("CLIENT_SSL_KEY_FILE", key_file)

            env = ClientSSLEnv()

            assert env.is_self_signed is False

    def test_validation_fails_without_cert_when_enabled(self, monkeypatch):
        """Test that validation fails when enabled but cert file missing."""
        monkeypatch.setenv("CLIENT_SSL_ENABLED", "true")

        with pytest.raises(ValueError, match="CLIENT_SSL_CERT_FILE"):
            ClientSSLEnv()

    def test_disabled_ssl_no_validation(self, monkeypatch):
        """Test that disabled SSL doesn't require cert files."""
        monkeypatch.setenv("CLIENT_SSL_ENABLED", "false")

        env = ClientSSLEnv()

        assert env.is_enabled is False


class TestTelemetryEnv:
    """Tests for TelemetryEnv settings class."""

    VALID_RESOURCE_ATTRS = (
        "service.name=myapp,service.version=1.0.0,deployment.environment=prod"
    )

    def test_valid_settings(self, monkeypatch):
        """Should create TelemetryEnv with valid env vars."""
        from ayuna_core.settings import TelemetryEnv

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "Authorization=Bearer token")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", self.VALID_RESOURCE_ATTRS)

        env = TelemetryEnv()

        assert env.otel_exporter == "otlp"
        assert env.otel_exporter_headers == "Authorization=Bearer token"
        assert env.otel_exporter_endpoint == "http://collector:4317"
        assert env.otel_export_interval_millis == 5000
        assert env.otel_exporter_certificate is None
        assert env.otel_exporter_certchain is None
        assert env.otel_exporter_privkey is None

    def test_resource_attributes_parsed(self, monkeypatch):
        """Should parse OTEL_RESOURCE_ATTRIBUTES into a dict."""
        from ayuna_core.settings import TelemetryEnv

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "auth=token")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", self.VALID_RESOURCE_ATTRS)

        env = TelemetryEnv()
        attrs = env.resource_attributes

        assert attrs["service.name"] == "myapp"
        assert attrs["service.version"] == "1.0.0"
        assert attrs["deployment.environment"] == "prod"
        assert "service.instance.id" in attrs  # Auto-generated

    def test_custom_export_interval(self, monkeypatch):
        """Should accept custom export interval."""
        from ayuna_core.settings import TelemetryEnv

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "auth=token")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", self.VALID_RESOURCE_ATTRS)
        monkeypatch.setenv("OTEL_EXPORT_INTERVAL_MILLIS", "10000")

        env = TelemetryEnv()

        assert env.otel_export_interval_millis == 10000

    def test_mtls_certchain_without_privkey_fails(self, monkeypatch):
        """Should fail if certchain is set but privkey is not."""
        from ayuna_core.settings import TelemetryEnv

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "auth=token")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", self.VALID_RESOURCE_ATTRS)
        monkeypatch.setenv("OTEL_EXPORTER_CERTCHAIN", "/path/to/cert.pem")

        with pytest.raises(ValueError, match="otel_exporter_privkey"):
            TelemetryEnv()

    def test_mtls_privkey_without_certchain_fails(self, monkeypatch):
        """Should fail if privkey is set but certchain is not."""
        from ayuna_core.settings import TelemetryEnv

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "auth=token")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", self.VALID_RESOURCE_ATTRS)
        monkeypatch.setenv("OTEL_EXPORTER_PRIVKEY", "/path/to/key.pem")

        with pytest.raises(ValueError, match="otel_exporter_certchain"):
            TelemetryEnv()

    def test_invalid_resource_attributes_pattern_fails(self, monkeypatch):
        """Should fail with invalid resource attributes pattern."""
        from pydantic import ValidationError

        from ayuna_core.settings import TelemetryEnv

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "auth=token")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "invalid-format")

        with pytest.raises(ValidationError):
            TelemetryEnv()
