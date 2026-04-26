"""
settings.py - Configuration settings models for the Ayuna framework.

This module provides Pydantic-based settings classes for configuring various
aspects of the Ayuna framework through environment variables:

- LoggingEnv: Logging configuration (log levels, file rotation, multiprocess logging)
- TelemetryEnv: OpenTelemetry exporter configuration
- ServerSSLEnv: Server-side SSL/TLS certificate configuration
- ClientSSLEnv: Client-side SSL/TLS certificate configuration

Each settings class reads from environment variables and provides validation
and computed properties. Global singleton instances are accessed via factory
functions (logging_env(), telemetry_env(), etc.).
"""

import os
import ssl
from typing import Annotated, Dict, Literal

from pydantic import (
    AliasChoices,
    Field,
    SecretStr,
    StringConstraints,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from .basefuncs import id_by_sysinfo
from .basetypes import LogLevelName
from .constants import DEFAULT_LOG_FORMAT, SERVICE_INST_ID_KEY
from .fileops import is_file_readable

# =============================================================================
# Type Definitions
# =============================================================================

# Constrained string type for OpenTelemetry resource attributes
# Must follow the format: "service.name=value,service.version=value,deployment.environment=value,..."
OTelResourceAttrsStr = Annotated[
    str,
    StringConstraints(
        pattern=r"^service.name=[a-zA-Z0-9_.-]+,service.version=[a-zA-Z0-9_.-]+,deployment.environment=[a-zA-Z0-9_.-]+(,[a-zA-Z0-9_.]+=[a-zA-Z0-9_.,%&@\'\"\[\]-]+)*$"
    ),
]

# =============================================================================
# Settings Classes
# =============================================================================


class LoggingEnv(BaseSettings):
    """
    Logging configuration settings loaded from environment variables.

    Controls all aspects of logging behavior including log levels,
    output destinations, file rotation, and multiprocess logging support.

    Environment Variables
    ---------------------
    DEBUG : bool
        Enable debug mode (default: False)
    LOGS_BASE_DIR : str
        Base directory for log files (default: "/tmp/logs")
    LOG_LEVEL : str
        Logging level: CRITICAL, ERROR, WARNING, INFO, DEBUG, TRACE (default: "INFO")
    LOG_FORMAT : str
        Log message format string (default: see DEFAULT_LOG_FORMAT)
    ENABLE_FILE_LOGGING : bool
        Enable logging to rotating files (default: False)
    LOG_MAX_FILE_BYTES : int
        Maximum size per log file before rotation (default: 10MB)
    LOG_MAX_FILE_COUNT : int
        Number of backup log files to keep (default: 5)
    ENABLE_MPROC_LOGGING : bool
        Enable multiprocess-safe logging via queue (default: False)
    MPROC_LOG_QUEUE_SIZE : int
        Maximum size of multiprocess log queue (default: 1,000,000)

    Notes
    -----
    Setting DEBUG=true automatically sets LOG_LEVEL to DEBUG.
    Setting LOG_LEVEL=DEBUG automatically sets debug=True.
    """

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file_encoding="utf-8",
        allow_inf_nan=False,
        populate_by_name=True,
        loc_by_alias=True,
    )

    debug: bool = Field(validation_alias=AliasChoices("DEBUG"), default=False)
    logs_base_dir: str = Field(
        validation_alias=AliasChoices("LOGS_BASE_DIR"), default="/tmp/logs"
    )
    log_level: LogLevelName = Field(
        validation_alias=AliasChoices("LOG_LEVEL"), default=LogLevelName("INFO")
    )
    log_format: str = Field(
        validation_alias=AliasChoices("LOG_FORMAT"), default=DEFAULT_LOG_FORMAT
    )
    enable_file_logging: bool = Field(
        validation_alias=AliasChoices("ENABLE_FILE_LOGGING"), default=False
    )
    log_max_file_bytes: int = Field(
        validation_alias=AliasChoices("LOG_MAX_FILE_BYTES"), default=10 * 1024 * 1024
    )
    log_max_file_count: int = Field(
        validation_alias=AliasChoices("LOG_MAX_FILE_COUNT"), default=5, ge=1
    )
    enable_mproc_logging: bool = Field(
        validation_alias=AliasChoices("ENABLE_MPROC_LOGGING"), default=False
    )
    mproc_log_queue_size: int = Field(
        validation_alias=AliasChoices("MPROC_LOG_QUEUE_SIZE"),
        default=1_000_000,
        ge=1000,
    )

    @model_validator(mode="after")
    def sync_log_settings(self):
        """Synchronize debug flag and log level for consistency."""
        if self.log_level == LogLevelName.DEBUG:
            self.debug = True
        elif self.debug:
            self.log_level = LogLevelName.DEBUG

        return self


