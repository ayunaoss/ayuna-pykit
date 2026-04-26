"""
Tests for ayuna_core.utils.archiver module.

Tests the Archiver class for:
- Compressing/decompressing bytes using gzip, lz4, zstd
- Compressing/decompressing strings
- Compressing JSON data
- Various output formats (raw bytes, base64)
"""

import base64
import json

from ayuna_core.utils.archiver import (
    Archiver,
    CompressionConfig,
    DecompressionConfig,
    GzipCompression,
    Lz4Compression,
    ZstdCompression,
)


class TestGzipCompression:
    """Tests for gzip compression/decompression."""

    def test_compress_decompress_bytes(self):
        """Test basic bytes compression and decompression."""
        original = b"Hello, World! This is a test string for compression."
        config = CompressionConfig(archive=GzipCompression())
        deconfig = DecompressionConfig(archive=GzipCompression())

        compressed = Archiver.compress_bytes(data=original, config=config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=deconfig)

        assert decompressed == original

    def test_compress_returns_smaller_data(self):
        """Test that compression actually reduces data size for compressible content."""
        # Create highly compressible data
        original = b"a" * 10000
        config = CompressionConfig(archive=GzipCompression(level=9))

        compressed = Archiver.compress_bytes(data=original, config=config)

        assert len(compressed) < len(original)

    def test_compress_with_b64_output(self):
        """Test compression with base64 output."""
        original = b"Test data for base64 encoding"
        config = CompressionConfig(archive=GzipCompression(), output="b64_string")

        compressed = Archiver.compress_bytes(data=original, config=config)

        assert isinstance(compressed, str)
        # Should be valid base64
        base64.b64decode(compressed)

    def test_decompress_to_raw_string(self):
        """Test decompression to raw string output."""
        original = b"Hello, World!"
        comp_config = CompressionConfig(archive=GzipCompression())
        decomp_config = DecompressionConfig(
            archive=GzipCompression(), output="raw_string"
        )

        compressed = Archiver.compress_bytes(data=original, config=comp_config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=decomp_config)

        assert isinstance(decompressed, str)
        assert decompressed == "Hello, World!"

    def test_decompress_to_json(self):
        """Test decompression to JSON output."""
        original_data = {"key": "value", "number": 42}
        original = json.dumps(original_data).encode("utf-8")
        comp_config = CompressionConfig(archive=GzipCompression())
        decomp_config = DecompressionConfig(archive=GzipCompression(), output="json")

        compressed = Archiver.compress_bytes(data=original, config=comp_config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=decomp_config)

        assert decompressed == original_data

    def test_compression_levels(self):
        """Test different compression levels."""
        original = b"Test data " * 100

        # Test level 1 (fastest, least compression)
        config_1 = CompressionConfig(archive=GzipCompression(level=1))
        compressed_1 = Archiver.compress_bytes(data=original, config=config_1)

        # Test level 9 (slowest, best compression)
        config_9 = CompressionConfig(archive=GzipCompression(level=9))
        compressed_9 = Archiver.compress_bytes(data=original, config=config_9)

        # Level 9 should produce smaller or equal output
        assert len(compressed_9) <= len(compressed_1)


class TestLz4Compression:
    """Tests for LZ4 compression/decompression."""

    def test_compress_decompress_bytes(self):
        """Test basic bytes compression and decompression."""
        original = b"Hello, World! This is a test string for LZ4 compression."
        config = CompressionConfig(archive=Lz4Compression())
        deconfig = DecompressionConfig(archive=Lz4Compression())

        compressed = Archiver.compress_bytes(data=original, config=config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=deconfig)

        assert decompressed == original

    def test_compress_returns_smaller_data(self):
        """Test that compression reduces data size for compressible content."""
        original = b"a" * 10000
        config = CompressionConfig(archive=Lz4Compression())

        compressed = Archiver.compress_bytes(data=original, config=config)

        assert len(compressed) < len(original)

    def test_compress_with_b64_output(self):
        """Test compression with base64 output."""
        original = b"Test data for LZ4 base64 encoding"
        config = CompressionConfig(archive=Lz4Compression(), output="b64_string")

        compressed = Archiver.compress_bytes(data=original, config=config)

        assert isinstance(compressed, str)
        base64.b64decode(compressed)

    def test_decompress_to_raw_string(self):
        """Test decompression to raw string output."""
        original = b"Hello from LZ4!"
        comp_config = CompressionConfig(archive=Lz4Compression())
        decomp_config = DecompressionConfig(
            archive=Lz4Compression(), output="raw_string"
        )

        compressed = Archiver.compress_bytes(data=original, config=comp_config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=decomp_config)

        assert isinstance(decompressed, str)
        assert decompressed == "Hello from LZ4!"


