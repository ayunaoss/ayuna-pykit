"""Tests for Azure credential provider."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ayuna_creds.azure_config import (
    CredConfigAPIKey,
    CredConfigAuto,
    CredConfigManagedIdentity,
    CredConfigServicePrincipalCertificate,
    CredConfigServicePrincipalSecret,
    CredConfigWorkloadIdentity,
)
from ayuna_creds.azure_provider import CredProvider


class TestCredProviderAPIKey:
    """Tests for Azure API key credential resolution."""

    def test_resolve_api_key(self):
        """Test that API key resolution creates AzureKeyCredential."""
        from azure.core.credentials import AzureKeyCredential

        config = CredConfigAPIKey(api_key=SecretStr("my-api-key"))
        provider = CredProvider(config=config)

        credential = provider.resolve_credential(async_mode=False)

        # Verify it's an AzureKeyCredential with correct key
        assert isinstance(credential, AzureKeyCredential)
        assert credential.key == "my-api-key"


class TestCredProviderAuto:
    """Tests for automatic Azure credential resolution."""

    def test_resolve_auto_sync(self):
        """Test auto resolution returns sync DefaultAzureCredential."""
        config = CredConfigAuto()
        provider = CredProvider(config=config)

        # Patch the imported alias in the provider module
        with patch(
            "ayuna_creds.azure_provider.SyncDefaultAzureCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=False)

            mock_credential_class.assert_called_once()
            assert credential == mock_credential

    def test_resolve_auto_async(self):
        """Test auto resolution returns async DefaultAzureCredential."""
        config = CredConfigAuto()
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.AsyncDefaultAzureCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=True)

            mock_credential_class.assert_called_once()
            assert credential == mock_credential


class TestCredProviderManagedIdentity:
    """Tests for Azure Managed Identity credential resolution."""

    def test_resolve_system_assigned_managed_identity_sync(self):
        """Test system-assigned managed identity resolution (sync)."""
        config = CredConfigManagedIdentity()
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.SyncManagedIdentityCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=False)

            mock_credential_class.assert_called_once_with()
            assert credential == mock_credential

    def test_resolve_user_assigned_managed_identity_sync(self):
        """Test user-assigned managed identity resolution (sync)."""
        config = CredConfigManagedIdentity(client_id="my-client-id")
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.SyncManagedIdentityCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=False)

            mock_credential_class.assert_called_once_with(client_id="my-client-id")
            assert credential == mock_credential

    def test_resolve_system_assigned_managed_identity_async(self):
        """Test system-assigned managed identity resolution (async)."""
        config = CredConfigManagedIdentity()
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.AsyncManagedIdentityCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=True)

            mock_credential_class.assert_called_once_with()
            assert credential == mock_credential

    def test_resolve_user_assigned_managed_identity_async(self):
        """Test user-assigned managed identity resolution (async)."""
        config = CredConfigManagedIdentity(client_id="my-client-id")
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.AsyncManagedIdentityCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=True)

            mock_credential_class.assert_called_once_with(client_id="my-client-id")
            assert credential == mock_credential


class TestCredProviderWorkloadIdentity:
    """Tests for Azure Workload Identity credential resolution."""

    def test_resolve_workload_identity_sync(self):
        """Test workload identity resolution (sync)."""
        config = CredConfigWorkloadIdentity(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            federated_token_file="/path/to/token",
        )
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.SyncWorkloadIdentityCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=False)

            mock_credential_class.assert_called_once_with(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                token_file_path="/path/to/token",
            )
            assert credential == mock_credential

    def test_resolve_workload_identity_async(self):
        """Test workload identity resolution (async)."""
        config = CredConfigWorkloadIdentity(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            federated_token_file="/path/to/token",
        )
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.AsyncWorkloadIdentityCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=True)

            mock_credential_class.assert_called_once_with(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                token_file_path="/path/to/token",
            )
            assert credential == mock_credential


class TestCredProviderServicePrincipalSecret:
    """Tests for Azure Service Principal with Client Secret."""

    def test_resolve_service_principal_secret_sync(self):
        """Test service principal secret resolution (sync)."""
        config = CredConfigServicePrincipalSecret(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            client_secret=SecretStr("my-client-secret"),
        )
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.SyncClientSecretCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=False)

            mock_credential_class.assert_called_once_with(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                client_secret="my-client-secret",
            )
            assert credential == mock_credential

    def test_resolve_service_principal_secret_async(self):
        """Test service principal secret resolution (async)."""
        config = CredConfigServicePrincipalSecret(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            client_secret=SecretStr("my-client-secret"),
        )
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.AsyncClientSecretCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=True)

            mock_credential_class.assert_called_once_with(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                client_secret="my-client-secret",
            )
            assert credential == mock_credential

    def test_resolve_service_principal_secret_with_authority(self):
        """Test service principal secret with custom authority."""
        config = CredConfigServicePrincipalSecret(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            client_secret=SecretStr("my-client-secret"),
            authority="https://login.chinacloudapi.cn",
        )
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.SyncClientSecretCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            provider.resolve_credential(async_mode=False)

            mock_credential_class.assert_called_once_with(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                client_secret="my-client-secret",
                authority="https://login.chinacloudapi.cn",
            )


class TestCredProviderServicePrincipalCertificate:
    """Tests for Azure Service Principal with Certificate."""

    def test_resolve_service_principal_certificate_sync(self):
        """Test service principal certificate resolution (sync)."""
        config = CredConfigServicePrincipalCertificate(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            certificate_path="/path/to/cert.pfx",
        )
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.SyncCertificateCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=False)

            mock_credential_class.assert_called_once_with(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                certificate_path="/path/to/cert.pfx",
            )
            assert credential == mock_credential

    def test_resolve_service_principal_certificate_with_password_sync(self):
        """Test service principal certificate with password (sync)."""
        config = CredConfigServicePrincipalCertificate(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            certificate_path="/path/to/cert.pfx",
            certificate_password=SecretStr("cert-password"),
        )
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.SyncCertificateCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            provider.resolve_credential(async_mode=False)

            mock_credential_class.assert_called_once_with(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                certificate_path="/path/to/cert.pfx",
                password="cert-password",
            )

    def test_resolve_service_principal_certificate_async(self):
        """Test service principal certificate resolution (async)."""
        config = CredConfigServicePrincipalCertificate(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            certificate_path="/path/to/cert.pfx",
        )
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.AsyncCertificateCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.resolve_credential(async_mode=True)

            mock_credential_class.assert_called_once_with(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                certificate_path="/path/to/cert.pfx",
            )
            assert credential == mock_credential

    def test_resolve_service_principal_certificate_with_authority(self):
        """Test service principal certificate with custom authority."""
        config = CredConfigServicePrincipalCertificate(
            tenant_id="12345678-1234-1234-1234-123456789012",
            client_id="87654321-4321-4321-4321-210987654321",
            certificate_path="/path/to/cert.pfx",
            authority="https://login.microsoftonline.us",
        )
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.azure_provider.SyncCertificateCredential"
        ) as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            provider.resolve_credential(async_mode=False)

            mock_credential_class.assert_called_once_with(
                tenant_id="12345678-1234-1234-1234-123456789012",
                client_id="87654321-4321-4321-4321-210987654321",
                certificate_path="/path/to/cert.pfx",
                authority="https://login.microsoftonline.us",
            )


class TestCredProviderUnsupportedMethod:
    """Tests for unsupported Azure credential methods."""

    def test_unsupported_method_async(self):
        """Test that API key is not supported in async mode."""
        config = CredConfigAPIKey(api_key=SecretStr("my-api-key"))
        provider = CredProvider(config=config)

        with pytest.raises(ValueError) as exc_info:
            provider.resolve_credential(async_mode=True)

        assert "api_key" in str(exc_info.value)

    def test_unknown_method_raises_error(self):
        """Test that unknown method raises ValueError."""
        from unittest.mock import MagicMock

        config = MagicMock()
        config.typid = "unknown_method"
        provider = CredProvider(config=config)

        with pytest.raises(ValueError) as exc_info:
            provider.resolve_credential(async_mode=False)

        assert "unknown_method" in str(exc_info.value)
