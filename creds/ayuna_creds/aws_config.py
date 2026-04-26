from typing import Annotated, Literal, Union

from ayuna_core.basetypes import CoreData, NonEmptyStr
from pydantic import Field, SecretStr

CredMethodType = Literal[
    "auto",
    "profile",
    "assume_role",
    "web_identity",
    "static_keys",
]


class _CredConfigBase(CoreData):
    region: NonEmptyStr | None = Field(
        None,
        description="The AWS region to use. If not provided, the default region will be used.",
    )
    allowed_account_ids: list[NonEmptyStr] | None = Field(
        None,
        description="List of allowed AWS account IDs for security enforcement.",
    )
    allowed_role_arns: list[NonEmptyStr] | None = Field(
        None,
        description="List of allowed AWS role ARNs for security enforcement.",
    )


class CredConfigAuto(_CredConfigBase):
    """
    Configuration for automatic AWS authentication.
    """

    typid: Literal["auto"] = "auto"


class CredConfigProfile(_CredConfigBase):
    """
    Configuration for AWS authentication using a named profile.
    """

    typid: Literal["profile"] = "profile"
    profile_name: NonEmptyStr = Field(
        ...,
        description="The name of the AWS profile to use for authentication.",
    )


class CredConfigAssumeRole(_CredConfigBase):
    """
    Configuration for AWS authentication using Assume Role.
    """

    typid: Literal["assume_role"] = "assume_role"
    role_arn: NonEmptyStr = Field(
        ...,
        description="The Amazon Resource Name (ARN) of the role to assume.",
    )
    session_name: NonEmptyStr = Field(
        ...,
        description="An identifier for the assumed role session.",
    )
    external_id: NonEmptyStr | None = Field(
        None,
        description="A unique identifier that might be required when you assume a role in another account (optional).",
    )
    duration_seconds: int = Field(
        3600,
        ge=900,
        le=43200,
        description="The duration, in seconds, of the role session. Minimum 900 seconds (15 min), maximum 43200 seconds (12 hours).",
    )


class CredConfigWebIdentity(_CredConfigBase):
    """
    Configuration for AWS authentication using Web Identity Federation.
    """

    typid: Literal["web_identity"] = "web_identity"
    role_arn: NonEmptyStr = Field(
        ...,
        description="The Amazon Resource Name (ARN) of the role to assume.",
    )
    federated_token_file: NonEmptyStr = Field(
        ...,
        description="The file path to the web identity token.",
    )
    session_name: NonEmptyStr = Field(
        ...,
        description="An identifier for the assumed role session.",
    )
    duration_seconds: int = Field(
        3600,
        ge=900,
        le=43200,
        description="The duration, in seconds, of the role session. Should be within the limit set by the administrator.",
    )


class CredConfigStaticKeys(_CredConfigBase):
    """
    Configuration for AWS authentication using static access keys.
    """

    typid: Literal["static_keys"] = "static_keys"
    access_key_id: SecretStr = Field(
        ...,
        description="The AWS access key ID.",
    )
    secret_access_key: SecretStr = Field(
        ...,
        description="The AWS secret access key.",
    )
    session_token: SecretStr | None = Field(
        None,
        description="The AWS session token, if using temporary credentials.",
    )


CredConfig = Annotated[
    Union[
        CredConfigAuto,
        CredConfigProfile,
        CredConfigAssumeRole,
        CredConfigWebIdentity,
        CredConfigStaticKeys,
    ],
    Field(discriminator="typid"),
]
