"""Tests for AWSSecrets implementation."""

from unittest.mock import MagicMock, patch

import orjson as json
import pytest
from ayuna_creds.aws_config import CredConfigAuto as AwsCredConfigAuto
from botocore.exceptions import ClientError

from ayuna_secrets import (
    AWSSecretsConfig,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    SecretsError,
)
from ayuna_secrets.aws import AWSSecrets


def _make_client_error(code: str) -> ClientError:
    """Create a botocore ClientError with a given error code."""
    return ClientError(
        {"Error": {"Code": code, "Message": f"Test error: {code}"}},
        "GetSecretValue",
    )


def make_aws_vault(initial_secrets: dict | None = None, secret_id: str = "test/secret"):
    """
    Create an AWSSecrets instance with a mocked boto3 session.

    Returns (vault, mock_client) so callers can configure side effects per test.
    The mock_client is pre-configured with initial_secrets if provided.
    """
    config = AWSSecretsConfig(
        secret_id=secret_id,
        cred_config=AwsCredConfigAuto(region="us-east-1"),
    )

    mock_client = MagicMock()
    if initial_secrets is not None:
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(initial_secrets).decode("utf-8")
        }

    mock_session = MagicMock()
    mock_session.client.return_value = mock_client

    with patch("ayuna_secrets.aws.CredProvider") as mock_provider_class:
        mock_provider = MagicMock()
        mock_provider_class.return_value = mock_provider
        mock_provider.resolve_session.return_value = mock_session
        vault = AWSSecrets(config=config)

    return vault, mock_client


class TestAWSSecretsInit:
    """Tests for AWSSecrets initialization."""

    def test_vault_type(self):
        """Test that vault_type is 'aws'."""
        vault, _ = make_aws_vault({})
        assert vault.vault_type == "aws"

    def test_cache_is_empty_on_init(self):
        """Test that the secrets cache starts as None before any retrieval."""
        vault, _ = make_aws_vault({})
        assert vault._secrets_cache is None

    def test_session_client_called_with_secrets_manager(self):
        """Test that the boto3 session creates a secretsmanager client."""
        config = AWSSecretsConfig(
            secret_id="test/secret",
            cred_config=AwsCredConfigAuto(region="eu-west-1"),
        )
        mock_session = MagicMock()

        with patch("ayuna_secrets.aws.CredProvider") as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.resolve_session.return_value = mock_session
            AWSSecrets(config=config)

        mock_session.client.assert_called_once_with(
            "secretsmanager", region_name="eu-west-1"
        )


class TestAWSSecretsRetrieve:
    """Tests for AWSSecrets.retrieve_secret()."""

    def test_retrieve_existing_key(self):
        """Test retrieving a key that exists in the secret JSON."""
        vault, _ = make_aws_vault({"db_pass": "hunter2", "api_key": "abc"})
        assert vault.retrieve_secret("db_pass") == "hunter2"

    def test_retrieve_missing_key_returns_none(self):
        """Test that a key absent from the secret JSON returns None."""
        vault, _ = make_aws_vault({"other_key": "value"})
        assert vault.retrieve_secret("missing_key") is None

    def test_retrieve_caches_aws_response(self):
        """Test that AWS is only queried once due to in-memory caching."""
        vault, mock_client = make_aws_vault({"k": "v"})

        vault.retrieve_secret("k")
        vault.retrieve_secret("k")

        mock_client.get_secret_value.assert_called_once()

    def test_retrieve_resource_not_found_raises(self):
        """Test that ResourceNotFoundException from AWS raises SecretNotFoundError."""
        vault, mock_client = make_aws_vault()
        mock_client.get_secret_value.side_effect = _make_client_error(
            "ResourceNotFoundException"
        )
        with pytest.raises(SecretNotFoundError):
            vault.retrieve_secret("any_key")

    def test_retrieve_access_denied_raises(self):
        """Test that AccessDeniedException from AWS raises SecretsError."""
        vault, mock_client = make_aws_vault()
        mock_client.get_secret_value.side_effect = _make_client_error(
            "AccessDeniedException"
        )
        with pytest.raises(SecretsError):
            vault.retrieve_secret("any_key")

    def test_retrieve_other_client_error_raises(self):
        """Test that an unexpected ClientError raises SecretsError."""
        vault, mock_client = make_aws_vault()
        mock_client.get_secret_value.side_effect = _make_client_error(
            "InternalServiceError"
        )
        with pytest.raises(SecretsError):
            vault.retrieve_secret("any_key")

    def test_retrieve_non_dict_json_raises(self):
        """Test that a secret value that is not a JSON object raises SecretsError."""
        vault, mock_client = make_aws_vault()
        mock_client.get_secret_value.return_value = {
            "SecretString": '["list", "not", "a", "dict"]'
        }
        with pytest.raises(SecretsError, match="not a valid JSON object"):
            vault.retrieve_secret("key")

    def test_retrieve_invalid_json_raises(self):
        """Test that a non-JSON secret value raises SecretsError."""
        vault, mock_client = make_aws_vault()
        mock_client.get_secret_value.return_value = {"SecretString": "{{not json}}"}
        with pytest.raises(SecretsError):
            vault.retrieve_secret("key")


