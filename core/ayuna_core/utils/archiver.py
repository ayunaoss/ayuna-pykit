"""
archiver.py - Data compression and decompression utilities.

This module provides the Archiver class for compressing and decompressing
data using various algorithms:

- gzip: Good compression ratio, widely compatible
- lz4: Fast compression/decompression, moderate ratio
- zstd: Excellent ratio and speed balance

Supports compressing bytes, strings, and JSON data with configurable
output formats (raw bytes or base64 encoded strings).
"""

import base64
import gzip
import io
from sys import getsizeof
from typing import Annotated, Literal, Union

import lz4.block as lz4b
import lz4.frame as lz4f
import orjson as json
import zstandard as zstd
from pydantic import BaseModel, Field

from ..basetypes import JsonType
from ..constants import DEFAULT_COMPRESS_LEVEL

# =============================================================================
# Type Definitions
# =============================================================================

# Compression level constraints for each algorithm
GzipLevel = Annotated[int, Field(ge=0, le=9)]  # gzip: 0-9
ZstdLevel = Annotated[int, Field(ge=0, le=22)]  # zstd: 0-22
Lz4Level = Annotated[int, Field(ge=0, le=16)]  # lz4: 0-16

# =============================================================================
# Compression Configuration Models
# =============================================================================


class GzipCompression(BaseModel):
    """Configuration for gzip compression."""

    algo: Literal["gzip"] = "gzip"
    level: GzipLevel = DEFAULT_COMPRESS_LEVEL


class ZstdCompression(BaseModel):
    """Configuration for Zstandard compression."""

    algo: Literal["zstd"] = "zstd"
    level: ZstdLevel = DEFAULT_COMPRESS_LEVEL


class Lz4Compression(BaseModel):
    """Configuration for LZ4 compression."""

    algo: Literal["lz4"] = "lz4"
    level: Lz4Level = DEFAULT_COMPRESS_LEVEL


# Discriminated union type for compression algorithms
ArcCompression = Annotated[
    Union[GzipCompression, ZstdCompression, Lz4Compression], Field(discriminator="algo")
]


class CompressionConfig(BaseModel):
    """
    Configuration for data compression.

    Attributes
    ----------
    archive : ArcCompression
        Compression algorithm configuration.
    output : Literal["raw_bytes", "b64_string"]
        Output format: raw bytes or base64-encoded string.
    encoding : str
        Character encoding for string operations (default: "utf-8").
    """

    archive: ArcCompression
    output: Literal["raw_bytes", "b64_string"] = "raw_bytes"
    encoding: str = "utf-8"


class DecompressionConfig(BaseModel):
    """
    Configuration for data decompression.

    Attributes
    ----------
    archive : ArcCompression
        Compression algorithm configuration (must match original compression).
    output : Literal["raw_bytes", "raw_string", "json"]
        Output format: raw bytes, decoded string, or parsed JSON.
    encoding : str
        Character encoding for string operations (default: "utf-8").
    """

    archive: ArcCompression
    output: Literal["raw_bytes", "raw_string", "json"] = "raw_bytes"
    encoding: str = "utf-8"


# =============================================================================
# Archiver Class
# =============================================================================


