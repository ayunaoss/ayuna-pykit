import logging
from typing import Callable, Dict, Literal, TypeVar, overload

from azure.core.credentials import AzureKeyCredential
from azure.identity import (
    CertificateCredential as SyncCertificateCredential,
)
from azure.identity import (
    ClientSecretCredential as SyncClientSecretCredential,
)
from azure.identity import (
    DefaultAzureCredential as SyncDefaultAzureCredential,
)
from azure.identity import (
    ManagedIdentityCredential as SyncManagedIdentityCredential,
)
from azure.identity import (
    WorkloadIdentityCredential as SyncWorkloadIdentityCredential,
)
from azure.identity.aio import (
    CertificateCredential as AsyncCertificateCredential,
)
from azure.identity.aio import (
    ClientSecretCredential as AsyncClientSecretCredential,
)
from azure.identity.aio import (
    DefaultAzureCredential as AsyncDefaultAzureCredential,
)
from azure.identity.aio import (
    ManagedIdentityCredential as AsyncManagedIdentityCredential,
)
from azure.identity.aio import (
    WorkloadIdentityCredential as AsyncWorkloadIdentityCredential,
)

from .azure_config import CredConfig, CredMethodType

T = TypeVar("T")

AzureCred = (
    SyncDefaultAzureCredential
    | AzureKeyCredential
    | SyncManagedIdentityCredential
    | SyncClientSecretCredential
    | SyncCertificateCredential
    | SyncWorkloadIdentityCredential
)

AsyncAzureCred = (
    AsyncDefaultAzureCredential
    | AsyncManagedIdentityCredential
    | AsyncClientSecretCredential
    | AsyncCertificateCredential
    | AsyncWorkloadIdentityCredential
)


class CredProvider:
    __logger = logging.getLogger(__name__)

    def __init__(self, config: CredConfig):
        self._config = config

    def _resolve_api_key(self, async_mode: bool = False) -> AzureKeyCredential:
        self.__logger.debug("Using API Key for Azure authentication.")
        if self._config.typid != "api_key":
            raise ValueError(
                "Credential type must be 'api_key' for API Key resolution."
            )
        if async_mode:
            raise TypeError("API Key credential does not support async mode")

        credential = AzureKeyCredential(self._config.api_key.get_secret_value())

        return credential

    def _resolve_workload_identity(self, async_mode: bool = False):
        self.__logger.debug("Using Workload Identity for Azure authentication.")
        if self._config.typid != "workload_identity":
            raise ValueError(
                "Credential type must be 'workload_identity' for Workload Identity resolution."
            )

        credential_class = (
            AsyncWorkloadIdentityCredential
            if async_mode
            else SyncWorkloadIdentityCredential
        )

        credential = credential_class(
            tenant_id=self._config.tenant_id,
            client_id=self._config.client_id,
            token_file_path=self._config.federated_token_file,
        )

        return credential

    def _resolve_managed_identity(self, async_mode: bool = False):
        self.__logger.debug("Using Managed Identity for Azure authentication.")
        if self._config.typid != "managed_identity":
            raise ValueError(
                "Credential type must be 'managed_identity' for Managed Identity resolution."
            )

        credential_class = (
            AsyncManagedIdentityCredential
            if async_mode
            else SyncManagedIdentityCredential
        )

        if not self._config.client_id:
            self.__logger.debug("Creating System Assigned Managed Identity Credential.")
            return credential_class()

        self.__logger.debug("Creating User Assigned Managed Identity Credential.")
        return credential_class(client_id=self._config.client_id)

    def _resolve_service_principal_secret(self, async_mode: bool = False):
        self.__logger.debug(
            "Using Service Principal with Client Secret for Azure authentication."
        )
        if self._config.typid != "service_principal_secret":
            raise ValueError(
                "Credential type must be 'service_principal_secret' for Service Principal Secret resolution."
            )

        credential_class = (
            AsyncClientSecretCredential if async_mode else SyncClientSecretCredential
        )

        kwargs = {
            "tenant_id": self._config.tenant_id,
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret.get_secret_value(),
        }

        if self._config.authority:
            kwargs["authority"] = self._config.authority

        credential = credential_class(**kwargs)

        return credential

    def _resolve_service_principal_certificate(self, async_mode: bool = False):
        self.__logger.debug(
            "Using Service Principal with Client Certificate for Azure authentication."
        )
        if self._config.typid != "service_principal_certificate":
            raise ValueError(
                "Credential type must be 'service_principal_certificate' for Service Principal Certificate resolution."
            )

        credential_class = (
            AsyncCertificateCredential if async_mode else SyncCertificateCredential
        )

        kwargs = {
            "tenant_id": self._config.tenant_id,
            "client_id": self._config.client_id,
            "certificate_path": self._config.certificate_path,
        }

        if self._config.certificate_password:
            kwargs["password"] = self._config.certificate_password.get_secret_value()

        if self._config.authority:
            kwargs["authority"] = self._config.authority

        credential = credential_class(**kwargs)

        return credential

    def _resolve_auto(self, async_mode: bool = False):
        self.__logger.debug("Using Automatic Azure authentication resolution.")
        if self._config.typid != "auto":
            raise ValueError("Credential type must be 'auto' for auto resolution.")

        credential_class = (
            AsyncDefaultAzureCredential if async_mode else SyncDefaultAzureCredential
        )
        credential = credential_class()

        return credential

    ## NOTE: This is the public method to be called to get azure credential
    @overload
    def resolve_credential(self, async_mode: Literal[False] = False) -> AzureCred: ...

    @overload
    def resolve_credential(self, async_mode: Literal[True]) -> AsyncAzureCred: ...

    def resolve_credential(
        self, async_mode: bool = False
    ) -> AzureCred | AsyncAzureCred:
        mapping: Dict[CredMethodType, Callable] = {
            "auto": self._resolve_auto,
            "workload_identity": self._resolve_workload_identity,
            "managed_identity": self._resolve_managed_identity,
            "service_principal_secret": self._resolve_service_principal_secret,
            "service_principal_certificate": self._resolve_service_principal_certificate,
        }

        if not async_mode:
            mapping["api_key"] = self._resolve_api_key

        method = self._config.typid

        if method not in mapping:
            raise ValueError(f"Unsupported Azure credential method: {method}")

        return mapping[method](async_mode=async_mode)