class TelemetryEnv(BaseSettings):
    """
    OpenTelemetry exporter configuration settings.

    Configures the OTLP exporter for sending traces and metrics to
    an OpenTelemetry collector or compatible backend.

    Environment Variables
    ---------------------
    OTEL_EXPORTER_OTLP_HEADERS : str
        Headers to include in OTLP requests (e.g., authentication)
    OTEL_EXPORTER_OTLP_ENDPOINT : str
        URL of the OTLP collector endpoint
    OTEL_RESOURCE_ATTRIBUTES : str
        Comma-separated key=value pairs for resource attributes
        Must include: service.name, service.version, deployment.environment
    OTEL_EXPORT_INTERVAL_MILLIS : int
        Metric export interval in milliseconds (default: 5000, min: 1000)
    OTEL_EXPORTER_OTLP_CERTIFICATE : str
        Path to CA certificate for TLS verification (optional)
    OTEL_EXPORTER_CERTCHAIN : str
        Path to client certificate chain for mTLS (optional)
    OTEL_EXPORTER_PRIVKEY : str
        Path to client private key for mTLS (optional)

    Notes
    -----
    If using mTLS, both certchain and privkey must be provided together.
    A service.instance.id is automatically generated if not provided.
    """

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file_encoding="utf-8",
        allow_inf_nan=False,
        populate_by_name=True,
        loc_by_alias=True,
    )

    otel_exporter: Literal["otlp"] = "otlp"
    otel_exporter_headers: str = Field(
        validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_HEADERS")
    )
    otel_exporter_endpoint: str = Field(
        validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_ENDPOINT")
    )
    otel_resource_attributes: OTelResourceAttrsStr = Field(
        validation_alias=AliasChoices("OTEL_RESOURCE_ATTRIBUTES")
    )
    otel_export_interval_millis: int = Field(
        validation_alias=AliasChoices("OTEL_EXPORT_INTERVAL_MILLIS"),
        default=5000,
        ge=1000,
    )
    otel_exporter_certificate: str | None = Field(
        validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_CERTIFICATE"), default=None
    )
    otel_exporter_certchain: str | None = Field(
        validation_alias=AliasChoices("OTEL_EXPORTER_CERTCHAIN"), default=None
    )
    otel_exporter_privkey: str | None = Field(
        validation_alias=AliasChoices("OTEL_EXPORTER_PRIVKEY"), default=None
    )

    @computed_field
    @property
    def resource_attributes(self) -> Dict:
        """
        Parse resource attributes string into a dictionary.

        Automatically adds a service.instance.id if not provided,
        using a hash of the system's IP addresses and OS info.

        Returns
        -------
        Dict
            Dictionary of resource attribute key-value pairs.
        """
        res_attrs: Dict[str, str] = {}

        resource_pairs = self.otel_resource_attributes.split(",")

        for resource_pair in resource_pairs:
            key, value = resource_pair.split("=")
            res_attrs[key] = value

        if SERVICE_INST_ID_KEY not in res_attrs:
            res_attrs[SERVICE_INST_ID_KEY] = id_by_sysinfo()

        return res_attrs

    @model_validator(mode="after")
    def check_certs(self):
        """Validate that mTLS certificate and key are provided together."""
        if (
            self.otel_exporter_certchain is not None
            and self.otel_exporter_privkey is None
        ):
            raise ValueError(
                "If 'otel_exporter_certchain' is set, 'otel_exporter_privkey' must be set as well"
            )

        if (
            self.otel_exporter_certchain is None
            and self.otel_exporter_privkey is not None
        ):
            raise ValueError(
                "If 'otel_exporter_privkey' is set, 'otel_exporter_certchain' must be set as well"
            )

        return self