class TestZstdCompression:
    """Tests for Zstandard compression/decompression."""

    def test_compress_decompress_bytes(self):
        """Test basic bytes compression and decompression."""
        original = b"Hello, World! This is a test string for Zstd compression."
        config = CompressionConfig(archive=ZstdCompression())
        deconfig = DecompressionConfig(archive=ZstdCompression())

        compressed = Archiver.compress_bytes(data=original, config=config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=deconfig)

        assert decompressed == original

    def test_compress_returns_smaller_data(self):
        """Test that compression reduces data size for compressible content."""
        original = b"a" * 10000
        config = CompressionConfig(archive=ZstdCompression())

        compressed = Archiver.compress_bytes(data=original, config=config)

        assert len(compressed) < len(original)

    def test_compress_with_b64_output(self):
        """Test compression with base64 output."""
        original = b"Test data for Zstd base64 encoding"
        config = CompressionConfig(archive=ZstdCompression(), output="b64_string")

        compressed = Archiver.compress_bytes(data=original, config=config)

        assert isinstance(compressed, str)
        base64.b64decode(compressed)

    def test_decompress_to_raw_string(self):
        """Test decompression to raw string output."""
        original = b"Hello from Zstd!"
        comp_config = CompressionConfig(archive=ZstdCompression())
        decomp_config = DecompressionConfig(
            archive=ZstdCompression(), output="raw_string"
        )

        compressed = Archiver.compress_bytes(data=original, config=comp_config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=decomp_config)

        assert isinstance(decompressed, str)
        assert decompressed == "Hello from Zstd!"

    def test_compression_levels(self):
        """Test different compression levels."""
        original = b"Test data " * 100

        # Test lower level
        config_1 = CompressionConfig(archive=ZstdCompression(level=1))
        compressed_1 = Archiver.compress_bytes(data=original, config=config_1)

        # Test higher level
        config_15 = CompressionConfig(archive=ZstdCompression(level=15))
        compressed_15 = Archiver.compress_bytes(data=original, config=config_15)

        # Higher level should produce smaller or equal output
        assert len(compressed_15) <= len(compressed_1)


class TestCompressString:
    """Tests for Archiver.compress_string() and decompress_string()."""

    def test_compress_decompress_string_gzip(self):
        """Test string compression and decompression with gzip."""
        original = "Hello, World! This is a test string."
        comp_config = CompressionConfig(archive=GzipCompression(), output="b64_string")
        decomp_config = DecompressionConfig(
            archive=GzipCompression(), output="raw_string"
        )

        compressed = Archiver.compress_string(data=original, config=comp_config)
        decompressed = Archiver.decompress_string(data=compressed, config=decomp_config)

        assert decompressed == original

    def test_compress_decompress_string_lz4(self):
        """Test string compression and decompression with LZ4."""
        original = "Hello, World! LZ4 string test."
        comp_config = CompressionConfig(archive=Lz4Compression(), output="b64_string")
        decomp_config = DecompressionConfig(
            archive=Lz4Compression(), output="raw_string"
        )

        compressed = Archiver.compress_string(data=original, config=comp_config)
        decompressed = Archiver.decompress_string(data=compressed, config=decomp_config)

        assert decompressed == original

    def test_compress_decompress_string_zstd(self):
        """Test string compression and decompression with Zstd."""
        original = "Hello, World! Zstd string test."
        comp_config = CompressionConfig(archive=ZstdCompression(), output="b64_string")
        decomp_config = DecompressionConfig(
            archive=ZstdCompression(), output="raw_string"
        )

        compressed = Archiver.compress_string(data=original, config=comp_config)
        decompressed = Archiver.decompress_string(data=compressed, config=decomp_config)

        assert decompressed == original

    def test_compress_string_with_unicode(self):
        """Test string compression with unicode characters."""
        original = "Hello, World! Unicode: \u00e9\u00e8\u00ea \u4e2d\u6587"
        comp_config = CompressionConfig(archive=GzipCompression(), output="b64_string")
        decomp_config = DecompressionConfig(
            archive=GzipCompression(), output="raw_string"
        )

        compressed = Archiver.compress_string(data=original, config=comp_config)
        decompressed = Archiver.decompress_string(data=compressed, config=decomp_config)

        assert decompressed == original

    def test_compress_string_with_custom_encoding(self):
        """Test string compression with custom encoding."""
        original = "Simple ASCII text"
        comp_config = CompressionConfig(
            archive=GzipCompression(), output="b64_string", encoding="utf-8"
        )
        decomp_config = DecompressionConfig(
            archive=GzipCompression(), output="raw_string", encoding="utf-8"
        )

        compressed = Archiver.compress_string(data=original, config=comp_config)
        decompressed = Archiver.decompress_string(data=compressed, config=decomp_config)

        assert decompressed == original


