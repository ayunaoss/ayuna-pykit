"""Tests for AWS credential configuration models."""

import pytest
from pydantic import SecretStr, ValidationError

from ayuna_creds.aws_config import (
    CredConfigAssumeRole,
    CredConfigAuto,
    CredConfigProfile,
    CredConfigStaticKeys,
    CredConfigWebIdentity,
)


class TestCredConfigAuto:
    """Tests for automatic AWS credential configuration."""

    def test_default_values(self):
        """Test that auto config has correct default values."""
        config = CredConfigAuto()
        assert config.typid == "auto"
        assert config.region is None
        assert config.allowed_account_ids is None
        assert config.allowed_role_arns is None

    def test_with_region(self):
        """Test auto config with region specified."""
        config = CredConfigAuto(region="us-west-2")
        assert config.region == "us-west-2"

    def test_with_security_settings(self):
        """Test auto config with account/role restrictions."""
        config = CredConfigAuto(
            region="eu-west-1",
            allowed_account_ids=["123456789012"],
            allowed_role_arns=["arn:aws:iam::123456789012:role/MyRole"],
        )
        assert config.allowed_account_ids == ["123456789012"]
        assert config.allowed_role_arns == ["arn:aws:iam::123456789012:role/MyRole"]


class TestCredConfigProfile:
    """Tests for AWS profile-based credential configuration."""

    def test_valid_profile(self):
        """Test profile config with valid profile name."""
        config = CredConfigProfile(profile_name="my-profile")
        assert config.typid == "profile"
        assert config.profile_name == "my-profile"
        assert config.region is None

    def test_profile_with_region(self):
        """Test profile config with region."""
        config = CredConfigProfile(profile_name="prod-profile", region="us-east-1")
        assert config.region == "us-east-1"

    def test_empty_profile_name(self):
        """Test that empty profile name raises validation error."""
        with pytest.raises(ValidationError):
            CredConfigProfile(profile_name="")


class TestCredConfigAssumeRole:
    """Tests for AWS assume role credential configuration."""

    def test_valid_assume_role(self):
        """Test assume role config with required fields."""
        config = CredConfigAssumeRole(
            role_arn="arn:aws:iam::123456789012:role/MyRole",
            session_name="my-session",
        )
        assert config.typid == "assume_role"
        assert config.role_arn == "arn:aws:iam::123456789012:role/MyRole"
        assert config.session_name == "my-session"
        assert config.external_id is None
        assert config.duration_seconds == 3600

    def test_assume_role_with_external_id(self):
        """Test assume role config with external ID."""
        config = CredConfigAssumeRole(
            role_arn="arn:aws:iam::123456789012:role/MyRole",
            session_name="my-session",
            external_id="my-external-id",
            duration_seconds=7200,
        )
        assert config.external_id == "my-external-id"
        assert config.duration_seconds == 7200


class TestCredConfigWebIdentity:
    """Tests for AWS web identity federation configuration."""

    def test_valid_web_identity(self):
        """Test web identity config with required fields."""
        config = CredConfigWebIdentity(
            role_arn="arn:aws:iam::123456789012:role/MyRole",
            federated_token_file="/path/to/token",
            session_name="my-session",
        )
        assert config.typid == "web_identity"
        assert config.role_arn == "arn:aws:iam::123456789012:role/MyRole"
        assert config.federated_token_file == "/path/to/token"
        assert config.session_name == "my-session"
        assert config.duration_seconds == 3600


class TestCredConfigDurationSeconds:
    """Tests for duration_seconds validation on assume role and web identity configs."""

    def test_assume_role_duration_below_minimum(self):
        """Test that duration_seconds below 900 raises ValidationError."""
        with pytest.raises(ValidationError):
            CredConfigAssumeRole(
                role_arn="arn:aws:iam::123456789012:role/MyRole",
                session_name="my-session",
                duration_seconds=899,
            )

    def test_assume_role_duration_above_maximum(self):
        """Test that duration_seconds above 43200 raises ValidationError."""
        with pytest.raises(ValidationError):
            CredConfigAssumeRole(
                role_arn="arn:aws:iam::123456789012:role/MyRole",
                session_name="my-session",
                duration_seconds=43201,
            )

    def test_web_identity_duration_below_minimum(self):
        """Test that duration_seconds below 900 raises ValidationError."""
        with pytest.raises(ValidationError):
            CredConfigWebIdentity(
                role_arn="arn:aws:iam::123456789012:role/MyRole",
                federated_token_file="/path/to/token",
                session_name="my-session",
                duration_seconds=899,
            )

    def test_web_identity_duration_above_maximum(self):
        """Test that duration_seconds above 43200 raises ValidationError."""
        with pytest.raises(ValidationError):
            CredConfigWebIdentity(
                role_arn="arn:aws:iam::123456789012:role/MyRole",
                federated_token_file="/path/to/token",
                session_name="my-session",
                duration_seconds=43201,
            )

    def test_assume_role_duration_boundary_values(self):
        """Test that boundary values 900 and 43200 are accepted."""
        config_min = CredConfigAssumeRole(
            role_arn="arn:aws:iam::123456789012:role/MyRole",
            session_name="my-session",
            duration_seconds=900,
        )
        assert config_min.duration_seconds == 900

        config_max = CredConfigAssumeRole(
            role_arn="arn:aws:iam::123456789012:role/MyRole",
            session_name="my-session",
            duration_seconds=43200,
        )
        assert config_max.duration_seconds == 43200


class TestCredConfigStaticKeys:
    """Tests for AWS static access key configuration."""

    def test_valid_static_keys(self):
        """Test static keys config with credentials."""
        config = CredConfigStaticKeys(
            access_key_id=SecretStr("AKIAIOSFODNN7EXAMPLE"),
            secret_access_key=SecretStr("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
        )
        assert config.typid == "static_keys"
        assert config.access_key_id.get_secret_value() == "AKIAIOSFODNN7EXAMPLE"
        assert (
            config.secret_access_key.get_secret_value()
            == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        )
        assert config.session_token is None

    def test_static_keys_with_session_token(self):
        """Test static keys config with session token."""
        config = CredConfigStaticKeys(
            access_key_id=SecretStr("AKIAIOSFODNN7EXAMPLE"),
            secret_access_key=SecretStr("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
            session_token=SecretStr("FwoGZXIvYXdzEBYaDG..."),
        )
        assert config.session_token is not None
        assert config.session_token.get_secret_value() == "FwoGZXIvYXdzEBYaDG..."
