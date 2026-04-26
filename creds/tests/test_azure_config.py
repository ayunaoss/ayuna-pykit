"""Tests for Azure credential configuration models."""

from pydantic import SecretStr

from ayuna_creds.azure_config import (
    CredConfigAPIKey,
    CredConfigAuto,
    CredConfigManagedIdentity,
    CredConfigServicePrincipalCertificate,
    CredConfigServicePrincipalSecret,
    CredConfigWorkloadIdentity,
)


class TestCredConfigAuto:
    """Tests for automatic Azure credential configuration."""

    def test_default_values(self):
        """Test that auto config has correct default values."""
        config = CredConfigAuto()
        assert config.typid == "auto"


class TestCredConfigAPIKey:
    """Tests for Azure API key credential configuration."""

    def test_valid_api_key(self):
        """Test API key config with valid key."""
        config = CredConfigAPIKey(api_key=SecretStr("my-secret-api-key"))
        assert config.typid == "api_key"
        assert config.api_key.get_secret_value() == "my-secret-api-key"

    def test_empty_api_key_is_allowed(self):
        """Test that empty API key is technically allowed (Pydantic SecretStr behavior)."""
        # Note: Pydantic SecretStr doesn't validate against empty strings
        config = CredConfigAPIKey(api_key=SecretStr(""))
        assert config.api_key.get_secret_value() == ""


class TestCredConfigWorkloadIdentity:
    """Tests for Azure Workload Identity configuration."""

    def test_valid_workload_identity(self):
        """Test workload identity config with required fields."""
        config = CredConfigWorkloadIdentity(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            federated_token_file="/path/to/token",
        )
        assert config.typid == "workload_identity"
        assert config.tenant_id == "12345678-1234-1234-1234-123456789012"
        assert config.client_id == "87654321-4321-4321-4321-210987654321"
        assert config.federated_token_file == "/path/to/token"
        assert config.authority_host == "https://login.microsoftonline.com"

    def test_workload_identity_with_custom_authority(self):
        """Test workload identity with custom authority host."""
        config = CredConfigWorkloadIdentity(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            federated_token_file="/path/to/token",
            authority_host="https://login.chinacloudapi.cn",
        )
        assert config.authority_host == "https://login.chinacloudapi.cn"


class TestCredConfigManagedIdentity:
    """Tests for Azure Managed Identity configuration."""

    def test_system_assigned_managed_identity(self):
        """Test system-assigned managed identity config."""
        config = CredConfigManagedIdentity()
        assert config.typid == "managed_identity"
        assert config.client_id is None

    def test_user_assigned_managed_identity(self):
        """Test user-assigned managed identity config."""
        config = CredConfigManagedIdentity(
            client_id="87654321-4321-4321-4321-210987654321"
        )
        assert config.client_id == "87654321-4321-4321-4321-210987654321"


class TestCredConfigServicePrincipalSecret:
    """Tests for Azure Service Principal with Client Secret configuration."""

    def test_valid_service_principal_secret(self):
        """Test service principal secret config."""
        config = CredConfigServicePrincipalSecret(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            client_secret=SecretStr("my-client-secret"),
        )
        assert config.typid == "service_principal_secret"
        assert config.tenant_id == "12345678-1234-1234-1234-123456789012"
        assert config.client_id == "87654321-4321-4321-4321-210987654321"
        assert config.client_secret.get_secret_value() == "my-client-secret"
        assert config.authority is None

    def test_service_principal_secret_with_authority(self):
        """Test service principal with custom authority."""
        config = CredConfigServicePrincipalSecret(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            client_secret=SecretStr("my-client-secret"),
            authority="https://login.chinacloudapi.cn",
        )
        assert config.authority == "https://login.chinacloudapi.cn"


class TestCredConfigServicePrincipalCertificate:
    """Tests for Azure Service Principal with Certificate configuration."""

    def test_valid_service_principal_certificate(self):
        """Test service principal certificate config."""
        config = CredConfigServicePrincipalCertificate(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            certificate_path="/path/to/cert.pfx",
        )
        assert config.typid == "service_principal_certificate"
        assert config.certificate_path == "/path/to/cert.pfx"
        assert config.certificate_password is None
        assert config.authority is None

    def test_service_principal_certificate_with_password(self):
        """Test service principal certificate with password."""
        config = CredConfigServicePrincipalCertificate(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            certificate_path="/path/to/cert.pfx",
            certificate_password=SecretStr("cert-password"),
        )
        assert config.certificate_password.get_secret_value() == "cert-password"

    def test_service_principal_certificate_with_authority(self):
        """Test service principal certificate with custom authority."""
        config = CredConfigServicePrincipalCertificate(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            certificate_path="/path/to/cert.pfx",
            authority="https://login.microsoftonline.us",
        )
        assert config.authority == "https://login.microsoftonline.us"
