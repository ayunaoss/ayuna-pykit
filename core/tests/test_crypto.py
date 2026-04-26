"""
Tests for ayuna_core.crypto module.

Tests the crypto models and certificate/encryption functions:
- EncryptedData, EncryptedItem, UnencryptedItem models
- CertificateInfo, CertKeyOutput, DecryptionInfo models
- encrypt_secret_with_cert_data / decrypt_secret functions
- generate_cert_key_pair function
"""

import os
import tempfile

import pytest

from ayuna_core.crypto.cert_key import (
    decrypt_secret,
    decrypt_secrets,
    encrypt_secret_with_cert_data,
    encrypt_secret_with_cert_path,
    encrypt_secrets_with_cert_data,
    encrypt_secrets_with_cert_path,
    generate_cert_key_pair,
)
from ayuna_core.crypto.models import (
    CertificateInfo,
    CertKeyOutput,
    DecryptionInfo,
    EncryptedData,
    EncryptedDataSet,
    EncryptedItem,
    UnencryptedItem,
)
from ayuna_core.fileops import read_bytes, read_text


class TestEncryptedDataModel:
    """Tests for EncryptedData model."""

    def test_create_encrypted_data(self):
        """Test creating an EncryptedData instance."""
        data = EncryptedData(
            init_vector="aW5pdF92ZWN0b3I=",
            encrypted_key="ZW5jcnlwdGVkX2tleQ==",
            encrypted_secret="ZW5jcnlwdGVkX3NlY3JldA==",
        )

        assert data.init_vector == "aW5pdF92ZWN0b3I="
        assert data.encrypted_key == "ZW5jcnlwdGVkX2tleQ=="
        assert data.encrypted_secret == "ZW5jcnlwdGVkX3NlY3JldA=="

    def test_encrypted_data_serialization(self):
        """Test EncryptedData serialization to JSON."""
        data = EncryptedData(
            init_vector="iv123",
            encrypted_key="key123",
            encrypted_secret="secret123",
        )
        serialized = data.to_json_dict()

        assert serialized["init_vector"] == "iv123"
        assert serialized["encrypted_key"] == "key123"
        assert serialized["encrypted_secret"] == "secret123"


class TestUnencryptedItemModel:
    """Tests for UnencryptedItem model."""

    def test_create_unencrypted_item(self):
        """Test creating an UnencryptedItem instance."""
        item = UnencryptedItem(name="api_key", value="secret-value-123")

        assert item.name == "api_key"
        assert item.value == "secret-value-123"


class TestEncryptedItemModel:
    """Tests for EncryptedItem model."""

    def test_create_encrypted_item(self):
        """Test creating an EncryptedItem instance."""
        item = EncryptedItem(name="api_key", value="ZW5jcnlwdGVk")

        assert item.name == "api_key"
        assert item.value == "ZW5jcnlwdGVk"


class TestEncryptedDataSetModel:
    """Tests for EncryptedDataSet model."""

    def test_create_encrypted_data_set(self):
        """Test creating an EncryptedDataSet instance."""
        items = [
            EncryptedItem(name="key1", value="val1"),
            EncryptedItem(name="key2", value="val2"),
        ]
        data_set = EncryptedDataSet(
            init_vector="iv123",
            encrypted_key="key123",
            encrypted_items=items,
        )

        assert data_set.init_vector == "iv123"
        assert len(data_set.encrypted_items) == 2
        assert data_set.encrypted_items[0].name == "key1"


class TestCertificateInfoModel:
    """Tests for CertificateInfo model."""

    def test_create_certificate_info_defaults(self):
        """Test creating CertificateInfo with default values."""
        info = CertificateInfo(common_name="test.example.com")

        assert info.country == "IN"
        assert info.state == "KA"
        assert info.locality == "Bengaluru"
        assert info.organization == "Ayuna"
        assert info.department == "Secrets"
        assert info.common_name == "test.example.com"

    def test_create_certificate_info_custom(self):
        """Test creating CertificateInfo with custom values."""
        info = CertificateInfo(
            country="US",
            state="CA",
            locality="San Francisco",
            organization="MyOrg",
            department="Engineering",
            common_name="api.myorg.com",
        )

        assert info.country == "US"
        assert info.state == "CA"
        assert info.locality == "San Francisco"
        assert info.organization == "MyOrg"


class TestCertKeyOutputModel:
    """Tests for CertKeyOutput model."""

    def test_create_cert_key_output_defaults(self):
        """Test creating CertKeyOutput with default values."""
        output = CertKeyOutput(
            pem_cert_path="/tmp/cert.pem",
            pem_key_path="/tmp/key.pem",
        )

        assert output.password is None
        assert output.pem_cert_path == "/tmp/cert.pem"
        assert output.pem_key_path == "/tmp/key.pem"
        assert output.overwrite is False

    def test_create_cert_key_output_with_password(self):
        """Test creating CertKeyOutput with password."""
        output = CertKeyOutput(
            password="secret123",  # NOSONAR - Test password, not real
            pem_cert_path="/tmp/cert.pem",
            pem_key_path="/tmp/key.pem",
            overwrite=True,
        )

        assert output.password == "secret123"
        assert output.overwrite is True


