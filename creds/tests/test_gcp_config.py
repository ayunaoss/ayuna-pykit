"""Tests for GCP credential configuration models."""

import pytest
from pydantic import ValidationError

from ayuna_creds.gcp_config import (
    CredConfigAuto,
    CredConfigServiceAccount,
    CredConfigWorkloadIdentity,
)


class TestCredConfigAuto:
    """Tests for automatic GCP credential configuration."""

    def test_default_values(self):
        """Test that auto config has correct default values."""
        config = CredConfigAuto()
        assert config.typid == "auto"


class TestCredConfigServiceAccount:
    """Tests for GCP Service Account credential configuration."""

    def test_valid_service_account(self):
        """Test service account config with valid key file path."""
        config = CredConfigServiceAccount(
            key_file_path="/path/to/service-account-key.json"
        )
        assert config.typid == "service_account"
        assert config.key_file_path == "/path/to/service-account-key.json"
        assert config.scopes is None

    def test_service_account_with_scopes(self):
        """Test service account config with OAuth scopes."""
        config = CredConfigServiceAccount(
            key_file_path="/path/to/service-account-key.json",
            scopes=[
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/bigquery",
            ],
        )
        assert config.scopes == [
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/bigquery",
        ]

    def test_empty_key_file_path(self):
        """Test that empty key file path raises validation error."""
        with pytest.raises(ValidationError):
            CredConfigServiceAccount(key_file_path="")


class TestCredConfigWorkloadIdentity:
    """Tests for GCP Workload Identity Federation configuration."""

    def test_valid_workload_identity(self):
        """Test workload identity config with required fields."""
        config = CredConfigWorkloadIdentity(
            file_path="/path/to/workload-identity-config.json",
            account_id="my-service-account@my-project.iam.gserviceaccount.com",
        )
        assert config.typid == "workload_identity"
        assert config.file_path == "/path/to/workload-identity-config.json"
        assert (
            config.account_id == "my-service-account@my-project.iam.gserviceaccount.com"
        )

    def test_empty_file_path(self):
        """Test that empty file path raises validation error."""
        with pytest.raises(ValidationError):
            CredConfigWorkloadIdentity(
                file_path="",
                account_id="my-service-account@my-project.iam.gserviceaccount.com",
            )

    def test_empty_account_id(self):
        """Test that empty account ID raises validation error."""
        with pytest.raises(ValidationError):
            CredConfigWorkloadIdentity(
                file_path="/path/to/config.json",
                account_id="",
            )
