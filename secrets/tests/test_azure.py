"""Tests for AzureSecrets implementation."""

from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import (
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)

from ayuna_secrets import (
    AzureSecretsConfig,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    SecretsError,
)
from ayuna_secrets.azure import AzureSecrets


def _make_secret(value: str | None) -> MagicMock:
    """Create a mock azure SecretBundle with a given value."""
    secret = MagicMock()
    secret.value = value
    return secret


def _make_http_error(status_code: int, message: str = "error") -> HttpResponseError:
    """Create an HttpResponseError with a given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    err = HttpResponseError(message=message, response=mock_response)
    err.status_code = status_code
    return err


def make_azure_vault():
    """
    Create an AzureSecrets instance with mocked Azure SDK clients.

    Returns (vault, mock_client).
    """
    config = AzureSecretsConfig(vault_url="https://test-vault.vault.azure.net/")
    mock_client = MagicMock()
    mock_cred_provider = MagicMock()
    mock_cred_provider.resolve_credential.return_value = MagicMock()

    with (
        patch("ayuna_secrets.azure.AzureCredProvider", return_value=mock_cred_provider),
        patch("ayuna_secrets.azure.SecretClient", return_value=mock_client),
    ):
        vault = AzureSecrets(config=config)

    return vault, mock_client


class TestAzureSecretsInit:
    """Tests for AzureSecrets initialization."""

    def test_vault_type(self):
        """Test that vault_type is 'azure'."""
        vault, _ = make_azure_vault()
        assert vault.vault_type == "azure"

    def test_vault_url_stored(self):
        """Test that the vault URL is stored on the instance."""
        vault, _ = make_azure_vault()
        assert vault._vault_url == "https://test-vault.vault.azure.net/"

    def test_secret_client_created_with_correct_url(self):
        """Test that SecretClient is instantiated with the vault URL."""
        config = AzureSecretsConfig(vault_url="https://my-vault.vault.azure.net/")
        mock_credential = MagicMock()
        mock_cred_provider = MagicMock()
        mock_cred_provider.resolve_credential.return_value = mock_credential

        with (
            patch(
                "ayuna_secrets.azure.AzureCredProvider",
                return_value=mock_cred_provider,
            ),
            patch("ayuna_secrets.azure.SecretClient") as mock_client_class,
        ):
            AzureSecrets(config=config)

            mock_client_class.assert_called_once_with(
                vault_url="https://my-vault.vault.azure.net/",
                credential=mock_credential,
            )


class TestAzureSecretsRetrieve:
    """Tests for AzureSecrets.retrieve_secret()."""

    def test_retrieve_existing_secret(self):
        """Test retrieving a secret that exists in the vault."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.return_value = _make_secret("secret_value")

        assert vault.retrieve_secret("my_secret") == "secret_value"
        mock_client.get_secret.assert_called_once_with("my_secret")

    def test_retrieve_missing_secret_returns_none(self):
        """Test that a missing secret returns None."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.side_effect = ResourceNotFoundError("not found")

        assert vault.retrieve_secret("missing") is None

    def test_retrieve_secret_with_none_value_returns_none(self):
        """Test that a secret with no value returns None."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.return_value = _make_secret(None)

        assert vault.retrieve_secret("empty_secret") is None

    def test_retrieve_http_error_raises(self):
        """Test that an HttpResponseError raises SecretsError."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.side_effect = _make_http_error(500, "server error")

        with pytest.raises(SecretsError, match="Azure API error"):
            vault.retrieve_secret("my_secret")

    def test_retrieve_network_error_raises(self):
        """Test that a ServiceRequestError (network error) raises SecretsError."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.side_effect = ServiceRequestError("network failure")

        with pytest.raises(SecretsError, match="Network error"):
            vault.retrieve_secret("my_secret")


