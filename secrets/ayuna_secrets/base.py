from abc import ABC, abstractmethod
from typing import Annotated, Literal, Union

from ayuna_core.basetypes import AyunaError, CoreData, NonEmptyStr
from ayuna_creds.aws_config import CredConfig as AwsCredConfig
from ayuna_creds.azure_config import CredConfig as AzureCredConfig
from ayuna_creds.azure_config import CredConfigAuto as AzureCredConfigAuto
from ayuna_creds.gcp_config import CredConfig as GcpCredConfig
from pydantic import Field


class LocalSecretsConfig(CoreData):
    typid: Literal["local"] = "local"
    yaml_file_path: NonEmptyStr
    encryption_key: str | None = None
    encrypt_values_only: bool = True


class AzureSecretsConfig(CoreData):
    typid: Literal["azure"] = "azure"
    vault_url: NonEmptyStr
    cred_config: AzureCredConfig = Field(
        default_factory=AzureCredConfigAuto,
        description="Azure credential configuration. Defaults to automatic credential resolution.",
    )


class AWSSecretsConfig(CoreData):
    typid: Literal["aws"] = "aws"
    secret_id: NonEmptyStr
    cred_config: AwsCredConfig


class GCPSecretsConfig(CoreData):
    typid: Literal["gcp"] = "gcp"
    project_id: NonEmptyStr
    secret_id: NonEmptyStr
    cred_config: GcpCredConfig


SecretsConfig = Annotated[
    Union[
        LocalSecretsConfig,
        AzureSecretsConfig,
        AWSSecretsConfig,
        GCPSecretsConfig,
    ],
    Field(discriminator="typid"),
]


class SecretsError(AyunaError):
    pass


class SecretNotFoundError(SecretsError):
    pass


class SecretAlreadyExistsError(SecretsError):
    pass


class BaseSecrets(ABC):
    def __init__(self, config: SecretsConfig):
        self._vault_type = config.typid

    @property
    def vault_type(self) -> str:
        return self._vault_type

    @abstractmethod
    def retrieve_secret(self, key: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def store_secret(self, *, key: str, value: str, replace: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_secret(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_secrets(self) -> list[str]:
        raise NotImplementedError

    @classmethod
    def create(cls, config: SecretsConfig) -> "BaseSecrets":
        from .local import LocalSecrets
        from .aws import AWSSecrets
        from .azure import AzureSecrets
        from .gcp import GCPSecrets

        vault_map = {
            "local": LocalSecrets,
            "aws": AWSSecrets,
            "azure": AzureSecrets,
            "gcp": GCPSecrets,
        }

        vault_class = vault_map.get(config.typid)
        if vault_class is None:
            raise SecretsError(f"Unknown vault type: {config.typid}")

        return vault_class(config=config)
