"""Tests for AWS credential provider."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from ayuna_creds.aws_config import (
    CredConfigAssumeRole,
    CredConfigAuto,
    CredConfigProfile,
    CredConfigStaticKeys,
    CredConfigWebIdentity,
)
from ayuna_creds.aws_provider import CredProvider


class TestCredProviderAuto:
    """Tests for automatic AWS credential resolution."""

    def test_resolve_auto_creates_session(self):
        """Test that auto resolution creates a boto3 session."""
        config = CredConfigAuto(region="us-east-1")
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            # Mock STS client for security enforcement
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            }
            mock_session.client.return_value = mock_sts

            session = provider.resolve_session()

            mock_session_class.assert_called_once_with(region_name="us-east-1")
            assert session == mock_session

    def test_resolve_auto_enforces_account_id(self):
        """Test that auto resolution enforces account ID restrictions."""
        config = CredConfigAuto(
            region="us-east-1",
            allowed_account_ids=["123456789012"],
        )
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            }
            mock_session.client.return_value = mock_sts

            session = provider.resolve_session()
            assert session == mock_session

    def test_resolve_auto_fails_wrong_account(self):
        """Test that auto resolution fails for wrong account ID."""
        config = CredConfigAuto(
            region="us-east-1",
            allowed_account_ids=["999999999999"],
        )
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            }
            mock_session.client.return_value = mock_sts

            with pytest.raises(PermissionError) as exc_info:
                provider.resolve_session()

            assert "123456789012" in str(exc_info.value)
            assert "not in the list of allowed account IDs" in str(exc_info.value)


class TestCredProviderProfile:
    """Tests for profile-based AWS credential resolution."""

    def test_resolve_profile_creates_session(self):
        """Test that profile resolution creates a boto3 session with profile."""
        config = CredConfigProfile(profile_name="my-profile", region="us-west-2")
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            }
            mock_session.client.return_value = mock_sts

            session = provider.resolve_session()

            mock_session_class.assert_called_once_with(
                profile_name="my-profile", region_name="us-west-2"
            )
            assert session == mock_session


class TestCredProviderAssumeRole:
    """Tests for assume role AWS credential resolution."""

    def test_resolve_assume_role(self):
        """Test that assume role resolution works correctly."""
        config = CredConfigAssumeRole(
            role_arn="arn:aws:iam::123456789012:role/MyRole",
            session_name="test-session",
            external_id="my-external-id",
            duration_seconds=7200,
        )
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.client") as mock_client:
            mock_sts = MagicMock()
            mock_sts.assume_role.return_value = {
                "Credentials": {
                    "AccessKeyId": "ASgeiageoKIH",
                    "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "SessionToken": "FwoGZXIvYXdzEBYaDG...",
                }
            }
            mock_client.return_value = mock_sts

            with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                # Mock STS for security enforcement
                mock_enforce_sts = MagicMock()
                mock_enforce_sts.get_caller_identity.return_value = {
                    "Account": "123456789012",
                    "Arn": "arn:aws:sts::123456789012:assumed-role/MyRole/test-session",
                }
                mock_session.client.return_value = mock_enforce_sts

                session = provider.resolve_session()

                # Verify assume_role was called with correct parameters
                mock_sts.assume_role.assert_called_once_with(
                    RoleArn="arn:aws:iam::123456789012:role/MyRole",
                    RoleSessionName="test-session",
                    DurationSeconds=7200,
                    ExternalId="my-external-id",
                )
                assert session == mock_session


class TestCredProviderWebIdentity:
    """Tests for web identity federation credential resolution."""

    def test_resolve_web_identity_file_not_found(self):
        """Test that web identity fails gracefully when token file doesn't exist."""
        config = CredConfigWebIdentity(
            role_arn="arn:aws:iam::123456789012:role/MyRole",
            federated_token_file="/nonexistent/path/token",
            session_name="test-session",
        )
        provider = CredProvider(config=config)

        with pytest.raises(FileNotFoundError) as exc_info:
            provider.resolve_session()

        assert "/nonexistent/path/token" in str(exc_info.value)

    def test_resolve_web_identity_success(self, tmp_path):
        """Test successful web identity resolution."""
        token_file = tmp_path / "token"
        token_file.write_text("my-web-identity-token")

        config = CredConfigWebIdentity(
            role_arn="arn:aws:iam::123456789012:role/MyRole",
            federated_token_file=str(token_file),
            session_name="test-session",
            duration_seconds=3600,
        )
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.client") as mock_client:
            mock_sts = MagicMock()
            mock_sts.assume_role_with_web_identity.return_value = {
                "Credentials": {
                    "AccessKeyId": "ASgeiageoKIH",
                    "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "SessionToken": "FwoGZXIvYXdzEBYaDG...",
                }
            }
            mock_client.return_value = mock_sts

            with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                mock_enforce_sts = MagicMock()
                mock_enforce_sts.get_caller_identity.return_value = {
                    "Account": "123456789012",
                    "Arn": "arn:aws:sts::123456789012:assumed-role/MyRole/test-session",
                }
                mock_session.client.return_value = mock_enforce_sts

                session = provider.resolve_session()

                mock_sts.assume_role_with_web_identity.assert_called_once_with(
                    RoleArn="arn:aws:iam::123456789012:role/MyRole",
                    RoleSessionName="test-session",
                    WebIdentityToken="my-web-identity-token",
                    DurationSeconds=3600,
                )
                assert session == mock_session


