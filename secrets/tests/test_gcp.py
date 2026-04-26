"""Tests for GCPSecrets implementation."""

from unittest.mock import MagicMock, patch

import orjson as json
import pytest
from ayuna_creds.gcp_config import CredConfigAuto as GcpCredConfigAuto
from google.api_core.exceptions import GoogleAPICallError, NotFound, PermissionDenied

from ayuna_secrets import (
    GCPSecretsConfig,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    SecretsError,
)
from ayuna_secrets.gcp import GCPSecrets


def make_gcp_vault(initial_secrets: dict | None = None):
    """
    Create a GCPSecrets instance with mocked GCP SDK clients.

    Returns (vault, mock_client).
    The mock_client is pre-configured with initial_secrets if provided.
    """
    config = GCPSecretsConfig(
        project_id="test-project",
        secret_id="test-secret",
        cred_config=GcpCredConfigAuto(),
    )

    mock_client = MagicMock()
    if initial_secrets is not None:
        mock_response = MagicMock()
        mock_response.payload.data = json.dumps(initial_secrets)
        mock_client.access_secret_version.return_value = mock_response

    with (
        patch("ayuna_secrets.gcp.CredProvider") as mock_provider_class,
        patch("ayuna_secrets.gcp.secretmanager") as mock_secretmanager,
    ):
        mock_provider = MagicMock()
        mock_provider_class.return_value = mock_provider
        mock_provider.resolve_credentials.return_value = MagicMock()
        mock_secretmanager.SecretManagerServiceClient.return_value = mock_client

        vault = GCPSecrets(config=config)

    return vault, mock_client


class TestGCPSecretsInit:
    """Tests for GCPSecrets initialization."""

    def test_vault_type(self):
        """Test that vault_type is 'gcp'."""
        vault, _ = make_gcp_vault({})
        assert vault.vault_type == "gcp"

    def test_cache_is_empty_on_init(self):
        """Test that the secrets cache starts as None before any retrieval."""
        vault, _ = make_gcp_vault({})
        assert vault._secrets_cache is None

    def test_parent_path_format(self):
        """Test that the _parent resource path is formatted correctly."""
        vault, _ = make_gcp_vault({})
        assert vault._parent == "projects/test-project/secrets/test-secret"

    def test_credentials_resolved_from_config(self):
        """Test that CredProvider is called to resolve GCP credentials."""
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

            GCPSecrets(config=config)

            mock_provider.resolve_credentials.assert_called_once()


class TestGCPSecretsRetrieve:
    """Tests for GCPSecrets.retrieve_secret()."""

    def test_retrieve_existing_key(self):
        """Test retrieving a key that exists in the secret payload."""
        vault, _ = make_gcp_vault({"db_pass": "hunter2", "api_key": "xyz"})
        assert vault.retrieve_secret("db_pass") == "hunter2"

    def test_retrieve_missing_key_returns_none(self):
        """Test that a key absent from the secret payload returns None."""
        vault, _ = make_gcp_vault({"other_key": "value"})
        assert vault.retrieve_secret("missing_key") is None

    def test_retrieve_caches_gcp_response(self):
        """Test that GCP is only queried once due to in-memory caching."""
        vault, mock_client = make_gcp_vault({"k": "v"})

        vault.retrieve_secret("k")
        vault.retrieve_secret("k")

        mock_client.access_secret_version.assert_called_once()

    def test_retrieve_not_found_raises(self):
        """Test that a NotFound error from GCP raises SecretNotFoundError."""
        vault, mock_client = make_gcp_vault()
        mock_client.access_secret_version.side_effect = NotFound("secret not found")

        with pytest.raises(SecretNotFoundError):
            vault.retrieve_secret("any_key")

    def test_retrieve_permission_denied_raises(self):
        """Test that a PermissionDenied error from GCP raises SecretsError."""
        vault, mock_client = make_gcp_vault()
        mock_client.access_secret_version.side_effect = PermissionDenied(
            "access denied"
        )

        with pytest.raises(SecretsError, match="Access denied"):
            vault.retrieve_secret("any_key")

    def test_retrieve_gcp_api_error_raises(self):
        """Test that a generic GoogleAPICallError raises SecretsError."""
        vault, mock_client = make_gcp_vault()
        mock_client.access_secret_version.side_effect = GoogleAPICallError(
            "api failure"
        )

        with pytest.raises(SecretsError, match="GCP API error"):
            vault.retrieve_secret("any_key")

    def test_retrieve_non_dict_json_raises(self):
        """Test that a secret payload that is not a JSON object raises SecretsError."""
        vault, mock_client = make_gcp_vault()
        mock_response = MagicMock()
        mock_response.payload.data = json.dumps(["list", "not", "dict"])
        mock_client.access_secret_version.return_value = mock_response

        with pytest.raises(SecretsError, match="not a valid JSON object"):
            vault.retrieve_secret("key")

    def test_retrieve_invalid_json_raises(self):
        """Test that an invalid JSON payload raises SecretsError."""
        vault, mock_client = make_gcp_vault()
        mock_response = MagicMock()
        mock_response.payload.data = b"{{not valid json}}"
        mock_client.access_secret_version.return_value = mock_response

        with pytest.raises(SecretsError, match="Failed to parse"):
            vault.retrieve_secret("key")


