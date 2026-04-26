import base64
import logging
import os
from pathlib import Path

import yaml
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .base import (
    BaseSecrets,
    LocalSecretsConfig,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    SecretsError,
)

# Reserved YAML key used to persist the PBKDF2 salt alongside encrypted secrets.
# This key is never exposed via list_secrets() or retrieve_secret().
_SALT_KEY = "_salt"


class LocalSecrets(BaseSecrets):
    __logger = logging.getLogger(__name__)

    def __init__(self, *, config: LocalSecretsConfig):
        super().__init__(config)
        self._yaml_file_path = Path(config.yaml_file_path)
        self._encrypt_values_only = config.encrypt_values_only
        self._raw_encryption_key = config.encryption_key
        self._fernet: Fernet | None = None
        self._pbkdf2_salt: bytes | None = None

        self._secrets = self._load_secrets()

    def _create_fernet(self, key: str, salt: bytes | None = None) -> Fernet:
        """Create a Fernet cipher from a key string.

        If the key is a raw Fernet key (44-char URL-safe base64 ending with '='),
        it is used directly.  Otherwise, PBKDF2-SHA256 is used to derive a key
        from the password, using *salt* if provided or a freshly generated salt.
        The salt used is stored in ``self._pbkdf2_salt`` for later persistence.
        """
        if len(key) == 44 and key.endswith("="):
            try:
                return Fernet(key.encode())
            except Exception:
                pass

        # Password-based key derivation — use provided salt or generate a new one
        if salt is None:
            salt = os.urandom(16)
        self._pbkdf2_salt = salt

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key_bytes = kdf.derive(key.encode())
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)

    def _encrypt(self, value: str) -> str:
        if not self._fernet:
            return value
        return self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        if not self._fernet:
            return value
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as e:
            raise SecretsError("Failed to decrypt secret value", exc_cause=e)

    def _load_secrets(self) -> dict:
        if not self._yaml_file_path.exists():
            # New vault — initialise Fernet now (generates fresh salt if needed)
            if self._raw_encryption_key:
                self._fernet = self._create_fernet(self._raw_encryption_key)
            return {}

        try:
            with open(self._yaml_file_path, "r") as file:
                data = yaml.safe_load(file) or {}
        except yaml.YAMLError as e:
            raise SecretsError(
                f"Failed to parse YAML file: {self._yaml_file_path}",
                exc_cause=e,
            )
        except OSError as e:
            raise SecretsError(
                f"Failed to read secrets file: {self._yaml_file_path}",
                exc_cause=e,
            )

        # Extract persisted PBKDF2 salt before processing secrets
        stored_salt: bytes | None = None
        if _SALT_KEY in data:
            try:
                stored_salt = base64.urlsafe_b64decode(data.pop(_SALT_KEY))
            except Exception:
                pass

        # Initialise Fernet using the stored salt so the same password can decrypt
        if self._raw_encryption_key:
            self._fernet = self._create_fernet(self._raw_encryption_key, stored_salt)

        if not self._fernet or not self._encrypt_values_only:
            return data

        decrypted = {}
        for k, v in data.items():
            if isinstance(v, str) and v.startswith("ENC:"):
                decrypted[k] = self._decrypt(v[4:])
            elif isinstance(v, str):
                decrypted[k] = v
            else:
                decrypted[k] = v

        return decrypted

    def _save_secrets(self) -> None:
        data_to_save = self._secrets.copy()

        if self._fernet and self._encrypt_values_only:
            for k, v in data_to_save.items():
                if isinstance(v, str):
                    data_to_save[k] = f"ENC:{self._encrypt(v)}"

        # Persist PBKDF2 salt so future vault instances can derive the same key
        if self._pbkdf2_salt is not None:
            data_to_save[_SALT_KEY] = base64.urlsafe_b64encode(
                self._pbkdf2_salt
            ).decode()

        try:
            self._yaml_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._yaml_file_path, "w") as file:
                yaml.dump(data_to_save, file, default_flow_style=False, sort_keys=True)
        except OSError as e:
            raise SecretsError(
                f"Failed to write secrets file: {self._yaml_file_path}",
                exc_cause=e,
            )

    def retrieve_secret(self, key: str) -> str | None:
        if key in self._secrets:
            return self._secrets[key]

        self.__logger.warning(f"Secret '{key}' not found in local vault.")
        return None

    def store_secret(self, *, key: str, value: str, replace: bool = False) -> None:
        if not replace and key in self._secrets:
            raise SecretAlreadyExistsError(
                f"Secret '{key}' already exists in local vault. "
                "Use replace=True to overwrite."
            )

        self._secrets[key] = value
        self._save_secrets()

    def delete_secret(self, key: str) -> None:
        if key not in self._secrets:
            raise SecretNotFoundError(f"Secret '{key}' not found in local vault.")

        del self._secrets[key]
        self._save_secrets()

    def list_secrets(self) -> list[str]:
        return list(self._secrets.keys())
