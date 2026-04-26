"""
hasher.py - Hashing utilities for the Ayuna framework.

This module provides the Hasher class with static methods for:

- Validating hash string formats (MD5, SHA256)
- Generating hashes from JSON-serializable data
"""

import hashlib
import re

import orjson as json

from ..basetypes import JsonType


class Hasher:
    """
    Static utility class for hash validation and generation.

    Provides methods to check if strings are valid hash formats
    and to generate hashes from JSON-serializable data.

    All methods are static and can be called without instantiation.
    """

    # Regex patterns for validating hash string formats
    __md5_hash_regex = re.compile(r"^[a-fA-F0-9]{32}$")
    __sha256_hash_regex = re.compile(r"^[a-fA-F0-9]{64}$")

    @staticmethod
    def is_formatted_md5(hash_val: str) -> bool:
        """
        Check if a string is a valid MD5 hash format.

        Parameters
        ----------
        hash_val : str
            String to validate.

        Returns
        -------
        bool
            True if the string is a 32-character hexadecimal string.
        """
        return bool(Hasher.__md5_hash_regex.match(hash_val))

    @staticmethod
    def is_formatted_sha256(hash_val: str) -> bool:
        """
        Check if a string is a valid SHA256 hash format.

        Parameters
        ----------
        hash_val : str
            String to validate.

        Returns
        -------
        bool
            True if the string is a 64-character hexadecimal string.
        """
        return bool(Hasher.__sha256_hash_regex.match(hash_val))

    @staticmethod
    def generate_md5_hash(payload: JsonType) -> str:
        """
        Generate a MD5 hash from the given payload

        Parameters
        ----------
        payload : JsonType
            The payload to be hashed

        Returns
        -------
        str
            The MD5 hash
        """
        bytes_val = json.dumps(payload)
        hash_val = hashlib.md5(bytes_val).hexdigest()

        return hash_val

    @staticmethod
    def generate_sha256_hash(payload: JsonType) -> str:
        """
        Generate a SHA256 hash from the given payload

        Parameters
        ----------
        payload : JsonType
            The payload to be hashed

        Returns
        -------
        str
            The SHA256 hash
        """
        bytes_val = json.dumps(payload)
        hash_val = hashlib.sha256(bytes_val).hexdigest()

        return hash_val