class TestCompressJson:
    """Tests for Archiver.compress_json()."""

    def test_compress_decompress_json_gzip(self):
        """Test JSON compression and decompression with gzip."""
        original = {"name": "test", "value": 123, "nested": {"key": "value"}}
        comp_config = CompressionConfig(archive=GzipCompression())
        decomp_config = DecompressionConfig(archive=GzipCompression(), output="json")

        compressed = Archiver.compress_json(data=original, config=comp_config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=decomp_config)

        assert decompressed == original

    def test_compress_decompress_json_lz4(self):
        """Test JSON compression and decompression with LZ4."""
        original = {"name": "test", "items": [1, 2, 3, 4, 5]}
        comp_config = CompressionConfig(archive=Lz4Compression())
        decomp_config = DecompressionConfig(archive=Lz4Compression(), output="json")

        compressed = Archiver.compress_json(data=original, config=comp_config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=decomp_config)

        assert decompressed == original

    def test_compress_decompress_json_zstd(self):
        """Test JSON compression and decompression with Zstd."""
        original = {"key": "value", "boolean": True, "null": None}
        comp_config = CompressionConfig(archive=ZstdCompression())
        decomp_config = DecompressionConfig(archive=ZstdCompression(), output="json")

        compressed = Archiver.compress_json(data=original, config=comp_config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=decomp_config)

        assert decompressed == original

    def test_compress_json_with_list(self):
        """Test JSON compression with a list."""
        original = [1, 2, 3, {"key": "value"}, [4, 5, 6]]
        comp_config = CompressionConfig(archive=GzipCompression())
        decomp_config = DecompressionConfig(archive=GzipCompression(), output="json")

        compressed = Archiver.compress_json(data=original, config=comp_config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=decomp_config)

        assert decompressed == original

    def test_compress_json_with_b64_output(self):
        """Test JSON compression with base64 output."""
        original = {"data": "test"}
        comp_config = CompressionConfig(archive=GzipCompression(), output="b64_string")
        decomp_config = DecompressionConfig(archive=GzipCompression(), output="json")

        compressed = Archiver.compress_json(data=original, config=comp_config)
        assert isinstance(compressed, str)

        # Decompress from b64
        decompressed = Archiver.decompress_string(data=compressed, config=decomp_config)
        assert decompressed == original


class TestCompressionConfigModels:
    """Tests for compression configuration models."""

    def test_gzip_compression_default_level(self):
        """Test GzipCompression default level."""
        config = GzipCompression()
        assert config.algo == "gzip"
        assert config.level >= 0 and config.level <= 9

    def test_lz4_compression_default_level(self):
        """Test Lz4Compression default level."""
        config = Lz4Compression()
        assert config.algo == "lz4"
        assert config.level >= 0 and config.level <= 16

    def test_zstd_compression_default_level(self):
        """Test ZstdCompression default level."""
        config = ZstdCompression()
        assert config.algo == "zstd"
        assert config.level >= 0 and config.level <= 22

    def test_compression_config_default_output(self):
        """Test CompressionConfig default output format."""
        config = CompressionConfig(archive=GzipCompression())
        assert config.output == "raw_bytes"
        assert config.encoding == "utf-8"

    def test_decompression_config_default_output(self):
        """Test DecompressionConfig default output format."""
        config = DecompressionConfig(archive=GzipCompression())
        assert config.output == "raw_bytes"
        assert config.encoding == "utf-8"


class TestCrossAlgorithmCompatibility:
    """Tests to ensure algorithms produce different but valid results."""

    def test_algorithms_produce_different_output(self):
        """Test that different algorithms produce different compressed output."""
        original = b"Test data for comparison" * 10

        gzip_config = CompressionConfig(archive=GzipCompression())
        lz4_config = CompressionConfig(archive=Lz4Compression())
        zstd_config = CompressionConfig(archive=ZstdCompression())

        gzip_compressed = Archiver.compress_bytes(data=original, config=gzip_config)
        lz4_compressed = Archiver.compress_bytes(data=original, config=lz4_config)
        zstd_compressed = Archiver.compress_bytes(data=original, config=zstd_config)

        # All should be different
        assert gzip_compressed != lz4_compressed
        assert gzip_compressed != zstd_compressed
        assert lz4_compressed != zstd_compressed

    def test_empty_data_compression(self):
        """Test compression of empty data."""
        original = b""
        config = CompressionConfig(archive=GzipCompression())
        deconfig = DecompressionConfig(archive=GzipCompression())

        compressed = Archiver.compress_bytes(data=original, config=config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=deconfig)

        assert decompressed == original

    def test_large_data_compression(self):
        """Test compression of large data."""
        # 1MB of compressible data
        original = b"x" * (1024 * 1024)
        config = CompressionConfig(archive=ZstdCompression())
        deconfig = DecompressionConfig(archive=ZstdCompression())

        compressed = Archiver.compress_bytes(data=original, config=config)
        decompressed = Archiver.decompress_bytes(data=compressed, config=deconfig)

        assert decompressed == original
        assert len(compressed) < len(original)