class ServerSSLEnv(BaseSettings):
    """
    Server-side SSL/TLS configuration settings.

    Configures TLS for server applications, including certificate,
    private key, and CA certificate for client verification.

    Environment Variables
    ---------------------
    SERVER_SSL_ENABLED : bool
        Enable SSL/TLS for the server (default: False)
    SERVER_SSL_CA_FILE : str
        Path to CA certificate file for client verification (optional)
    SERVER_SSL_CERT_FILE : str
        Path to server certificate file (required if SSL enabled)
    SERVER_SSL_KEY_FILE : str
        Path to server private key file (required if SSL enabled)
    SERVER_SSL_PASSWORD : str
        Password for encrypted private key (optional)

    Attributes
    ----------
    is_self_signed : bool
        True if no CA file is provided (self-signed certificate mode)
    """

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file_encoding="utf-8",
        allow_inf_nan=False,
        populate_by_name=True,
        loc_by_alias=True,
    )

    is_enabled: bool = Field(
        validation_alias=AliasChoices("SERVER_SSL_ENABLED"), default=False
    )
    ca_file: str | None = Field(
        validation_alias=AliasChoices("SERVER_SSL_CA_FILE"), default=None
    )
    cert_file: str | None = Field(
        validation_alias=AliasChoices("SERVER_SSL_CERT_FILE"), default=None
    )
    key_file: str | None = Field(
        validation_alias=AliasChoices("SERVER_SSL_KEY_FILE"), default=None
    )
    password: SecretStr | None = Field(
        validation_alias=AliasChoices("SERVER_SSL_PASSWORD"), default=None
    )

    @computed_field
    @property
    def is_self_signed(self) -> bool:
        """Check if using self-signed certificates (no CA file provided)."""
        return not self.ca_file

    @model_validator(mode="after")
    def check_certs(self):
        """Validate that all required certificate files exist and are readable."""
        if self.is_enabled:
            if not self.cert_file or not is_file_readable(self.cert_file):
                raise ValueError(
                    "SERVER_SSL_CERT_FILE environment variable is not set or, the file is not readable"
                )

            if not self.key_file or not is_file_readable(self.key_file):
                raise ValueError(
                    "SERVER_SSL_KEY_FILE environment variable is not set or, the file is not readable"
                )

            if not self.ca_file or not is_file_readable(self.ca_file):
                raise ValueError(
                    "SERVER_SSL_CA_FILE environment variable is not set or, the file is not readable"
                )

        return self


