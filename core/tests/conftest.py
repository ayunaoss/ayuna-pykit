"""
conftest.py - Pytest configuration and fixtures for ayuna_core tests.

This module provides common fixtures and configuration for all test modules.
"""

import asyncio  # noqa: F401
import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
import pytest_asyncio  # noqa: F401

# Configure pytest-asyncio to use auto mode
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use uvloop for better async performance in tests."""
    import uvloop

    return uvloop.EventLoopPolicy()


@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="function")
def temp_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary file path (file not created)."""
    yield temp_dir / "test_file.txt"


@pytest.fixture(scope="function")
def sample_text_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary text file with sample content."""
    file_path = temp_dir / "sample.txt"
    file_path.write_text("Hello, World!\nThis is a test file.")
    yield file_path


@pytest.fixture(scope="function")
def sample_json_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary JSON file with sample content."""
    file_path = temp_dir / "sample.json"
    file_path.write_text('{"key": "value", "number": 42, "nested": {"a": 1}}')
    yield file_path


@pytest.fixture(scope="function")
def sample_yaml_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary YAML file with sample content."""
    file_path = temp_dir / "sample.yaml"
    file_path.write_text("key: value\nnumber: 42\nnested:\n  a: 1")
    yield file_path


@pytest.fixture(scope="function")
def sample_toml_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary TOML file with sample content."""
    file_path = temp_dir / "sample.toml"
    file_path.write_text('[section]\nkey = "value"\nnumber = 42')
    yield file_path


@pytest.fixture(scope="function")
def env_vars() -> Generator[dict, None, None]:
    """
    Fixture to set and cleanup environment variables.

    Usage:
        def test_something(env_vars):
            env_vars["MY_VAR"] = "value"
            # test code
    """
    original_env = os.environ.copy()

    class EnvVarManager(dict):
        def __setitem__(self, key, value):
            os.environ[key] = value
            super().__setitem__(key, value)

        def __delitem__(self, key):
            if key in os.environ:
                del os.environ[key]
            if key in self:
                super().__delitem__(key)

    manager = EnvVarManager()
    yield manager

    # Cleanup: restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(scope="function")
def sample_pem_cert_and_key(temp_dir: Path) -> Generator[tuple[Path, Path], None, None]:
    """Generate a sample self-signed certificate and key for testing."""
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    # Generate key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Generate certificate
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Test"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Test City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
            x509.NameAttribute(NameOID.COMMON_NAME, "test.example.com"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365)
        )
        .sign(key, hashes.SHA256())
    )

    # Write files
    cert_path = temp_dir / "test_cert.pem"
    key_path = temp_dir / "test_key.pem"

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )

    yield cert_path, key_path


@pytest.fixture(scope="session")
def ayuna_app_initialized():
    """Initialize Ayuna app configuration for tests that need it."""
    from ayuna_core.basefuncs import ayuna_app_init

    ayuna_app_init()
    return True