class TestAWSSecretsStore:
    """Tests for AWSSecrets.store_secret()."""

    def test_store_new_key(self):
        """Test storing a new key calls update_secret with the key added."""
        vault, mock_client = make_aws_vault({"existing": "value"})

        vault.store_secret(key="new_key", value="new_value")

        updated = json.loads(mock_client.update_secret.call_args[1]["SecretString"])
        assert updated["new_key"] == "new_value"
        assert updated["existing"] == "value"

    def test_store_duplicate_raises(self):
        """Test that storing an existing key without replace raises SecretAlreadyExistsError."""
        vault, _ = make_aws_vault({"existing": "value"})

        with pytest.raises(SecretAlreadyExistsError):
            vault.store_secret(key="existing", value="new")

    def test_store_with_replace_overwrites(self):
        """Test that replace=True overwrites an existing key."""
        vault, mock_client = make_aws_vault({"existing": "old"})
        vault.store_secret(key="existing", value="new", replace=True)

        updated = json.loads(mock_client.update_secret.call_args[1]["SecretString"])
        assert updated["existing"] == "new"

    def test_store_updates_cache(self):
        """Test that cache is updated after a successful store."""
        vault, _ = make_aws_vault({"k": "v"})
        vault.retrieve_secret("k")  # populate cache

        vault.store_secret(key="new_key", value="new_value")

        assert vault._secrets_cache is not None
        assert vault._secrets_cache["new_key"] == "new_value"

    def test_store_update_secret_error_raises(self):
        """Test that a ClientError from update_secret raises SecretsError."""
        vault, mock_client = make_aws_vault({})
        mock_client.update_secret.side_effect = _make_client_error(
            "InternalServiceError"
        )

        with pytest.raises(SecretsError):
            vault.store_secret(key="k", value="v")


class TestAWSSecretsDelete:
    """Tests for AWSSecrets.delete_secret()."""

    def test_delete_existing_key(self):
        """Test deleting an existing key updates the secret in AWS."""
        vault, mock_client = make_aws_vault({"to_delete": "val", "to_keep": "keep"})
        vault.delete_secret("to_delete")

        updated = json.loads(mock_client.update_secret.call_args[1]["SecretString"])
        assert "to_delete" not in updated
        assert updated["to_keep"] == "keep"

    def test_delete_missing_key_raises(self):
        """Test that deleting a non-existent key raises SecretNotFoundError."""
        vault, _ = make_aws_vault({"other": "value"})

        with pytest.raises(SecretNotFoundError):
            vault.delete_secret("nonexistent")

    def test_delete_updates_cache(self):
        """Test that cache is updated after a successful delete."""
        vault, _ = make_aws_vault({"a": "1", "b": "2"})
        vault.retrieve_secret("a")  # populate cache

        vault.delete_secret("a")

        assert vault._secrets_cache is not None
        assert "a" not in vault._secrets_cache
        assert "b" in vault._secrets_cache


class TestAWSSecretsList:
    """Tests for AWSSecrets.list_secrets()."""

    def test_list_returns_all_keys(self):
        """Test that list_secrets returns all keys from the JSON secret."""
        vault, _ = make_aws_vault({"key_a": "a", "key_b": "b", "key_c": "c"})
        assert sorted(vault.list_secrets()) == ["key_a", "key_b", "key_c"]

    def test_list_empty_secret(self):
        """Test that list_secrets returns an empty list for an empty JSON object."""
        vault, _ = make_aws_vault({})
        assert vault.list_secrets() == []