class Archiver:
    """
    Static utility class for data compression and decompression.

    Supports multiple compression algorithms (gzip, lz4, zstd) and
    can compress/decompress bytes, strings, and JSON data.

    All methods are static and can be called without instantiation.
    """

    @staticmethod
    def _lz4b_decompress(data: bytes):
        """
        Decompress data using lz4b

        Parameters
        ----------
        data : bytes
            Data to decompress

        Returns
        -------
        bytes
            Decompressed data
        """
        res_data = bytes()
        comp_size = getsizeof(data)
        max_decomp_size = comp_size * 100
        usize = max_decomp_size // 16

        while True:
            try:
                res_data = lz4b.decompress(
                    data, uncompressed_size=usize, return_bytearray=False
                )
                break
            except lz4b.LZ4BlockError:
                usize *= 2

                if usize > max_decomp_size:
                    raise

        return res_data

    @staticmethod
    def compress_bytes(*, data: bytes, config: CompressionConfig):
        """
        Compress data using gzip, lz4 or zstd based on the configuration

        Parameters
        ----------
        data : bytes
            Data to compress
        config : CompressionConfig
            Compression configuration

        Returns
        -------
        bytes or base64 encoded string
            Compressed data
        """
        res_data = bytes()

        ## Default is zstd compression
        if config.archive.algo == "gzip":
            res_data = gzip.compress(data, compresslevel=config.archive.level)
        elif config.archive.algo == "lz4":
            res_data = lz4f.compress(
                data,
                compression_level=config.archive.level,
                return_bytearray=False,
                store_size=True,
            )
        else:
            zstd_compressor = zstd.ZstdCompressor(level=config.archive.level)

            with io.BytesIO() as out_bio:
                with zstd_compressor.stream_writer(out_bio) as compressor:
                    compressor.write(data)
                    compressor.flush(zstd.FLUSH_FRAME)

                    res_data = out_bio.getvalue()

            del zstd_compressor

        if config.output == "b64_string":
            res_data = base64.b64encode(res_data).decode(encoding=config.encoding)

        return res_data

    @staticmethod
    def decompress_bytes(*, data: bytes, config: DecompressionConfig):
        """
        Decompress data using gzip, lz4 or zstd based on the configuration

        Parameters
        ----------
        data : bytes
            Data to decompress
        config : DecompressionConfig
            Decompression configuration

        Returns
        -------
        bytes or string or json object
            Decompressed data
        """
        res_data = bytes()

        if config.archive.algo == "gzip":
            res_data = gzip.decompress(data)
        elif config.archive.algo == "lz4":
            try:
                res_data = lz4f.decompress(data, return_bytearray=False)
            except Exception:
                try:
                    res_data = lz4b.decompress(data, return_bytearray=False)
                except Exception:
                    res_data = Archiver._lz4b_decompress(data=data)
        else:
            zstd_decompressor = zstd.ZstdDecompressor()

            with zstd_decompressor.stream_reader(data) as stream_reader:
                res_data = stream_reader.readall()

            del zstd_decompressor

        if config.output == "raw_string":
            res_data = bytes.decode(res_data, encoding=config.encoding)
        elif config.output == "json":
            try:
                res_data = json.loads(res_data)
            except json.JSONDecodeError:
                pass

        return res_data

    @staticmethod
    def compress_string(*, data: str, config: CompressionConfig):
        """
        Compress string using gzip, lz4 or zstd based on the configuration

        Parameters
        ----------
        data : str
            Data to compress
        config : CompressionConfig
            Compression configuration

        Returns
        -------
        bytes or base64 encoded string
            Compressed data
        """
        in_data = bytes(data, encoding=config.encoding)
        return Archiver.compress_bytes(data=in_data, config=config)

    @staticmethod
    def decompress_string(*, data: str, config: DecompressionConfig):
        """
        Decompress string using gzip, lz4 or zstd based on the configuration

        Parameters
        ----------
        data : str
            Data to decompress
        config : DecompressionConfig
            Decompression configuration

        Returns
        -------
        bytes or string or json object
            Decompressed data
        """
        try:
            in_data = base64.b64decode(data)
        except Exception:
            in_data = bytes(data, encoding=config.encoding)

        return Archiver.decompress_bytes(data=in_data, config=config)

    @staticmethod
    def compress_json(*, data: JsonType, config: CompressionConfig):
        """
        Compress json using gzip, lz4 or zstd based on the configuration

        Parameters
        ----------
        data : JsonType
            Data to compress
        config : CompressionConfig
            Compression configuration

        Returns
        -------
        bytes or base64 encoded string
            Compressed data
        """
        in_data = json.dumps(data)
        return Archiver.compress_bytes(data=in_data, config=config)
