from typing import Annotated, Literal, Union

from ayuna_core.basetypes import CoreData, NonEmptyStr
from pydantic import Field, SecretStr

CredMethodType = Literal[
    "auto",
    "api_key",
    "workload_identity",
    "managed_identity",
    "service_principal_secret",
    "service_principal_certificate",
]

_TENANT_ID_DESC = "The Azure Active Directory tenant ID."
_CLIENT_ID_DESC = "The client ID of the Azure AD application."


class CredConfigAuto(CoreData):
    """
    Configuration for automatic Azure authentication using default credentials.
    """

    typid: Literal["auto"] = "auto"


class CredConfigAPIKey(CoreData):
    """
    Configuration for Azure authentication using API Key.
    """

    typid: Literal["api_key"] = "api_key"
    api_key: SecretStr = Field(
        ...,
        description="The API key for Azure authentication.",
    )


class CredConfigWorkloadIdentity(CoreData):
    """
    Configuration for Azure authentication using Workload Identity.
    """

    typid: Literal["workload_identity"] = "workload_identity"
    tenant_id: NonEmptyStr = Field(
        ...,
        description=_TENANT_ID_DESC,
    )
    client_id: NonEmptyStr = Field(
        ...,
        description=_CLIENT_ID_DESC,
    )
    federated_token_file: NonEmptyStr = Field(
        ...,
        description="The file path to the federated token.",
    )
    authority_host: NonEmptyStr = Field(
        "https://login.microsoftonline.com",
        description="The authority host for the token request.",
    )


class CredConfigManagedIdentity(CoreData):
    """
    Configuration for Azure authentication using Managed Identity.
    """

    typid: Literal["managed_identity"] = "managed_identity"
    client_id: NonEmptyStr | None = Field(
        None,
        description="The client ID of the user-assigned managed identity. If not provided, the system-assigned identity will be used.",
    )


class CredConfigServicePrincipalSecret(CoreData):
    """
    Configuration for Azure authentication using Service Principal with Client Secret.
    """

    typid: Literal["service_principal_secret"] = "service_principal_secret"
    tenant_id: NonEmptyStr = Field(
        ...,
        description=_TENANT_ID_DESC,
    )
    client_id: NonEmptyStr = Field(
        ...,
        description=_CLIENT_ID_DESC,
    )
    client_secret: SecretStr = Field(
        ...,
        description="The client secret of the Azure AD application.",
    )
    authority: NonEmptyStr | None = Field(
        None,
        description="The authority URL for Azure AD (e.g., 'https://login.microsoftonline.com' for public cloud, 'https://login.chinacloudapi.cn' for China cloud).",
    )


class CredConfigServicePrincipalCertificate(CoreData):
    """
    Configuration for Azure authentication using Service Principal with Client Certificate.
    """

    typid: Literal["service_principal_certificate"] = "service_principal_certificate"
    tenant_id: NonEmptyStr = Field(
        ...,
        description=_TENANT_ID_DESC,
    )
    client_id: NonEmptyStr = Field(
        ...,
        description=_CLIENT_ID_DESC,
    )
    certificate_path: NonEmptyStr = Field(
        ...,
        description="The file path to the client certificate.",
    )
    certificate_password: SecretStr | None = Field(
        None,
        description="The password for the client certificate, if applicable.",
    )
    authority: NonEmptyStr | None = Field(
        None,
        description="The authority URL for Azure AD (e.g., 'https://login.microsoftonline.com' for public cloud, 'https://login.chinacloudapi.cn' for China cloud).",
    )


CredConfig = Annotated[
    Union[
        CredConfigAuto,
        CredConfigAPIKey,
        CredConfigWorkloadIdentity,
        CredConfigManagedIdentity,
        CredConfigServicePrincipalSecret,
        CredConfigServicePrincipalCertificate,
    ],
    Field(discriminator="typid"),
]