class ClientSSLEnv(BaseSettings):
    """
    Client-side SSL/TLS configuration settings.

    Configures TLS for client applications making outbound connections,
    including client certificate for mTLS and CA certificate for server verification.

    Environment Variables
    ---------------------
    CLIENT_SSL_ENABLED : bool
        Enable SSL/TLS for client connections (default: False)
    CLIENT_SSL_CA_FILE : str
        Path to CA certificate file for server verification (optional)
    CLIENT_SSL_CERT_FILE : str
        Path to client certificate file for mTLS (required if SSL enabled)
    CLIENT_SSL_KEY_FILE : str
        Path to client private key file (required if SSL enabled)
    CLIENT_SSL_PASSWORD : str
        Password for encrypted private key (optional)

    Attributes
    ----------
    is_self_signed : bool
        True if no CA file is provided (skip server verification)
    """

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file_encoding="utf-8",
        allow_inf_nan=False,
        populate_by_name=True,
        loc_by_alias=True,
    )

    is_enabled: bool = Field(
        validation_alias=AliasChoices("CLIENT_SSL_ENABLED"), default=False
    )
    ca_file: str | None = Field(
        validation_alias=AliasChoices("CLIENT_SSL_CA_FILE"), default=None
    )
    cert_file: str | None = Field(
        validation_alias=AliasChoices("CLIENT_SSL_CERT_FILE"), default=None
    )
    key_file: str | None = Field(
        validation_alias=AliasChoices("CLIENT_SSL_KEY_FILE"), default=None
    )
    password: SecretStr | None = Field(
        validation_alias=AliasChoices("CLIENT_SSL_PASSWORD"), default=None
    )

    @computed_field
    @property
    def is_self_signed(self) -> bool:
        """Check if using self-signed mode (no CA file for verification)."""
        return not self.ca_file

    @model_validator(mode="after")
    def check_certs(self):
        """Validate that all required certificate files exist and are readable."""
        if self.is_enabled:
            if not self.cert_file or not is_file_readable(self.cert_file):
                raise ValueError(
                    "CLIENT_SSL_CERT_FILE environment variable is not set or, the file is not readable"
                )

            if not self.key_file or not is_file_readable(self.key_file):
                raise ValueError(
                    "CLIENT_SSL_KEY_FILE environment variable is not set or, the file is not readable"
                )

            if not self.ca_file or not is_file_readable(self.ca_file):
                raise ValueError(
                    "CLIENT_SSL_CA_FILE environment variable is not set or, the file is not readable"
                )

        return self


# =============================================================================
# Global Settings Singletons
# =============================================================================

# Lazily-initialized global instances of settings classes
__logging_env: LoggingEnv | None = None
__telemetry_env: TelemetryEnv | None = None
__server_ssl_env: ServerSSLEnv | None = None
__client_ssl_env: ClientSSLEnv | None = None


def logging_env():
    """
    Get the global LoggingEnv singleton instance.

    Returns
    -------
    LoggingEnv
        Singleton logging configuration loaded from environment variables.
    """
    global __logging_env

    if __logging_env is None:
        __logging_env = LoggingEnv()

    return __logging_env


def telemetry_env():
    """
    Get the global TelemetryEnv singleton instance.

    Returns
    -------
    TelemetryEnv
        Singleton telemetry configuration loaded from environment variables.
    """
    global __telemetry_env

    if __telemetry_env is None:
        __telemetry_env = TelemetryEnv()  # type: ignore[call-arg]

    return __telemetry_env


def server_ssl_env():
    """
    Get the global ServerSSLEnv singleton instance.

    Returns
    -------
    ServerSSLEnv
        Singleton server SSL configuration loaded from environment variables.
    """
    global __server_ssl_env

    if __server_ssl_env is None:
        __server_ssl_env = ServerSSLEnv()

    return __server_ssl_env


def client_ssl_env():
    """
    Get the global ClientSSLEnv singleton instance.

    Returns
    -------
    ClientSSLEnv
        Singleton client SSL configuration loaded from environment variables.
    """
    global __client_ssl_env

    if __client_ssl_env is None:
        __client_ssl_env = ClientSSLEnv()

    return __client_ssl_env


# =============================================================================
# SSL Context Factory Functions
# =============================================================================


