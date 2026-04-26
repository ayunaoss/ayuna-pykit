"""Tests for base secrets configuration models, error types, and factory."""

from unittest.mock import MagicMock, patch

import pytest
from ayuna_core.basetypes import AyunaError
from ayuna_creds.aws_config import CredConfigAuto as AwsCredConfigAuto
from ayuna_creds.gcp_config import CredConfigAuto as GcpCredConfigAuto
from pydantic import ValidationError

from ayuna_secrets import (
    AWSSecretsConfig,
    AzureSecretsConfig,
    BaseSecrets,
    GCPSecretsConfig,
    LocalSecretsConfig,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    SecretsError,
)


class TestLocalSecretsConfig:
    """Tests for LocalSecretsConfig model."""

    def test_default_values(self, tmp_path):
        """Test that local config has correct defaults."""
        config = LocalSecretsConfig(yaml_file_path=str(tmp_path / "s.yaml"))
        assert config.typid == "local"
        assert config.encryption_key is None
        assert config.encrypt_values_only is True

    def test_with_encryption_key(self, tmp_path):
        """Test local config with an encryption key."""
        config = LocalSecretsConfig(
            yaml_file_path=str(tmp_path / "s.yaml"),
            encryption_key="my-secret-key",
        )
        assert config.encryption_key == "my-secret-key"

    def test_encrypt_values_only_can_be_disabled(self, tmp_path):
        """Test that encrypt_values_only flag can be set to False."""
        config = LocalSecretsConfig(
            yaml_file_path=str(tmp_path / "s.yaml"),
            encryption_key="key",
            encrypt_values_only=False,
        )
        assert config.encrypt_values_only is False

    def test_empty_yaml_file_path_raises(self):
        """Test that an empty yaml_file_path raises a validation error."""
        with pytest.raises(ValidationError):
            LocalSecretsConfig(yaml_file_path="")


class TestAzureSecretsConfig:
    """Tests for AzureSecretsConfig model."""

    def test_valid_config(self):
        """Test valid Azure secrets config."""
        config = AzureSecretsConfig(vault_url="https://my-vault.vault.azure.net/")
        assert config.typid == "azure"
        assert config.vault_url == "https://my-vault.vault.azure.net/"

    def test_empty_vault_url_raises(self):
        """Test that an empty vault_url raises a validation error."""
        with pytest.raises(ValidationError):
            AzureSecretsConfig(vault_url="")


class TestAWSSecretsConfig:
    """Tests for AWSSecretsConfig model."""

    def test_valid_config(self):
        """Test valid AWS secrets config."""
        config = AWSSecretsConfig(
            secret_id="prod/db/password",
            cred_config=AwsCredConfigAuto(),
        )
        assert config.typid == "aws"
        assert config.secret_id == "prod/db/password"

    def test_empty_secret_id_raises(self):
        """Test that an empty secret_id raises a validation error."""
        with pytest.raises(ValidationError):
            AWSSecretsConfig(secret_id="", cred_config=AwsCredConfigAuto())


class TestGCPSecretsConfig:
    """Tests for GCPSecretsConfig model."""

    def test_valid_config(self):
        """Test valid GCP secrets config."""
        config = GCPSecretsConfig(
            project_id="my-gcp-project",
            secret_id="my-secret",
            cred_config=GcpCredConfigAuto(),
        )
        assert config.typid == "gcp"
        assert config.project_id == "my-gcp-project"
        assert config.secret_id == "my-secret"

    def test_empty_project_id_raises(self):
        """Test that an empty project_id raises a validation error."""
        with pytest.raises(ValidationError):
            GCPSecretsConfig(
                project_id="",
                secret_id="my-secret",
                cred_config=GcpCredConfigAuto(),
            )

    def test_empty_secret_id_raises(self):
        """Test that an empty secret_id raises a validation error."""
        with pytest.raises(ValidationError):
            GCPSecretsConfig(
                project_id="my-project",
                secret_id="",
                cred_config=GcpCredConfigAuto(),
            )