class TestCredProviderStaticKeys:
    """Tests for static key AWS credential resolution."""

    def test_resolve_static_keys(self):
        """Test that static keys resolution creates a boto3 session."""
        config = CredConfigStaticKeys(
            access_key_id=SecretStr("AKIAIOSFODNN7EXAMPLE"),
            secret_access_key=SecretStr("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
            region="eu-west-1",
        )
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            }
            mock_session.client.return_value = mock_sts

            session = provider.resolve_session()

            mock_session_class.assert_called_once_with(
                aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
                aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                aws_session_token=None,
                region_name="eu-west-1",
            )
            assert session == mock_session

    def test_resolve_static_keys_with_session_token(self):
        """Test static keys resolution with session token."""
        config = CredConfigStaticKeys(
            access_key_id=SecretStr("AKIAIOSFODNN7EXAMPLE"),
            secret_access_key=SecretStr("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
            session_token=SecretStr("FwoGZXIvYXdzEBYaDG..."),
        )
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            }
            mock_session.client.return_value = mock_sts

            provider.resolve_session()

            mock_session_class.assert_called_once_with(
                aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
                aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                aws_session_token="FwoGZXIvYXdzEBYaDG...",
                region_name=None,
            )


class TestCredProviderSecurityEnforcement:
    """Tests for security enforcement in credential provider."""

    def test_enforce_role_arn_success(self):
        """Test successful role ARN enforcement."""
        config = CredConfigAuto(
            allowed_role_arns=["arn:aws:iam::123456789012:role/AllowedRole"],
        )
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:role/AllowedRole",
            }
            mock_session.client.return_value = mock_sts

            session = provider.resolve_session()
            assert session == mock_session

    def test_enforce_role_arn_failure(self):
        """Test that wrong role ARN raises PermissionError."""
        config = CredConfigAuto(
            allowed_role_arns=["arn:aws:iam::123456789012:role/AllowedRole"],
        )
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:role/DifferentRole",
            }
            mock_session.client.return_value = mock_sts

            with pytest.raises(PermissionError) as exc_info:
                provider.resolve_session()

            assert "DifferentRole" in str(exc_info.value)

    def test_enforce_both_account_and_role(self):
        """Test enforcement of both account ID and role ARN."""
        config = CredConfigAuto(
            allowed_account_ids=["123456789012"],
            allowed_role_arns=["arn:aws:iam::123456789012:role/MyRole"],
        )
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:role/MyRole",
            }
            mock_session.client.return_value = mock_sts

            session = provider.resolve_session()
            assert session == mock_session


class TestCredProviderSecurityEnforcementSkipped:
    """Tests for security enforcement skipped when no restrictions are configured."""

    def test_enforce_security_skipped_when_no_restrictions(self):
        """Test that STS is not called when no account or role restrictions are set."""
        config = CredConfigAuto(region="us-east-1")
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            provider.resolve_session()

            # STS client should NOT be created since there are no restrictions
            mock_session.client.assert_not_called()


class TestCredProviderWebIdentityTokenStripping:
    """Tests for web identity token whitespace stripping."""

    def test_resolve_web_identity_strips_token(self, tmp_path):
        """Test that trailing newline in token file is stripped before sending to STS."""
        token_file = tmp_path / "token"
        token_file.write_text("my-web-identity-token\n")

        config = CredConfigWebIdentity(
            role_arn="arn:aws:iam::123456789012:role/MyRole",
            federated_token_file=str(token_file),
            session_name="test-session",
        )
        provider = CredProvider(config=config)

        with patch("ayuna_creds.aws_provider.boto3.client") as mock_client:
            mock_sts = MagicMock()
            mock_sts.assume_role_with_web_identity.return_value = {
                "Credentials": {
                    "AccessKeyId": "ASgeiageoKIH",
                    "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "SessionToken": "FwoGZXIvYXdzEBYaDG...",
                }
            }
            mock_client.return_value = mock_sts

            with patch("ayuna_creds.aws_provider.boto3.Session") as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                provider.resolve_session()

                # Token must be stripped — no trailing newline
                mock_sts.assume_role_with_web_identity.assert_called_once_with(
                    RoleArn="arn:aws:iam::123456789012:role/MyRole",
                    RoleSessionName="test-session",
                    WebIdentityToken="my-web-identity-token",
                    DurationSeconds=3600,
                )


class TestCredProviderUnsupportedMethod:
    """Tests for unsupported credential methods."""

    def test_unsupported_method_raises_error(self):
        """Test that unsupported method raises ValueError."""
        config = MagicMock()
        config.typid = "unsupported_method"
        provider = CredProvider(config=config)

        with pytest.raises(ValueError) as exc_info:
            provider.resolve_session()

        assert "unsupported_method" in str(exc_info.value)
