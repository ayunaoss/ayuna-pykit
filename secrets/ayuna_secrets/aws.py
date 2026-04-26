import logging

import orjson
from ayuna_creds.aws_provider import CredProvider
from botocore.exceptions import ClientError

from .base import (
    AWSSecretsConfig,
    BaseSecrets,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    SecretsError,
)


class AWSSecrets(BaseSecrets):
    __logger = logging.getLogger(__name__)

    def __init__(self, *, config: AWSSecretsConfig) -> None:
        super().__init__(config)

        cred_provider = CredProvider(config=config.cred_config)
        session = cred_provider.resolve_session()

        self._secret_id = config.secret_id
        self._client = session.client(
            "secretsmanager", region_name=config.cred_config.region
        )
        self._secrets_cache: dict | None = None

    def _get_all_secrets(self) -> dict:
        if self._secrets_cache is not None:
            return self._secrets_cache

        try:
            response = self._client.get_secret_value(SecretId=self._secret_id)
            secret_string = response.get("SecretString", "{}")
            secrets = orjson.loads(secret_string)
            if not isinstance(secrets, dict):
                raise SecretsError(
                    f"AWS secret '{self._secret_id}' is not a valid JSON object"
                )
            self._secrets_cache = secrets
            return self._secrets_cache
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "ResourceNotFoundException":
                raise SecretNotFoundError(
                    f"AWS secret '{self._secret_id}' not found"
                ) from e
            elif error_code == "AccessDeniedException":
                raise SecretsError(
                    f"Access denied to AWS secret '{self._secret_id}'"
                ) from e
            else:
                raise SecretsError(f"AWS API error ({error_code}): {str(e)}") from e
        except orjson.JSONDecodeError as e:
            raise SecretsError(f"Failed to parse AWS secret JSON: {str(e)}") from e

    def _update_secret(self, secrets: dict) -> None:
        try:
            updated_secret = orjson.dumps(secrets).decode("utf-8")
            self._client.update_secret(
                SecretId=self._secret_id, SecretString=updated_secret
            )
            self._secrets_cache = secrets
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            raise SecretsError(
                f"Failed to update AWS secret ({error_code}): {str(e)}"
            ) from e

    def retrieve_secret(self, key: str) -> str | None:
        secrets = self._get_all_secrets()

        if key in secrets:
            return secrets[key]

        self.__logger.warning(f"Secret '{key}' not found in AWS Secrets Manager.")
        return None

    def store_secret(self, *, key: str, value: str, replace: bool = False) -> None:
        secrets = self._get_all_secrets()

        if not replace and key in secrets:
            raise SecretAlreadyExistsError(
                f"Secret '{key}' already exists in AWS Secrets Manager. "
                "Use replace=True to overwrite."
            )

        secrets[key] = value
        self._update_secret(secrets)

    def delete_secret(self, key: str) -> None:
        secrets = self._get_all_secrets()

        if key not in secrets:
            raise SecretNotFoundError(
                f"Secret '{key}' not found in AWS Secrets Manager."
            )

        del secrets[key]
        self._update_secret(secrets)

    def list_secrets(self) -> list[str]:
        secrets = self._get_all_secrets()
        return list(secrets.keys())