class TestSecretsErrors:
    """Tests for secrets error hierarchy."""

    def test_secrets_error_is_ayuna_error(self):
        """Test that SecretsError inherits from AyunaError."""
        assert issubclass(SecretsError, AyunaError)

    def test_secret_not_found_is_secrets_error(self):
        """Test that SecretNotFoundError inherits from SecretsError."""
        assert issubclass(SecretNotFoundError, SecretsError)

    def test_secret_already_exists_is_secrets_error(self):
        """Test that SecretAlreadyExistsError inherits from SecretsError."""
        assert issubclass(SecretAlreadyExistsError, SecretsError)

    def test_secret_not_found_caught_as_secrets_error(self):
        """Test that SecretNotFoundError can be caught as SecretsError."""
        with pytest.raises(SecretsError):
            raise SecretNotFoundError("not found")

    def test_secret_already_exists_caught_as_secrets_error(self):
        """Test that SecretAlreadyExistsError can be caught as SecretsError."""
        with pytest.raises(SecretsError):
            raise SecretAlreadyExistsError("already exists")


class TestBaseSecretsFactory:
    """Tests for BaseSecrets.create() factory method."""

    def test_create_local(self, tmp_path):
        """Test that create() returns a LocalSecrets instance for 'local' typid."""
        from ayuna_secrets.local import LocalSecrets

        config = LocalSecretsConfig(yaml_file_path=str(tmp_path / "s.yaml"))
        vault = BaseSecrets.create(config)

        assert isinstance(vault, LocalSecrets)
        assert vault.vault_type == "local"

    def test_create_aws(self):
        """Test that create() returns an AWSSecrets instance for 'aws' typid."""
        from ayuna_secrets.aws import AWSSecrets

        config = AWSSecretsConfig(
            secret_id="test/secret",
            cred_config=AwsCredConfigAuto(),
        )
        mock_session = MagicMock()

        with patch("ayuna_secrets.aws.CredProvider") as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.resolve_session.return_value = mock_session

            vault = BaseSecrets.create(config)

        assert isinstance(vault, AWSSecrets)
        assert vault.vault_type == "aws"

    def test_create_azure(self):
        """Test that create() returns an AzureSecrets instance for 'azure' typid."""
        from ayuna_secrets.azure import AzureSecrets

        config = AzureSecretsConfig(vault_url="https://test.vault.azure.net/")

        mock_cred_provider = MagicMock()
        mock_cred_provider.resolve_credential.return_value = MagicMock()

        with (
            patch(
                "ayuna_secrets.azure.AzureCredProvider", return_value=mock_cred_provider
            ),
            patch("ayuna_secrets.azure.SecretClient"),
        ):
            vault = BaseSecrets.create(config)

        assert isinstance(vault, AzureSecrets)
        assert vault.vault_type == "azure"

    def test_create_gcp(self):
        """Test that create() returns a GCPSecrets instance for 'gcp' typid."""
        from ayuna_secrets.gcp import GCPSecrets

        config = GCPSecretsConfig(
            project_id="my-project",
            secret_id="my-secret",
            cred_config=GcpCredConfigAuto(),
        )

        with (
            patch("ayuna_secrets.gcp.CredProvider") as mock_provider_class,
            patch("ayuna_secrets.gcp.secretmanager"),
        ):
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.resolve_credentials.return_value = MagicMock()

            vault = BaseSecrets.create(config)

        assert isinstance(vault, GCPSecrets)
        assert vault.vault_type == "gcp"

    def test_create_unknown_typid_raises(self):
        """Test that create() raises SecretsError for an unknown typid."""
        config = MagicMock()
        config.typid = "unknown_backend"

        with pytest.raises(SecretsError, match="Unknown vault type"):
            BaseSecrets.create(config)
