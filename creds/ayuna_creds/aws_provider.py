import logging
import os
from typing import Callable, Dict

import boto3

from .aws_config import CredConfig, CredMethodType


class CredProvider:
    __logger = logging.getLogger(__name__)

    def __init__(self, config: CredConfig):
        self._config = config

    def _resolve_auto(self) -> boto3.Session:
        self.__logger.debug("Using automatic AWS authentication method resolution.")
        session = boto3.Session(region_name=self._config.region)

        return session

    def _resolve_profile(self) -> boto3.Session:
        self.__logger.debug("Using AWS profile for authentication.")
        if self._config.typid != "profile":
            raise ValueError("Invalid method for profile resolution.")

        session = boto3.Session(
            profile_name=self._config.profile_name,
            region_name=self._config.region,
        )

        return session

    def _resolve_assume_role(self) -> boto3.Session:
        self.__logger.debug("Using Assume Role for AWS authentication.")
        if self._config.typid != "assume_role":
            raise ValueError("Invalid method for assume role resolution.")

        sts_client = boto3.client("sts", region_name=self._config.region)

        assume_kwargs = {
            "RoleArn": self._config.role_arn,
            "RoleSessionName": self._config.session_name,
            "DurationSeconds": self._config.duration_seconds,
        }

        if self._config.external_id:
            assume_kwargs["ExternalId"] = self._config.external_id

        response = sts_client.assume_role(**assume_kwargs)

        credentials = response["Credentials"]
        session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name=self._config.region,
        )

        return session

    def _resolve_web_identity(self) -> boto3.Session:
        self.__logger.debug("Using Web Identity Federation for AWS authentication.")
        if self._config.typid != "web_identity":
            raise ValueError("Invalid method for web identity resolution.")

        if not os.path.exists(self._config.federated_token_file):
            raise FileNotFoundError(
                f"Web identity token file not found: {self._config.federated_token_file}"
            )

        with open(self._config.federated_token_file, "r") as f:
            web_identity_token = f.read().strip()

        sts_client = boto3.client("sts", region_name=self._config.region)

        assume_kwargs = {
            "RoleArn": self._config.role_arn,
            "RoleSessionName": self._config.session_name,
            "WebIdentityToken": web_identity_token,
            "DurationSeconds": self._config.duration_seconds,
        }

        response = sts_client.assume_role_with_web_identity(**assume_kwargs)

        credentials = response["Credentials"]
        session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name=self._config.region,
        )

        return session

    def _resolve_static_keys(self) -> boto3.Session:
        self.__logger.debug("Using static AWS access keys for authentication.")
        if self._config.typid != "static_keys":
            raise ValueError("Invalid method for static keys resolution.")

        session = boto3.Session(
            aws_access_key_id=self._config.access_key_id.get_secret_value(),
            aws_secret_access_key=self._config.secret_access_key.get_secret_value(),
            aws_session_token=self._config.session_token.get_secret_value()
            if self._config.session_token
            else None,
            region_name=self._config.region,
        )

        return session

    def _enforce_security(self, session: boto3.Session) -> None:
        if not self._config.allowed_account_ids and not self._config.allowed_role_arns:
            return

        sts_client = session.client("sts")
        identity = sts_client.get_caller_identity()
        account_id = identity.get("Account")
        role_arn = identity.get("Arn")

        if (
            self._config.allowed_account_ids
            and account_id not in self._config.allowed_account_ids
        ):
            raise PermissionError(
                f"Authenticated AWS account ID {account_id} is not in the list of allowed account IDs."
            )

        self.__logger.debug(f"AWS account ID {account_id} passed security enforcement.")

        if (
            self._config.allowed_role_arns
            and role_arn not in self._config.allowed_role_arns
        ):
            raise PermissionError(
                f"Authenticated AWS role ARN {role_arn} is not in the list of allowed role ARNs."
            )

        self.__logger.debug(f"AWS role ARN {role_arn} passed security enforcement.")

    ## NOTE: This the public method to be called to get boto3 session
    def resolve_session(self) -> boto3.Session:
        mapping: Dict[CredMethodType, Callable] = {
            "auto": self._resolve_auto,
            "profile": self._resolve_profile,
            "assume_role": self._resolve_assume_role,
            "web_identity": self._resolve_web_identity,
            "static_keys": self._resolve_static_keys,
        }

        method = self._config.typid

        if method not in mapping:
            raise ValueError(f"Unsupported AWS authentication method: {method}")

        session = mapping[method]()
        self._enforce_security(session)

        return session
