# AWS Credentials
from .aws_config import (
    CredConfig as AWSCredConfig,
    CredConfigAssumeRole,
    CredConfigAuto as AWSCredConfigAuto,
    CredConfigProfile,
    CredConfigStaticKeys,
    CredConfigWebIdentity,
)
from .aws_provider import CredProvider as AWSCredProvider

# Azure Credentials
from .azure_config import (
    CredConfig as AzureCredConfig,
    CredConfigAPIKey,
    CredConfigAuto as AzureCredConfigAuto,
    CredConfigManagedIdentity,
    CredConfigServicePrincipalCertificate,
    CredConfigServicePrincipalSecret,
    CredConfigWorkloadIdentity,
)
from .azure_provider import AzureCred, CredProvider as AzureCredProvider

# GCP Credentials
from .gcp_config import (
    CredConfig as GCPCredConfig,
    CredConfigAuto as GCPCredConfigAuto,
    CredConfigServiceAccount,
    CredConfigWorkloadIdentity as GCPCredConfigWorkloadIdentity,
)
from .gcp_provider import CredProvider as GCPCredProvider

__all__ = [
    # AWS
    "AWSCredConfig",
    "AWSCredConfigAuto",
    "CredConfigAssumeRole",
    "CredConfigProfile",
    "CredConfigStaticKeys",
    "CredConfigWebIdentity",
    "AWSCredProvider",
    # Azure
    "AzureCred",
    "AzureCredConfig",
    "CredConfigAPIKey",
    "AzureCredConfigAuto",
    "CredConfigManagedIdentity",
    "CredConfigServicePrincipalCertificate",
    "CredConfigServicePrincipalSecret",
    "CredConfigWorkloadIdentity",
    "AzureCredProvider",
    # GCP
    "GCPCredConfig",
    "GCPCredConfigAuto",
    "CredConfigServiceAccount",
    "GCPCredConfigWorkloadIdentity",
    "GCPCredProvider",
]