class TestAzureSecretsStore:
    """Tests for AzureSecrets.store_secret()."""

    def test_store_new_key(self):
        """Test storing a key that does not already exist."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.side_effect = ResourceNotFoundError("not found")

        vault.store_secret(key="new_key", value="new_value")

        mock_client.set_secret.assert_called_once_with("new_key", "new_value")

    def test_store_duplicate_raises(self):
        """Test that storing a key that already exists raises SecretAlreadyExistsError."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.return_value = _make_secret("existing_value")

        with pytest.raises(SecretAlreadyExistsError):
            vault.store_secret(key="existing_key", value="new_value")

    def test_store_with_replace_skips_existence_check(self):
        """Test that replace=True does not check for existing secret."""
        vault, mock_client = make_azure_vault()
        vault.store_secret(key="any_key", value="any_value", replace=True)

        mock_client.get_secret.assert_not_called()
        mock_client.set_secret.assert_called_once_with("any_key", "any_value")

    def test_store_http_error_on_set_raises(self):
        """Test that an HttpResponseError during set_secret raises SecretsError."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.side_effect = ResourceNotFoundError("not found")
        mock_client.set_secret.side_effect = _make_http_error(403, "forbidden")

        with pytest.raises(SecretsError):
            vault.store_secret(key="k", value="v")

    def test_store_http_error_on_check_raises(self):
        """Test that an unexpected error during existence check raises SecretsError."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.side_effect = _make_http_error(500, "server error")

        with pytest.raises(SecretsError):
            vault.store_secret(key="k", value="v", replace=False)


class TestAzureSecretsDelete:
    """Tests for AzureSecrets.delete_secret()."""

    def test_delete_existing_secret(self):
        """Test deleting an existing secret calls begin_delete_secret."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.return_value = _make_secret("value")

        vault.delete_secret("my_secret")

        mock_client.begin_delete_secret.assert_called_once_with("my_secret")
        mock_client.begin_delete_secret.return_value.wait.assert_called_once_with(30)

    def test_delete_missing_secret_raises(self):
        """Test that deleting a non-existent secret raises SecretNotFoundError."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.side_effect = ResourceNotFoundError("not found")

        with pytest.raises(SecretNotFoundError):
            vault.delete_secret("nonexistent")

    def test_delete_conflict_409_raises(self):
        """Test that a 409 conflict during deletion raises SecretsError."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.return_value = _make_secret("value")
        mock_client.begin_delete_secret.return_value.wait.side_effect = (
            _make_http_error(409, "conflict")
        )

        with pytest.raises(SecretsError, match="deleted state"):
            vault.delete_secret("my_secret")

    def test_delete_http_error_raises(self):
        """Test that a non-409 HttpResponseError during deletion raises SecretsError."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.return_value = _make_secret("value")
        mock_client.begin_delete_secret.return_value.wait.side_effect = (
            _make_http_error(500, "internal error")
        )

        with pytest.raises(SecretsError, match="Failed to delete"):
            vault.delete_secret("my_secret")

    def test_delete_check_error_raises(self):
        """Test that an error during the pre-delete check raises SecretsError."""
        vault, mock_client = make_azure_vault()
        mock_client.get_secret.side_effect = _make_http_error(403, "forbidden")

        with pytest.raises(SecretsError):
            vault.delete_secret("my_secret")


class TestAzureSecretsList:
    """Tests for AzureSecrets.list_secrets()."""

    def test_list_returns_secret_names(self):
        """Test that list_secrets returns names of all secrets in the vault."""
        vault, mock_client = make_azure_vault()

        def _prop(n):
            p = MagicMock()
            p.name = n
            return p

        mock_client.list_properties_of_secrets.return_value = iter(
            [_prop("alpha"), _prop("beta"), _prop("gamma")]
        )

        assert sorted(vault.list_secrets()) == ["alpha", "beta", "gamma"]

    def test_list_skips_secrets_with_no_name(self):
        """Test that secrets without a name attribute are excluded from the list."""
        vault, mock_client = make_azure_vault()

        valid_prop = MagicMock()
        valid_prop.name = "valid"
        none_prop = MagicMock()
        none_prop.name = None
        empty_prop = MagicMock()
        empty_prop.name = ""

        mock_client.list_properties_of_secrets.return_value = iter(
            [valid_prop, none_prop, empty_prop]
        )

        result = vault.list_secrets()
        assert result == ["valid"]

    def test_list_empty_vault(self):
        """Test that list_secrets returns an empty list for a vault with no secrets."""
        vault, mock_client = make_azure_vault()
        mock_client.list_properties_of_secrets.return_value = iter([])

        assert vault.list_secrets() == []

    def test_list_http_error_raises(self):
        """Test that an HttpResponseError during listing raises SecretsError."""
        vault, mock_client = make_azure_vault()
        mock_client.list_properties_of_secrets.side_effect = _make_http_error(
            403, "forbidden"
        )

        with pytest.raises(SecretsError):
            vault.list_secrets()