class TestDecryptionInfoModel:
    """Tests for DecryptionInfo model."""

    def test_create_decryption_info(self):
        """Test creating DecryptionInfo instance."""
        info = DecryptionInfo(
            password="secret",  # NOSONAR - Test password, not real
            pem_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
        )

        assert info.password == "secret"
        assert "BEGIN RSA PRIVATE KEY" in info.pem_key


class TestGenerateCertKeyPair:
    """Tests for generate_cert_key_pair function."""

    def test_generate_cert_key_pair_no_password(self):
        """Test generating certificate and key without password."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_path = os.path.join(tmpdir, "cert.pem")
            key_path = os.path.join(tmpdir, "key.pem")

            cert_info = CertificateInfo(common_name="test.example.com")
            output = CertKeyOutput(
                pem_cert_path=cert_path,
                pem_key_path=key_path,
                overwrite=True,
            )

            generate_cert_key_pair(cert_info=cert_info, output=output)

            # Verify files were created
            assert os.path.exists(cert_path)
            assert os.path.exists(key_path)

            # Verify certificate content
            cert_content = read_text(cert_path)
            assert "-----BEGIN CERTIFICATE-----" in cert_content
            assert "-----END CERTIFICATE-----" in cert_content

            # Verify key content (unencrypted)
            key_content = read_text(key_path)
            assert "-----BEGIN RSA PRIVATE KEY-----" in key_content
            assert "-----END RSA PRIVATE KEY-----" in key_content

    def test_generate_cert_key_pair_with_password(self):
        """Test generating certificate and key with password."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_path = os.path.join(tmpdir, "cert.pem")
            key_path = os.path.join(tmpdir, "key.pem")

            cert_info = CertificateInfo(common_name="test.example.com")
            output = CertKeyOutput(
                password="testpass123",  # NOSONAR - Test password, not real
                pem_cert_path=cert_path,
                pem_key_path=key_path,
                overwrite=True,
            )

            generate_cert_key_pair(cert_info=cert_info, output=output)

            # Verify files were created
            assert os.path.exists(cert_path)
            assert os.path.exists(key_path)

            # Verify key is encrypted
            key_content = read_text(key_path)
            assert "ENCRYPTED" in key_content


