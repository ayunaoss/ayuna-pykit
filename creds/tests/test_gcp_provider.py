"""Tests for GCP credential provider."""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ayuna_creds.gcp_config import (
    CredConfigAuto,
    CredConfigServiceAccount,
    CredConfigWorkloadIdentity,
)
from ayuna_creds.gcp_provider import CredProvider


class TestCredProviderAuto:
    """Tests for automatic GCP credential resolution."""

    def test_resolve_auto_creates_credentials(self):
        """Test that auto resolution creates default credentials."""
        config = CredConfigAuto()
        provider = CredProvider(config=config)

        with patch("ayuna_creds.gcp_provider.default") as mock_default:
            # Create a mock that passes the isinstance check
            from google.auth.credentials import Credentials

            mock_credentials = MagicMock(spec=Credentials)
            mock_project = "my-project"
            mock_default.return_value = (mock_credentials, mock_project)

            credentials = provider.resolve_credentials()

            mock_default.assert_called_once()
            assert credentials == mock_credentials

    def test_resolve_auto_validates_credentials_type(self):
        """Test that auto resolution raises TypeError for invalid credentials type."""
        config = CredConfigAuto()
        provider = CredProvider(config=config)

        with patch("ayuna_creds.gcp_provider.default") as mock_default:
            # Return something that's not a Credentials instance
            mock_default.return_value = ("not-credentials", "project")

            with pytest.raises(TypeError) as exc_info:
                provider.resolve_credentials()

            assert "Failed to obtain default credentials" in str(exc_info.value)


class TestCredProviderServiceAccount:
    """Tests for GCP Service Account credential resolution."""

    def test_resolve_service_account(self):
        """Test service account resolution creates credentials from file."""
        config = CredConfigServiceAccount(key_file_path="/path/to/key.json")
        provider = CredProvider(config=config)

        key_data = {
            "type": "service_account",
            "project_id": "my-project",
            "private_key_id": "1234567890abcdef",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
            "client_email": "service@my-project.iam.gserviceaccount.com",
            "client_id": "123456789",
        }

        with patch(
            "ayuna_creds.gcp_provider.open", mock_open(read_data=json.dumps(key_data))
        ):
            with patch(
                "ayuna_creds.gcp_provider.service_account.Credentials.from_service_account_info"
            ) as mock_from_info:
                mock_credentials = MagicMock()
                mock_from_info.return_value = mock_credentials

                credentials = provider.resolve_credentials()

                mock_from_info.assert_called_once()
                call_args = mock_from_info.call_args
                assert call_args[0][0] == key_data
                # Check default scopes were added
                assert "scopes" in call_args[1]
                assert call_args[1]["scopes"] == [
                    "https://www.googleapis.com/auth/cloud-platform"
                ]
                assert credentials == mock_credentials

    def test_resolve_service_account_with_custom_scopes(self):
        """Test service account resolution with custom scopes."""
        config = CredConfigServiceAccount(
            key_file_path="/path/to/key.json",
            scopes=["https://www.googleapis.com/auth/bigquery"],
        )
        provider = CredProvider(config=config)

        key_data = {
            "type": "service_account",
            "project_id": "my-project",
            "client_email": "service@my-project.iam.gserviceaccount.com",
        }

        with patch(
            "ayuna_creds.gcp_provider.open", mock_open(read_data=json.dumps(key_data))
        ):
            with patch(
                "ayuna_creds.gcp_provider.service_account.Credentials.from_service_account_info"
            ) as mock_from_info:
                mock_credentials = MagicMock()
                mock_from_info.return_value = mock_credentials

                provider.resolve_credentials()

                call_args = mock_from_info.call_args
                assert call_args[1]["scopes"] == [
                    "https://www.googleapis.com/auth/bigquery"
                ]


