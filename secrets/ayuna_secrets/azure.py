import logging
from typing import NoReturn, cast

from azure.core.credentials import TokenCredential
from azure.core.exceptions import (
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.keyvault.secrets import SecretClient
from ayuna_creds.azure_provider import CredProvider as AzureCredProvider

from .base import (
    AzureSecretsConfig,
    BaseSecrets,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    SecretsError,
)


class AzureSecrets(BaseSecrets):
    __logger = logging.getLogger(__name__)

    def __init__(self, *, config: AzureSecretsConfig) -> None:
        super().__init__(config)

        if config.cred_config.typid == "api_key":
            raise ValueError(
                "Azure Key Vault does not support API Key credentials. "
                "Use auto, managed_identity, service_principal_secret, "
                "service_principal_certificate, or workload_identity."
            )

        cred_provider = AzureCredProvider(config=config.cred_config)
        credential = cast(
            TokenCredential, cred_provider.resolve_credential(async_mode=False)
        )

        self._vault_url = config.vault_url
        self._client = SecretClient(vault_url=self._vault_url, credential=credential)

    def _handle_azure_error(
        self, e: Exception, operation: str, key: str | None = None
    ) -> NoReturn:
        if isinstance(e, ResourceNotFoundError):
            raise SecretNotFoundError(
                f"Secret '{key}' not found in Azure Key Vault."
            ) from e
        elif isinstance(e, HttpResponseError):
            raise SecretsError(
                f"Azure API error during {operation}: {e.message}"
            ) from e
        elif isinstance(e, ServiceRequestError):
            raise SecretsError(
                f"Network error connecting to Azure Key Vault: {str(e)}"
            ) from e
        else:
            raise SecretsError(f"Unexpected error during {operation}: {str(e)}") from e

    def retrieve_secret(self, key: str) -> str | None:
        try:
            secret = self._client.get_secret(key)
            return secret.value if secret and secret.value else None
        except ResourceNotFoundError:
            self.__logger.warning(f"Secret '{key}' not found in Azure Key Vault.")
            return None
        except Exception as e:
            self._handle_azure_error(e, "retrieve", key)

    def store_secret(self, *, key: str, value: str, replace: bool = False) -> None:
        if not replace:
            try:
                existing = self._client.get_secret(key)
                if existing and existing.value:
                    raise SecretAlreadyExistsError(
                        f"Secret '{key}' already exists in Azure Key Vault. "
                        "Use replace=True to overwrite."
                    )
            except ResourceNotFoundError:
                pass
            except SecretAlreadyExistsError:
                raise
            except Exception as e:
                self._handle_azure_error(e, "check existing", key)

        try:
            self._client.set_secret(key, value)
        except Exception as e:
            self._handle_azure_error(e, "store", key)

    def delete_secret(self, key: str) -> None:
        try:
            self._client.get_secret(key)
        except ResourceNotFoundError:
            raise SecretNotFoundError(f"Secret '{key}' not found in Azure Key Vault.")
        except Exception as e:
            self._handle_azure_error(e, "check before delete", key)

        try:
            self._client.begin_delete_secret(key).wait(30)
        except HttpResponseError as e:
            if e.status_code == 409:
                raise SecretsError(
                    f"Secret '{key}' is already in deleted state or being recovered."
                ) from e
            raise SecretsError(f"Failed to delete secret '{key}': {e.message}") from e
        except Exception as e:
            self._handle_azure_error(e, "delete", key)

    def list_secrets(self) -> list[str]:
        try:
            names: list[str] = []
            for secret in self._client.list_properties_of_secrets():
                if secret.name:
                    names.append(secret.name)
            return names
        except Exception as e:
            self._handle_azure_error(e, "list secrets")
