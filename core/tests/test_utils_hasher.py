"""
Tests for ayuna_core.utils.hasher module.

Tests the Hasher class for:
- MD5 hash validation and generation
- SHA256 hash validation and generation
"""

from ayuna_core.utils.hasher import Hasher


class TestHasherMd5Validation:
    """Tests for Hasher.is_formatted_md5()."""

    def test_valid_md5_lowercase(self):
        """Test valid MD5 hash with lowercase hex characters."""
        valid_md5 = "d41d8cd98f00b204e9800998ecf8427e"
        assert Hasher.is_formatted_md5(valid_md5) is True

    def test_valid_md5_uppercase(self):
        """Test valid MD5 hash with uppercase hex characters."""
        valid_md5 = "D41D8CD98F00B204E9800998ECF8427E"
        assert Hasher.is_formatted_md5(valid_md5) is True

    def test_valid_md5_mixed_case(self):
        """Test valid MD5 hash with mixed case hex characters."""
        valid_md5 = "D41d8cd98f00B204e9800998ecf8427E"
        assert Hasher.is_formatted_md5(valid_md5) is True

    def test_invalid_md5_too_short(self):
        """Test that a hash shorter than 32 characters is invalid."""
        invalid_md5 = "d41d8cd98f00b204e9800998ecf842"
        assert Hasher.is_formatted_md5(invalid_md5) is False

    def test_invalid_md5_too_long(self):
        """Test that a hash longer than 32 characters is invalid."""
        invalid_md5 = "d41d8cd98f00b204e9800998ecf8427eabc"
        assert Hasher.is_formatted_md5(invalid_md5) is False

    def test_invalid_md5_non_hex_characters(self):
        """Test that non-hex characters make the hash invalid."""
        invalid_md5 = "g41d8cd98f00b204e9800998ecf8427e"
        assert Hasher.is_formatted_md5(invalid_md5) is False

    def test_invalid_md5_empty_string(self):
        """Test that empty string is invalid."""
        assert Hasher.is_formatted_md5("") is False

    def test_invalid_md5_with_spaces(self):
        """Test that hash with spaces is invalid."""
        invalid_md5 = "d41d8cd9 8f00b204 e9800998 ecf8427e"
        assert Hasher.is_formatted_md5(invalid_md5) is False