class TestCredProviderWorkloadIdentity:
    """Tests for GCP Workload Identity Federation credential resolution."""

    def test_resolve_workload_identity(self):
        """Test workload identity resolution."""
        config = CredConfigWorkloadIdentity(
            file_path="/path/to/workload-identity.json",
            account_id="my-service@my-project.iam.gserviceaccount.com",
        )
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.gcp_provider.identity_pool.Credentials.from_file"
        ) as mock_from_file:
            mock_credentials = MagicMock()
            mock_from_file.return_value = mock_credentials

            with patch(
                "ayuna_creds.gcp_provider.google.auth.transport.requests.Request"
            ) as mock_request_class:
                mock_request = MagicMock()
                mock_request_class.return_value = mock_request

                credentials = provider.resolve_credentials()

                mock_from_file.assert_called_once_with(
                    "/path/to/workload-identity.json"
                )
                mock_credentials.refresh.assert_called_once_with(mock_request)
                assert credentials == mock_credentials


class TestCredProviderImpersonation:
    """Tests for GCP credential impersonation."""

    def test_resolve_impersonated_credentials(self):
        """Test impersonated credentials creation."""
        config = CredConfigAuto()
        provider = CredProvider(config=config)

        mock_source_credentials = MagicMock()

        with patch(
            "ayuna_creds.gcp_provider.ImpersonatedCredentials"
        ) as mock_impersonated_class:
            mock_impersonated = MagicMock()
            mock_impersonated_class.return_value = mock_impersonated

            credentials = provider.resolve_impersonated_credentials(
                source_credentials=mock_source_credentials,
                target_principal="target@my-project.iam.gserviceaccount.com",
                target_scopes=["https://www.googleapis.com/auth/bigquery"],
                lifetime=3600,
            )

            mock_impersonated_class.assert_called_once_with(
                source_credentials=mock_source_credentials,
                target_principal="target@my-project.iam.gserviceaccount.com",
                target_scopes=["https://www.googleapis.com/auth/bigquery"],
                lifetime=3600,
            )
            assert credentials == mock_impersonated

    def test_resolve_impersonated_credentials_default_scopes(self):
        """Test impersonated credentials with default scopes."""
        config = CredConfigAuto()
        provider = CredProvider(config=config)

        mock_source_credentials = MagicMock()

        with patch(
            "ayuna_creds.gcp_provider.ImpersonatedCredentials"
        ) as mock_impersonated_class:
            mock_impersonated = MagicMock()
            mock_impersonated_class.return_value = mock_impersonated

            provider.resolve_impersonated_credentials(
                source_credentials=mock_source_credentials,
                target_principal="target@my-project.iam.gserviceaccount.com",
            )

            call_kwargs = mock_impersonated_class.call_args[1]
            assert call_kwargs["target_scopes"] == [
                "https://www.googleapis.com/auth/cloud-platform"
            ]
            assert call_kwargs["lifetime"] == 3600


class TestCredProviderUnsupportedMethod:
    """Tests for unsupported GCP credential methods."""

    def test_unsupported_method_raises_error(self):
        """Test that unsupported method raises ValueError."""
        config = MagicMock()
        config.typid = "unsupported_method"
        provider = CredProvider(config=config)

        with pytest.raises(ValueError) as exc_info:
            provider.resolve_credentials()

        assert "unsupported_method" in str(exc_info.value)


class TestCredProviderFileOperations:
    """Tests for file operations in GCP credential provider."""

    def test_service_account_file_not_found(self):
        """Test that missing key file raises appropriate error."""
        config = CredConfigServiceAccount(key_file_path="/nonexistent/path/key.json")
        provider = CredProvider(config=config)

        with pytest.raises(FileNotFoundError):
            provider.resolve_credentials()

    def test_service_account_invalid_json(self):
        """Test that invalid JSON in key file raises error."""
        config = CredConfigServiceAccount(key_file_path="/path/to/key.json")
        provider = CredProvider(config=config)

        with patch(
            "ayuna_creds.gcp_provider.open", mock_open(read_data="invalid json")
        ):
            with pytest.raises(json.JSONDecodeError):
                provider.resolve_credentials()