class TestGCPSecretsStore:
    """Tests for GCPSecrets.store_secret()."""

    def test_store_new_key(self):
        """Test storing a new key adds a new secret version in GCP."""
        vault, mock_client = make_gcp_vault({"existing": "value"})

        vault.store_secret(key="new_key", value="new_value")

        mock_client.add_secret_version.assert_called_once()

    def test_store_new_key_payload_content(self):
        """Test that the new version payload contains both old and new keys."""
        vault, _ = make_gcp_vault({"existing": "value"})
        vault.store_secret(key="new_key", value="new_value")

        # The cache should reflect both keys after store
        assert vault._secrets_cache is not None
        assert vault._secrets_cache["new_key"] == "new_value"
        assert vault._secrets_cache["existing"] == "value"

    def test_store_duplicate_raises(self):
        """Test that storing an existing key without replace raises SecretAlreadyExistsError."""
        vault, _ = make_gcp_vault({"existing": "value"})

        with pytest.raises(SecretAlreadyExistsError):
            vault.store_secret(key="existing", value="new")

    def test_store_with_replace_overwrites(self):
        """Test that replace=True overwrites an existing key."""
        vault, _ = make_gcp_vault({"existing": "old"})
        vault.store_secret(key="existing", value="new", replace=True)
        assert vault._secrets_cache is not None
        assert vault._secrets_cache["existing"] == "new"

    def test_store_gcp_api_error_raises(self):
        """Test that a GoogleAPICallError during add_secret_version raises SecretsError."""
        vault, mock_client = make_gcp_vault({})
        mock_client.add_secret_version.side_effect = GoogleAPICallError("api failure")

        with pytest.raises(SecretsError, match="Failed to add GCP secret version"):
            vault.store_secret(key="k", value="v")


class TestGCPSecretsDelete:
    """Tests for GCPSecrets.delete_secret()."""

    def test_delete_existing_key(self):
        """Test deleting an existing key adds a new version without that key."""
        vault, _ = make_gcp_vault({"to_delete": "val", "to_keep": "keep"})
        vault.delete_secret("to_delete")

        assert vault._secrets_cache is not None
        assert "to_delete" not in vault._secrets_cache
        assert vault._secrets_cache["to_keep"] == "keep"

    def test_delete_calls_add_secret_version(self):
        """Test that delete persists the updated secret by calling add_secret_version."""
        vault, mock_client = make_gcp_vault({"a": "1"})
        vault.delete_secret("a")
        mock_client.add_secret_version.assert_called_once()

    def test_delete_missing_key_raises(self):
        """Test that deleting a non-existent key raises SecretNotFoundError."""
        vault, _ = make_gcp_vault({"other": "value"})

        with pytest.raises(SecretNotFoundError):
            vault.delete_secret("nonexistent")


class TestGCPSecretsList:
    """Tests for GCPSecrets.list_secrets()."""

    def test_list_returns_all_keys(self):
        """Test that list_secrets returns all keys from the JSON payload."""
        vault, _ = make_gcp_vault({"key_a": "a", "key_b": "b", "key_c": "c"})
        assert sorted(vault.list_secrets()) == ["key_a", "key_b", "key_c"]

    def test_list_empty_secret(self):
        """Test that list_secrets returns an empty list for an empty JSON object."""
        vault, _ = make_gcp_vault({})
        assert vault.list_secrets() == []

    def test_list_caches_result(self):
        """Test that listing secrets uses the cache after the first fetch."""
        vault, mock_client = make_gcp_vault({"k": "v"})

        vault.list_secrets()
        vault.list_secrets()

        mock_client.access_secret_version.assert_called_once()


class TestGCPSecretsCache:
    """Tests for GCPSecrets cache invalidation behavior."""

    def test_cache_populated_after_retrieve(self):
        """Test that the cache is populated after the first retrieve call."""
        vault, _ = make_gcp_vault({"k": "v"})
        assert vault._secrets_cache is None

        vault.retrieve_secret("k")
        assert vault._secrets_cache is not None

    def test_cache_cleared_after_store(self):
        """Test that the in-memory cache reflects mutations after store_secret."""
        vault, _ = make_gcp_vault({"k": "v"})
        vault.store_secret(key="new_key", value="new_value", replace=False)

        assert vault._secrets_cache is not None
        assert vault._secrets_cache.get("new_key") == "new_value"
