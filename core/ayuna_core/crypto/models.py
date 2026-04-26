"""
models.py - Data models for cryptographic operations.

This module provides Pydantic models for representing:

- Encrypted data with AES encryption and RSA key wrapping
- Certificate information for X.509 certificate generation
- Configuration for encryption/decryption operations

The encryption scheme uses:
- AES-256-CBC for data encryption
- RSA-OAEP for key wrapping
- Base64 encoding for serialization
"""

from typing import List

from ayuna_core.basetypes import CoreData
from pydantic import Field

# =============================================================================
# Encrypted Data Models
# =============================================================================


class EncryptedData(CoreData):
    """
    Model representing encrypted data using hybrid encryption.

    Data is encrypted with a random AES key, which is then encrypted
    with the recipient's RSA public key. Both are base64-encoded.

    Attributes
    ----------
    init_vector : str
        Base64-encoded initialization vector for AES-CBC.
    encrypted_key : str
        Base64-encoded AES key encrypted with RSA-OAEP.
    encrypted_secret : str
        Base64-encoded AES-encrypted data.
    """

    init_vector: str = Field(description="Initialization vector")
    encrypted_key: str = Field(description="Encrypted AES key")
    encrypted_secret: str = Field(description="Encrypted secret")


class UnencryptedItem(CoreData):
    """
    Model representing a named secret value before encryption.

    Attributes
    ----------
    name : str
        Identifier for the secret.
    value : str
        Plaintext secret value.
    """

    name: str = Field(description="Secret name")
    value: str = Field(description="Non-encrypted string value")


class EncryptedItem(CoreData):
    """
    Model representing a named secret value after encryption.

    Attributes
    ----------
    name : str
        Identifier for the secret.
    value : str
        Base64-encoded encrypted secret value.
    """

    name: str = Field(description="Secret name")
    value: str = Field(description="Encrypted string value")


class EncryptedDataSet(CoreData):
    """
    Model representing multiple encrypted secrets sharing one AES key.

    All items are encrypted with the same AES key and IV, which are
    then wrapped with RSA. More efficient than encrypting each item
    with its own key.

    Attributes
    ----------
    init_vector : str
        Base64-encoded initialization vector for AES-CBC.
    encrypted_key : str
        Base64-encoded AES key encrypted with RSA-OAEP.
    encrypted_items : List[EncryptedItem]
        List of encrypted name-value pairs.
    """

    init_vector: str = Field(description="Initialization vector")
    encrypted_key: str = Field(description="Encrypted AES key")
    encrypted_items: List[EncryptedItem] = Field(description="Encrypted secret items")


# =============================================================================
# Certificate Models
# =============================================================================


class CertificateInfo(CoreData):
    """
    Model for X.509 certificate subject information.

    Contains the distinguished name (DN) components for
    certificate generation.

    Attributes
    ----------
    country : str
        Two-letter country code (default: "IN").
    state : str
        State or province (default: "KA").
    locality : str
        City or locality (default: "Bengaluru").
    organization : str
        Organization name (default: "Ayuna").
    department : str
        Organizational unit/department (default: "Secrets").
    common_name : str
        Common name (CN) - typically the domain or identifier.
    """

    country: str = Field(default="IN", description="Country name")
    state: str = Field(default="KA", description="State name")
    locality: str = Field(default="Bengaluru", description="Locality name")
    organization: str = Field(default="Ayuna", description="Organization name")
    department: str = Field(default="Secrets", description="Department name")
    common_name: str = Field(description="Common name")


class CertKeyOutput(CoreData):
    """
    Configuration for certificate/key file output.

    Attributes
    ----------
    password : str | None
        Optional password to encrypt the private key.
    pem_cert_path : str
        Path where the PEM certificate will be saved.
    pem_key_path : str
        Path where the PEM private key will be saved.
    overwrite : bool
        Whether to overwrite existing files (default: False).
    """

    password: str | None = Field(default=None, description="Password for private key")
    pem_cert_path: str = Field(description="Certificate filename to save in PEM format")
    pem_key_path: str = Field(description="Private key filename to save in PEM format")
    overwrite: bool = Field(default=False, description="Overwrite existing files")


class DecryptionInfo(CoreData):
    """
    Configuration for decryption operations.

    Attributes
    ----------
    password : str | None
        Password for encrypted private key (None if unencrypted).
    pem_key : str
        PEM-encoded private key string.
    """

    password: str | None = Field(default=None, description="Password for private key")
    pem_key: str = Field(description="Private key in PEM format")
