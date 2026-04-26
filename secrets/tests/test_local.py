"""Tests for LocalSecrets implementation."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from ayuna_secrets import (
    LocalSecretsConfig,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    SecretsError,
)
from ayuna_secrets.local import LocalSecrets


def make_local_vault(tmp_path: Path, **kwargs) -> LocalSecrets:
    """Create a LocalSecrets instance backed by a temp YAML file."""
    config = LocalSecretsConfig(
        yaml_file_path=str(tmp_path / "secrets.yaml"),
        **kwargs,
    )
    return LocalSecrets(config=config)


class TestLocalSecretsInit:
    """Tests for LocalSecrets initialization."""

    def test_vault_type(self, tmp_path):
        """Test that vault_type is 'local'."""
        vault = make_local_vault(tmp_path)
        assert vault.vault_type == "local"

    def test_empty_vault_on_new_file(self, tmp_path):
        """Test that a new vault with no YAML file starts empty."""
        vault = make_local_vault(tmp_path)
        assert vault.list_secrets() == []

    def test_loads_existing_yaml_on_init(self, tmp_path):
        """Test that an existing YAML file is loaded at initialization."""
        yaml_path = tmp_path / "secrets.yaml"
        yaml_path.write_text("db_pass: hunter2\napi_key: abc123\n")

        vault = make_local_vault(tmp_path)
        assert vault.retrieve_secret("db_pass") == "hunter2"
        assert vault.retrieve_secret("api_key") == "abc123"

    def test_malformed_yaml_raises_secrets_error(self, tmp_path):
        """Test that a YAML parse error on load raises SecretsError."""
        yaml_path = tmp_path / "secrets.yaml"
        yaml_path.write_text("some: content")

        with patch(
            "ayuna_secrets.local.yaml.safe_load", side_effect=yaml.YAMLError("bad")
        ):
            with pytest.raises(SecretsError, match="Failed to parse YAML"):
                make_local_vault(tmp_path)

    def test_os_error_on_read_raises_secrets_error(self, tmp_path):
        """Test that an OS error while reading the YAML file raises SecretsError."""
        yaml_path = tmp_path / "secrets.yaml"
        yaml_path.write_text("key: value")

        with patch("builtins.open", side_effect=OSError("permission denied")):
            with pytest.raises(SecretsError, match="Failed to read secrets file"):
                make_local_vault(tmp_path)


class TestLocalSecretsRetrieve:
    """Tests for LocalSecrets.retrieve_secret()."""

    def test_retrieve_existing_secret(self, tmp_path):
        """Test retrieving a secret that exists."""
        vault = make_local_vault(tmp_path)
        vault.store_secret(key="token", value="secret-token")
        assert vault.retrieve_secret("token") == "secret-token"

    def test_retrieve_missing_secret_returns_none(self, tmp_path):
        """Test that retrieving a non-existent key returns None."""
        vault = make_local_vault(tmp_path)
        assert vault.retrieve_secret("nonexistent") is None


class TestLocalSecretsStore:
    """Tests for LocalSecrets.store_secret()."""

    def test_store_new_secret(self, tmp_path):
        """Test storing a new secret."""
        vault = make_local_vault(tmp_path)
        vault.store_secret(key="db_password", value="s3cr3t")
        assert vault.retrieve_secret("db_password") == "s3cr3t"

    def test_store_duplicate_raises(self, tmp_path):
        """Test that storing a duplicate key without replace raises SecretAlreadyExistsError."""
        vault = make_local_vault(tmp_path)
        vault.store_secret(key="api_key", value="original")

        with pytest.raises(SecretAlreadyExistsError):
            vault.store_secret(key="api_key", value="duplicate")

    def test_store_duplicate_error_message(self, tmp_path):
        """Test that the duplicate error message mentions the key."""
        vault = make_local_vault(tmp_path)
        vault.store_secret(key="my_key", value="v")

        with pytest.raises(SecretAlreadyExistsError, match="my_key"):
            vault.store_secret(key="my_key", value="v2")

    def test_store_with_replace_overwrites(self, tmp_path):
        """Test that storing with replace=True overwrites an existing secret."""
        vault = make_local_vault(tmp_path)
        vault.store_secret(key="api_key", value="original")
        vault.store_secret(key="api_key", value="updated", replace=True)
        assert vault.retrieve_secret("api_key") == "updated"

    def test_store_persists_to_yaml(self, tmp_path):
        """Test that stored secrets are written to the YAML file."""
        yaml_path = tmp_path / "secrets.yaml"
        vault = make_local_vault(tmp_path)

        vault.store_secret(key="db_pass", value="hunter2")

        assert yaml_path.exists()
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        assert data["db_pass"] == "hunter2"

    def test_store_creates_parent_directories(self, tmp_path):
        """Test that store creates missing parent directories."""
        nested_path = tmp_path / "a" / "b" / "c" / "secrets.yaml"
        config = LocalSecretsConfig(yaml_file_path=str(nested_path))
        vault = LocalSecrets(config=config)

        vault.store_secret(key="k", value="v")
        assert nested_path.exists()

    def test_os_error_on_write_raises_secrets_error(self, tmp_path):
        """Test that an OS error while writing raises SecretsError."""
        vault = make_local_vault(tmp_path)

        # After init, mock open to fail on write
        with patch("builtins.open", side_effect=OSError("disk full")):
            with pytest.raises(SecretsError, match="Failed to write secrets file"):
                vault.store_secret(key="k", value="v")


class TestLocalSecretsDelete:
    """Tests for LocalSecrets.delete_secret()."""

    def test_delete_existing_secret(self, tmp_path):
        """Test deleting an existing secret removes it."""
        vault = make_local_vault(tmp_path)
        vault.store_secret(key="token", value="abc123")
        vault.delete_secret("token")
        assert vault.retrieve_secret("token") is None

    def test_delete_missing_secret_raises(self, tmp_path):
        """Test that deleting a non-existent key raises SecretNotFoundError."""
        vault = make_local_vault(tmp_path)

        with pytest.raises(SecretNotFoundError):
            vault.delete_secret("nonexistent")

    def test_delete_updates_yaml(self, tmp_path):
        """Test that deletion is persisted to the YAML file."""
        yaml_path = tmp_path / "secrets.yaml"
        vault = make_local_vault(tmp_path)

        vault.store_secret(key="to_delete", value="gone")
        vault.store_secret(key="to_keep", value="stays")
        vault.delete_secret("to_delete")

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        assert "to_delete" not in data
        assert data["to_keep"] == "stays"

    def test_delete_leaves_other_secrets_intact(self, tmp_path):
        """Test that deleting one secret does not affect others."""
        vault = make_local_vault(tmp_path)
        vault.store_secret(key="a", value="1")
        vault.store_secret(key="b", value="2")
        vault.store_secret(key="c", value="3")

        vault.delete_secret("b")

        assert vault.retrieve_secret("a") == "1"
        assert vault.retrieve_secret("b") is None
        assert vault.retrieve_secret("c") == "3"


class TestLocalSecretsList:
    """Tests for LocalSecrets.list_secrets()."""

    def test_list_empty_vault(self, tmp_path):
        """Test that list on an empty vault returns an empty list."""
        vault = make_local_vault(tmp_path)
        assert vault.list_secrets() == []

    def test_list_returns_all_keys(self, tmp_path):
        """Test that list returns all stored keys."""
        vault = make_local_vault(tmp_path)
        vault.store_secret(key="key_a", value="a")
        vault.store_secret(key="key_b", value="b")
        vault.store_secret(key="key_c", value="c")

        assert sorted(vault.list_secrets()) == ["key_a", "key_b", "key_c"]

    def test_list_after_delete(self, tmp_path):
        """Test that list does not include deleted keys."""
        vault = make_local_vault(tmp_path)
        vault.store_secret(key="keep", value="v")
        vault.store_secret(key="remove", value="v")
        vault.delete_secret("remove")

        assert vault.list_secrets() == ["keep"]


class TestLocalSecretsPasswordEncryption:
    """Tests for LocalSecrets with password-based (PBKDF2) encryption."""

    def test_store_and_retrieve_with_password(self, tmp_path):
        """Test basic encrypt/decrypt round-trip with a plain password string."""
        vault = make_local_vault(tmp_path, encryption_key="my-secret-password")
        vault.store_secret(key="token", value="plaintext_value")
        assert vault.retrieve_secret("token") == "plaintext_value"

    def test_password_encryption_persists_across_reload(self, tmp_path):
        """Test that password-encrypted secrets survive a vault reload."""
        vault1 = make_local_vault(tmp_path, encryption_key="my-secret-password")
        vault1.store_secret(key="token", value="plaintext_value")

        # Reload vault with same password — salt is persisted so key derivation matches
        vault2 = make_local_vault(tmp_path, encryption_key="my-secret-password")
        assert vault2.retrieve_secret("token") == "plaintext_value"

    def test_salt_stored_in_yaml_when_password_used(self, tmp_path):
        """Test that the PBKDF2 salt is written to the YAML file."""
        yaml_path = tmp_path / "secrets.yaml"
        vault = make_local_vault(tmp_path, encryption_key="my-secret-password")
        vault.store_secret(key="k", value="v")

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        assert "_salt" in data

    def test_salt_not_exposed_in_list_secrets(self, tmp_path):
        """Test that the internal _salt key is not visible via list_secrets."""
        vault = make_local_vault(tmp_path, encryption_key="my-secret-password")
        vault.store_secret(key="k", value="v")

        assert "_salt" not in vault.list_secrets()

    def test_wrong_password_on_reload_raises(self, tmp_path):
        """Test that reloading a vault with the wrong password raises SecretsError."""
        vault1 = make_local_vault(tmp_path, encryption_key="correct-password")
        vault1.store_secret(key="token", value="value")

        with pytest.raises(SecretsError, match="Failed to decrypt"):
            make_local_vault(tmp_path, encryption_key="wrong-password")


class TestLocalSecretsEncryption:
    """Tests for LocalSecrets with Fernet encryption."""

    def test_store_and_retrieve_with_fernet_key(self, tmp_path, fernet_key):
        """Test basic encrypt/decrypt round-trip with a Fernet key."""
        vault = make_local_vault(tmp_path, encryption_key=fernet_key)
        vault.store_secret(key="secret", value="plaintext_value")
        assert vault.retrieve_secret("secret") == "plaintext_value"

    def test_values_encrypted_on_disk(self, tmp_path, fernet_key):
        """Test that values are stored as ENC:<token> on disk."""
        yaml_path = tmp_path / "secrets.yaml"
        vault = make_local_vault(tmp_path, encryption_key=fernet_key)
        vault.store_secret(key="secret", value="plaintext_value")

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        assert data["secret"].startswith("ENC:")
        assert "plaintext_value" not in data["secret"]

    def test_encrypted_values_decrypted_on_reload(self, tmp_path, fernet_key):
        """Test that encrypted values are decrypted correctly when the vault is reloaded."""
        vault1 = make_local_vault(tmp_path, encryption_key=fernet_key)
        vault1.store_secret(key="secret", value="plaintext_value")

        # Create a new instance pointing at the same file with the same key
        vault2 = make_local_vault(tmp_path, encryption_key=fernet_key)
        assert vault2.retrieve_secret("secret") == "plaintext_value"

    def test_replace_encrypted_secret(self, tmp_path, fernet_key):
        """Test replacing an encrypted secret stores the new encrypted value."""
        vault = make_local_vault(tmp_path, encryption_key=fernet_key)
        vault.store_secret(key="token", value="old_value")
        vault.store_secret(key="token", value="new_value", replace=True)
        assert vault.retrieve_secret("token") == "new_value"

    def test_invalid_fernet_token_on_load_raises(self, tmp_path, fernet_key):
        """Test that a corrupted ENC: value raises SecretsError on load."""
        yaml_path = tmp_path / "secrets.yaml"
        yaml_path.write_text("secret: 'ENC:not-a-valid-fernet-token'\n")

        with pytest.raises(SecretsError, match="Failed to decrypt"):
            make_local_vault(tmp_path, encryption_key=fernet_key)

    def test_plain_values_in_encrypted_vault_are_preserved(self, tmp_path, fernet_key):
        """Test that plain (non-ENC:) values in an encrypted vault are returned as-is."""
        yaml_path = tmp_path / "secrets.yaml"
        yaml_path.write_text("plain_key: plain_value\n")

        vault = make_local_vault(tmp_path, encryption_key=fernet_key)
        assert vault.retrieve_secret("plain_key") == "plain_value"
