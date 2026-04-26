import logging

import orjson
from ayuna_creds.gcp_provider import CredProvider
from google.api_core.exceptions import GoogleAPICallError, NotFound, PermissionDenied
from google.cloud import secretmanager

from .base import (
    BaseSecrets,
    GCPSecretsConfig,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    SecretsError,
)


class GCPSecrets(BaseSecrets):
    __logger = logging.getLogger(__name__)

    def __init__(self, *, config: GCPSecretsConfig) -> None:
        super().__init__(config)

        cred_provider = CredProvider(config=config.cred_config)
        credentials = cred_provider.resolve_credentials()

        self._project_id = config.project_id
        self._secret_id = config.secret_id
        self._client = secretmanager.SecretManagerServiceClient(credentials=credentials)
        self._parent = f"projects/{self._project_id}/secrets/{self._secret_id}"
        self._secrets_cache: dict | None = None

    def _get_secret_name(self) -> str:
        return f"{self._parent}/versions/latest"

    def _get_all_secrets(self) -> dict:
        if self._secrets_cache is not None:
            return self._secrets_cache

        name = self._get_secret_name()

        try:
            request = secretmanager.AccessSecretVersionRequest(name=name)
            response = self._client.access_secret_version(request=request)
            data = orjson.loads(response.payload.data)

            if not isinstance(data, dict):
                raise SecretsError(
                    f"GCP secret '{self._secret_id}' is not a valid JSON object"
                )

            self._secrets_cache = data
            return self._secrets_cache
        except NotFound as e:
            raise SecretNotFoundError(
                f"GCP secret '{self._secret_id}' not found"
            ) from e
        except PermissionDenied as e:
            raise SecretsError(
                f"Access denied to GCP secret '{self._secret_id}'"
            ) from e
        except GoogleAPICallError as e:
            raise SecretsError(f"GCP API error: {e.message}") from e
        except orjson.JSONDecodeError as e:
            raise SecretsError(f"Failed to parse GCP secret JSON: {str(e)}") from e

    def _add_secret_version(self, data: dict) -> None:
        try:
            updated_payload = orjson.dumps(data)
            payload = secretmanager.SecretPayload(data=updated_payload)
            add_req = secretmanager.AddSecretVersionRequest(
                parent=self._parent, payload=payload
            )
            self._client.add_secret_version(request=add_req)
            self._secrets_cache = data
        except GoogleAPICallError as e:
            raise SecretsError(f"Failed to add GCP secret version: {e.message}") from e

    def retrieve_secret(self, key: str) -> str | None:
        secrets = self._get_all_secrets()

        if key in secrets:
            return secrets[key]

        self.__logger.warning(f"Secret '{key}' not found in GCP Secret Manager.")
        return None

    def store_secret(self, *, key: str, value: str, replace: bool = False) -> None:
        secrets = self._get_all_secrets()

        if not replace and key in secrets:
            raise SecretAlreadyExistsError(
                f"Secret '{key}' already exists in GCP Secret Manager. "
                "Use replace=True to overwrite."
            )

        secrets[key] = value
        self._add_secret_version(secrets)

    def delete_secret(self, key: str) -> None:
        secrets = self._get_all_secrets()

        if key not in secrets:
            raise SecretNotFoundError(
                f"Secret '{key}' not found in GCP Secret Manager."
            )

        del secrets[key]
        self._add_secret_version(secrets)

    def list_secrets(self) -> list[str]:
        secrets = self._get_all_secrets()
        return list(secrets.keys())