class TestHasherSha256Validation:
    """Tests for Hasher.is_formatted_sha256()."""

    def test_valid_sha256_lowercase(self):
        """Test valid SHA256 hash with lowercase hex characters."""
        valid_sha256 = (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        assert Hasher.is_formatted_sha256(valid_sha256) is True

    def test_valid_sha256_uppercase(self):
        """Test valid SHA256 hash with uppercase hex characters."""
        valid_sha256 = (
            "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855"
        )
        assert Hasher.is_formatted_sha256(valid_sha256) is True

    def test_valid_sha256_mixed_case(self):
        """Test valid SHA256 hash with mixed case hex characters."""
        valid_sha256 = (
            "E3b0c44298fc1c149afbf4c8996fb92427ae41e4649B934ca495991b7852B855"
        )
        assert Hasher.is_formatted_sha256(valid_sha256) is True

    def test_invalid_sha256_too_short(self):
        """Test that a hash shorter than 64 characters is invalid."""
        invalid_sha256 = (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b8"
        )
        assert Hasher.is_formatted_sha256(invalid_sha256) is False

    def test_invalid_sha256_too_long(self):
        """Test that a hash longer than 64 characters is invalid."""
        invalid_sha256 = (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855abc"
        )
        assert Hasher.is_formatted_sha256(invalid_sha256) is False

    def test_invalid_sha256_non_hex_characters(self):
        """Test that non-hex characters make the hash invalid."""
        invalid_sha256 = (
            "g3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        assert Hasher.is_formatted_sha256(invalid_sha256) is False

    def test_invalid_sha256_empty_string(self):
        """Test that empty string is invalid."""
        assert Hasher.is_formatted_sha256("") is False

    def test_invalid_sha256_with_spaces(self):
        """Test that hash with spaces is invalid."""
        invalid_sha256 = (
            "e3b0c442 98fc1c14 9afbf4c8 996fb924 27ae41e4 649b934c a495991b 7852b855"
        )
        assert Hasher.is_formatted_sha256(invalid_sha256) is False


class TestHasherMd5Generation:
    """Tests for Hasher.generate_md5_hash()."""

    def test_generate_md5_from_string(self):
        """Test MD5 hash generation from a string."""
        payload = "hello world"
        hash_val = Hasher.generate_md5_hash(payload)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 32
        assert Hasher.is_formatted_md5(hash_val) is True

    def test_generate_md5_from_dict(self):
        """Test MD5 hash generation from a dictionary."""
        payload = {"name": "test", "value": 123}
        hash_val = Hasher.generate_md5_hash(payload)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 32
        assert Hasher.is_formatted_md5(hash_val) is True

    def test_generate_md5_from_list(self):
        """Test MD5 hash generation from a list."""
        payload = [1, 2, 3, "four", {"five": 5}]
        hash_val = Hasher.generate_md5_hash(payload)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 32
        assert Hasher.is_formatted_md5(hash_val) is True

    def test_generate_md5_deterministic(self):
        """Test that MD5 generation is deterministic."""
        payload = {"key": "value"}
        hash1 = Hasher.generate_md5_hash(payload)
        hash2 = Hasher.generate_md5_hash(payload)

        assert hash1 == hash2

    def test_generate_md5_different_payloads(self):
        """Test that different payloads produce different hashes."""
        hash1 = Hasher.generate_md5_hash("hello")
        hash2 = Hasher.generate_md5_hash("world")

        assert hash1 != hash2

    def test_generate_md5_from_int(self):
        """Test MD5 hash generation from an integer."""
        payload = 42
        hash_val = Hasher.generate_md5_hash(payload)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 32

    def test_generate_md5_from_bool(self):
        """Test MD5 hash generation from a boolean."""
        hash_true = Hasher.generate_md5_hash(True)
        hash_false = Hasher.generate_md5_hash(False)

        assert hash_true != hash_false
        assert Hasher.is_formatted_md5(hash_true) is True
        assert Hasher.is_formatted_md5(hash_false) is True

    def test_generate_md5_from_null(self):
        """Test MD5 hash generation from None."""
        hash_val = Hasher.generate_md5_hash(None)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 32


class TestHasherSha256Generation:
    """Tests for Hasher.generate_sha256_hash()."""

    def test_generate_sha256_from_string(self):
        """Test SHA256 hash generation from a string."""
        payload = "hello world"
        hash_val = Hasher.generate_sha256_hash(payload)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 64
        assert Hasher.is_formatted_sha256(hash_val) is True

    def test_generate_sha256_from_dict(self):
        """Test SHA256 hash generation from a dictionary."""
        payload = {"name": "test", "value": 123}
        hash_val = Hasher.generate_sha256_hash(payload)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 64
        assert Hasher.is_formatted_sha256(hash_val) is True

    def test_generate_sha256_from_list(self):
        """Test SHA256 hash generation from a list."""
        payload = [1, 2, 3, "four", {"five": 5}]
        hash_val = Hasher.generate_sha256_hash(payload)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 64
        assert Hasher.is_formatted_sha256(hash_val) is True

    def test_generate_sha256_deterministic(self):
        """Test that SHA256 generation is deterministic."""
        payload = {"key": "value"}
        hash1 = Hasher.generate_sha256_hash(payload)
        hash2 = Hasher.generate_sha256_hash(payload)

        assert hash1 == hash2

    def test_generate_sha256_different_payloads(self):
        """Test that different payloads produce different hashes."""
        hash1 = Hasher.generate_sha256_hash("hello")
        hash2 = Hasher.generate_sha256_hash("world")

        assert hash1 != hash2

    def test_generate_sha256_from_int(self):
        """Test SHA256 hash generation from an integer."""
        payload = 42
        hash_val = Hasher.generate_sha256_hash(payload)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 64

    def test_generate_sha256_from_bool(self):
        """Test SHA256 hash generation from a boolean."""
        hash_true = Hasher.generate_sha256_hash(True)
        hash_false = Hasher.generate_sha256_hash(False)

        assert hash_true != hash_false
        assert Hasher.is_formatted_sha256(hash_true) is True
        assert Hasher.is_formatted_sha256(hash_false) is True

    def test_generate_sha256_from_null(self):
        """Test SHA256 hash generation from None."""
        hash_val = Hasher.generate_sha256_hash(None)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 64


class TestHasherCrossAlgorithm:
    """Tests comparing MD5 and SHA256 behavior."""

    def test_md5_and_sha256_different_lengths(self):
        """Test that MD5 produces 32-char hash and SHA256 produces 64-char hash."""
        payload = "test"
        md5_hash = Hasher.generate_md5_hash(payload)
        sha256_hash = Hasher.generate_sha256_hash(payload)

        assert len(md5_hash) == 32
        assert len(sha256_hash) == 64

    def test_md5_and_sha256_different_values(self):
        """Test that MD5 and SHA256 produce different hash values."""
        payload = "test"
        md5_hash = Hasher.generate_md5_hash(payload)
        sha256_hash = Hasher.generate_sha256_hash(payload)

        # SHA256 is longer, so they can't be equal
        assert md5_hash != sha256_hash

    def test_validation_functions_distinguish_lengths(self):
        """Test that validation functions correctly distinguish hash types."""
        md5_hash = Hasher.generate_md5_hash("test")
        sha256_hash = Hasher.generate_sha256_hash("test")

        # MD5 hash should only pass MD5 validation
        assert Hasher.is_formatted_md5(md5_hash) is True
        assert Hasher.is_formatted_sha256(md5_hash) is False

        # SHA256 hash should only pass SHA256 validation
        assert Hasher.is_formatted_sha256(sha256_hash) is True
        assert Hasher.is_formatted_md5(sha256_hash) is False
