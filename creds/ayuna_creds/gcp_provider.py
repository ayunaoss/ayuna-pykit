import logging
from typing import Callable, Dict

import google.auth.transport.requests
import orjson
from google.auth import default, identity_pool
from google.auth.credentials import Credentials
from google.auth.impersonated_credentials import Credentials as ImpersonatedCredentials
from google.oauth2 import service_account

from .gcp_config import CredConfig, CredMethodType


class CredProvider:
    __logger = logging.getLogger(__name__)

    def __init__(self, config: CredConfig):
        self._config = config

    def _resolve_auto(self) -> Credentials:
        self.__logger.debug("Resolving GCP Application Default credentials")
        credentials, _ = default()
        if not isinstance(credentials, Credentials):
            raise TypeError("Failed to obtain default credentials.")

        return credentials

    def _resolve_workload_identity(self) -> Credentials:
        self.__logger.debug("Resolving GCP Workload Identity File credentials")
        if self._config.typid != "workload_identity":
            raise ValueError("Workload Identity File method must be selected.")

        request = google.auth.transport.requests.Request()

        credentials = identity_pool.Credentials.from_file(self._config.file_path)
        credentials.refresh(request)

        return credentials

    def _resolve_service_account(self) -> Credentials:
        self.__logger.debug("Resolving GCP Service Account credentials")
        if self._config.typid != "service_account":
            raise ValueError("Service Account method must be selected.")

        with open(self._config.key_file_path, "r") as f:
            key_data = orjson.loads(f.read())

        scopes = self._config.scopes or [
            "https://www.googleapis.com/auth/cloud-platform"
        ]
        credentials = service_account.Credentials.from_service_account_info(
            key_data, scopes=scopes
        )

        return credentials

    def resolve_credentials(self) -> Credentials:
        mapping: Dict[CredMethodType, Callable] = {
            "auto": self._resolve_auto,
            "workload_identity": self._resolve_workload_identity,
            "service_account": self._resolve_service_account,
        }

        method = self._config.typid

        if method not in mapping:
            raise ValueError(f"Unsupported GCP credential method: {method}")

        return mapping[method]()

    def resolve_impersonated_credentials(
        self,
        *,
        source_credentials: Credentials,
        target_principal: str,
        target_scopes: list[str] = ["https://www.googleapis.com/auth/cloud-platform"],
        lifetime: int = 3600,
    ) -> ImpersonatedCredentials:
        self.__logger.debug("Resolving GCP Impersonated credentials")

        impersonated_credentials = ImpersonatedCredentials(
            source_credentials=source_credentials,
            target_principal=target_principal,
            target_scopes=target_scopes,
            lifetime=lifetime,
        )

        return impersonated_credentials