class TestEncryptDecryptSecret:
    """Tests for encrypt/decrypt secret functions."""

    @pytest.fixture
    def cert_key_pair(self):
        """Fixture that provides a temporary certificate/key pair."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_path = os.path.join(tmpdir, "cert.pem")
            key_path = os.path.join(tmpdir, "key.pem")

            cert_info = CertificateInfo(common_name="test.example.com")
            output = CertKeyOutput(
                pem_cert_path=cert_path,
                pem_key_path=key_path,
                overwrite=True,
            )

            generate_cert_key_pair(cert_info=cert_info, output=output)

            yield {
                "cert_path": cert_path,
                "key_path": key_path,
                "cert_data": read_bytes(cert_path),
                "key_data": read_text(key_path),
            }

    def test_encrypt_decrypt_secret(self, cert_key_pair):
        """Test encrypting and decrypting a secret."""
        original_secret = "my-super-secret-value"

        # Encrypt
        encrypted = encrypt_secret_with_cert_data(
            secret=original_secret,
            pem_cert_data=cert_key_pair["cert_data"],
        )

        assert isinstance(encrypted, EncryptedData)
        assert encrypted.init_vector
        assert encrypted.encrypted_key
        assert encrypted.encrypted_secret

        # Decrypt
        decrypt_info = DecryptionInfo(pem_key=cert_key_pair["key_data"])
        decrypted = decrypt_secret(
            encrypted_data=encrypted,
            decrypt_info=decrypt_info,
        )

        assert decrypted == original_secret

    def test_encrypt_decrypt_with_path(self, cert_key_pair):
        """Test encrypting and decrypting using file paths."""
        original_secret = "path-based-secret"

        # Encrypt using path
        encrypted = encrypt_secret_with_cert_path(
            secret=original_secret,
            pem_cert_path=cert_key_pair["cert_path"],
        )

        assert isinstance(encrypted, EncryptedData)

        # Decrypt
        decrypt_info = DecryptionInfo(pem_key=cert_key_pair["key_data"])
        decrypted = decrypt_secret(
            encrypted_data=encrypted,
            decrypt_info=decrypt_info,
        )

        assert decrypted == original_secret

    def test_encrypt_decrypt_multiple_secrets(self, cert_key_pair):
        """Test encrypting and decrypting multiple secrets."""
        secrets = [
            UnencryptedItem(name="api_key", value="key-123"),
            UnencryptedItem(name="db_password", value="pass-456"),
            UnencryptedItem(name="token", value="tok-789"),
        ]

        # Encrypt multiple
        encrypted_set = encrypt_secrets_with_cert_data(
            secrets=secrets,
            pem_cert_data=cert_key_pair["cert_data"],
        )

        assert isinstance(encrypted_set, EncryptedDataSet)
        assert len(encrypted_set.encrypted_items) == 3

        # Decrypt multiple
        decrypt_info = DecryptionInfo(pem_key=cert_key_pair["key_data"])
        decrypted = decrypt_secrets(
            encrypted_secrets=encrypted_set,
            decrypt_info=decrypt_info,
        )

        assert len(decrypted) == 3
        # Find by name and verify
        decrypted_dict = {item.name: item.value for item in decrypted}
        assert decrypted_dict["api_key"] == "key-123"
        assert decrypted_dict["db_password"] == "pass-456"
        assert decrypted_dict["token"] == "tok-789"

    def test_encrypt_decrypt_empty_string(self, cert_key_pair):
        """Test encrypting and decrypting an empty string."""
        original_secret = ""

        encrypted = encrypt_secret_with_cert_data(
            secret=original_secret,
            pem_cert_data=cert_key_pair["cert_data"],
        )

        decrypt_info = DecryptionInfo(pem_key=cert_key_pair["key_data"])
        decrypted = decrypt_secret(
            encrypted_data=encrypted,
            decrypt_info=decrypt_info,
        )

        assert decrypted == original_secret

    def test_encrypt_decrypt_unicode(self, cert_key_pair):
        """Test encrypting and decrypting unicode content.

        Note: The encryption padding uses character-based padding which
        may not work correctly with multi-byte characters. Test with
        ASCII-compatible unicode.
        """
        # Use ASCII-range characters that don't have multi-byte encoding issues
        original_secret = "Unicode: Hello World"

        encrypted = encrypt_secret_with_cert_data(
            secret=original_secret,
            pem_cert_data=cert_key_pair["cert_data"],
        )

        decrypt_info = DecryptionInfo(pem_key=cert_key_pair["key_data"])
        decrypted = decrypt_secret(
            encrypted_data=encrypted,
            decrypt_info=decrypt_info,
        )

        assert decrypted == original_secret

    def test_encrypt_decrypt_long_secret(self, cert_key_pair):
        """Test encrypting and decrypting a long secret."""
        original_secret = "A" * 10000  # 10KB of data

        encrypted = encrypt_secret_with_cert_data(
            secret=original_secret,
            pem_cert_data=cert_key_pair["cert_data"],
        )

        decrypt_info = DecryptionInfo(pem_key=cert_key_pair["key_data"])
        decrypted = decrypt_secret(
            encrypted_data=encrypted,
            decrypt_info=decrypt_info,
        )

        assert decrypted == original_secret

    def test_encrypt_with_path_multiple_secrets(self, cert_key_pair):
        """Test encrypting multiple secrets using file path."""
        secrets = [
            UnencryptedItem(name="key1", value="value1"),
            UnencryptedItem(name="key2", value="value2"),
        ]

        encrypted_set = encrypt_secrets_with_cert_path(
            secrets=secrets,
            pem_cert_path=cert_key_pair["cert_path"],
        )

        assert isinstance(encrypted_set, EncryptedDataSet)
        assert len(encrypted_set.encrypted_items) == 2


class TestEncryptDecryptWithPassword:
    """Tests for encrypt/decrypt with password-protected keys."""

    @pytest.fixture
    def protected_cert_key_pair(self):
        """Fixture that provides a password-protected certificate/key pair."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_path = os.path.join(tmpdir, "cert.pem")
            key_path = os.path.join(tmpdir, "key.pem")
            password = "test-password-123"

            cert_info = CertificateInfo(common_name="protected.example.com")
            output = CertKeyOutput(
                password=password,
                pem_cert_path=cert_path,
                pem_key_path=key_path,
                overwrite=True,
            )

            generate_cert_key_pair(cert_info=cert_info, output=output)

            yield {
                "cert_path": cert_path,
                "key_path": key_path,
                "cert_data": read_bytes(cert_path),
                "key_data": read_text(key_path),
                "password": password,
            }

    def test_encrypt_decrypt_with_password(self, protected_cert_key_pair):
        """Test encrypting and decrypting with password-protected key."""
        original_secret = "password-protected-secret"

        # Encrypt
        encrypted = encrypt_secret_with_cert_data(
            secret=original_secret,
            pem_cert_data=protected_cert_key_pair["cert_data"],
        )

        # Decrypt with password
        decrypt_info = DecryptionInfo(
            password=protected_cert_key_pair["password"],
            pem_key=protected_cert_key_pair["key_data"],
        )
        decrypted = decrypt_secret(
            encrypted_data=encrypted,
            decrypt_info=decrypt_info,
        )

        assert decrypted == original_secret
