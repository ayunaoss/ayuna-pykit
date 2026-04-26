from typing import Annotated, Literal, Union

from ayuna_core.basetypes import CoreData, NonEmptyStr
from pydantic import Field

CredMethodType = Literal[
    "auto",
    "workload_identity",
    "service_account",
]


class CredConfigAuto(CoreData):
    """
    Configuration for automatic GCP authentication.
    """

    typid: Literal["auto"] = "auto"


class CredConfigWorkloadIdentity(CoreData):
    """
    Configuration for GCP authentication using Workload Identity Federation with a local file.
    """

    typid: Literal["workload_identity"] = "workload_identity"
    file_path: NonEmptyStr = Field(
        ...,
        description="The file path to the Workload Identity Federation configuration file.",
    )
    account_id: NonEmptyStr = Field(
        ...,
        description="The GCP service account email associated with the Workload Identity Federation.",
    )


class CredConfigServiceAccount(CoreData):
    """
    Configuration for GCP authentication using a Service Account key file.
    """

    typid: Literal["service_account"] = "service_account"
    key_file_path: NonEmptyStr = Field(
        ...,
        description="The file path to the service account key JSON file.",
    )
    scopes: list[NonEmptyStr] | None = Field(
        None,
        description="OAuth2 scopes to request (e.g., ['https://www.googleapis.com/auth/cloud-platform']).",
    )


CredConfig = Annotated[
    Union[
        CredConfigAuto,
        CredConfigWorkloadIdentity,
        CredConfigServiceAccount,
    ],
    Field(discriminator="typid"),
]