def create_context(
    certfile: str | os.PathLike[str],
    keyfile: str | os.PathLike[str] | None,
    password: str | None,
    ssl_version: int,
    cert_reqs: int,
    ca_certs: str | os.PathLike[str] | None,
    ciphers: str | None,
) -> ssl.SSLContext:
    """
    Create a customized SSL context with the specified parameters.

    Low-level function for creating SSL contexts with fine-grained control
    over all SSL options. For most use cases, prefer server_context() or
    client_context() which provide sensible defaults.

    Parameters
    ----------
    certfile : str | os.PathLike[str]
        Path to the certificate file.
    keyfile : str | os.PathLike[str] | None
        Path to the private key file.
    password : str | None
        Password for encrypted private key.
    ssl_version : int
        SSL protocol version constant (e.g., ssl.PROTOCOL_TLS_SERVER).
    cert_reqs : int
        Certificate verification mode (e.g., ssl.CERT_REQUIRED).
    ca_certs : str | os.PathLike[str] | None
        Path to CA certificates for verification.
    ciphers : str | None
        Cipher suite specification string.

    Returns
    -------
    ssl.SSLContext
        Configured SSL context.
    """
    ctx = ssl.SSLContext(ssl_version)
    get_password = (lambda: password) if password else None

    ctx.load_cert_chain(certfile, keyfile, get_password)
    ctx.verify_mode = ssl.VerifyMode(cert_reqs)

    if ca_certs:
        ctx.load_verify_locations(ca_certs)

    if ciphers:
        ctx.set_ciphers(ciphers)

    return ctx


def server_context(settings: ServerSSLEnv | None = None):
    """
    Create an SSL context configured for server-side TLS.

    Creates an SSL context suitable for accepting TLS connections,
    configured from ServerSSLEnv settings. The context loads the
    server certificate and optionally configures client verification.

    Parameters
    ----------
    settings : ServerSSLEnv | None, optional
        SSL settings to use. If None, uses the global server_ssl_env().

    Returns
    -------
    ssl.SSLContext
        Configured server SSL context.

    Notes
    -----
    - Uses TLS 1.2+ with PROTOCOL_TLS_SERVER
    - Loads default CA certs for client authentication
    - If self-signed, uses CERT_OPTIONAL; otherwise CERT_REQUIRED
    """
    if not settings:
        settings = server_ssl_env()

    if not settings.cert_file:
        raise ValueError("Server SSL settings require a certificate file")

    verify_mode = ssl.CERT_OPTIONAL if settings.is_self_signed else ssl.CERT_REQUIRED
    get_password = settings.password.get_secret_value() if settings.password else None

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)  # NOSONAR
    ctx.load_default_certs(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(settings.cert_file, settings.key_file, get_password)

    ctx.verify_mode = ssl.VerifyMode(verify_mode)

    if not settings.is_self_signed:
        ctx.load_verify_locations(settings.ca_file)

    return ctx


def client_context(settings: ClientSSLEnv | None = None):
    """
    Create an SSL context configured for client-side TLS.

    Creates an SSL context suitable for making outbound TLS connections,
    configured from ClientSSLEnv settings. The context loads the client
    certificate for mTLS and optionally configures server verification.

    Parameters
    ----------
    settings : ClientSSLEnv | None, optional
        SSL settings to use. If None, uses the global client_ssl_env().

    Returns
    -------
    ssl.SSLContext
        Configured client SSL context.

    Notes
    -----
    - Uses TLS 1.2+ with PROTOCOL_TLS_CLIENT
    - Loads default CA certs for server authentication
    - If self-signed, uses CERT_OPTIONAL; otherwise CERT_REQUIRED
    """
    if not settings:
        settings = client_ssl_env()

    if not settings.cert_file:
        raise ValueError("Client SSL settings require a certificate file")

    verify_mode = ssl.CERT_OPTIONAL if settings.is_self_signed else ssl.CERT_REQUIRED
    get_password = settings.password.get_secret_value() if settings.password else None

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # NOSONAR
    ctx.load_default_certs(ssl.Purpose.SERVER_AUTH)
    ctx.load_cert_chain(settings.cert_file, settings.key_file, get_password)

    ctx.verify_mode = ssl.VerifyMode(verify_mode)

    if not settings.is_self_signed:
        ctx.load_verify_locations(settings.ca_file)

    return ctx
