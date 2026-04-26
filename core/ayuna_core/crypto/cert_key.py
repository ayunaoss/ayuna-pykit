#!/usr/bin/env python3
"""
cert_key.py - Certificate and encryption utilities for the Ayuna framework.

This module provides functions for:

- Encrypting secrets using hybrid RSA+AES encryption
- Decrypting secrets with RSA private keys
- Generating self-signed X.509 certificates and RSA key pairs

Encryption Scheme
-----------------
1. Generate a random 256-bit AES key and 128-bit IV
2. Encrypt the secret with AES-256-CBC
3. Encrypt the AES key with RSA-OAEP (SHA256)
4. Return the IV, encrypted key, and encrypted data (all base64-encoded)

This hybrid approach allows encrypting large data while benefiting from
RSA's public-key cryptography for key distribution.
"""

import base64
import os
from datetime import timedelta
from typing import List

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.x509.oid import NameOID

from ayuna_core.fileops import read_bytes, write_bytes
from ayuna_core.utils.chrono import Chrono

from .models import (
    CertificateInfo,
    CertKeyOutput,
    DecryptionInfo,
    EncryptedData,
    EncryptedDataSet,
    EncryptedItem,
    UnencryptedItem,
)


# =============================================================================
# Encryption Functions
# =============================================================================
def encrypt_secret_with_cert_data(*, secret: str, pem_cert_data: bytes):
    """
    Encrypts a secret using a certificate's public key

    Parameters
    ----------
    secret : str
        Secret to encrypt
    pem_cert_data : bytes
        PEM encoded certificate data

    Returns
    -------
    EncryptedData
        Encrypted data containing the encrypted secret and AES key
    """
    public_key = x509.load_pem_x509_certificate(pem_cert_data).public_key()
    aes_key = os.urandom(32)
    init_vector = os.urandom(12)

    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(init_vector))
    encryptor = cipher.encryptor()
    encrypted_secret = encryptor.update(secret.encode()) + encryptor.finalize()
    tag = encryptor.tag

    assert isinstance(public_key, rsa.RSAPublicKey), "Public key is not an RSA key"

    encrypted_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    return EncryptedData(
        init_vector=base64.b64encode(init_vector).decode(),
        encrypted_key=base64.b64encode(encrypted_key).decode(),
        encrypted_secret=base64.b64encode(encrypted_secret + tag).decode(),
    )


def encrypt_secrets_with_cert_data(
    *, secrets: List[UnencryptedItem], pem_cert_data: bytes
):
    """
    Encrypts a data set using a certificate's public key

    Parameters
    ----------
    secrets : List[UnencryptedItem]
        List of secret items to encrypt
    pem_cert_data : bytes
        PEM encoded certificate data

    Returns
    -------
    EncryptedDataSet
        Encrypted data set containing the encrypted items and AES key
    """
    public_key = x509.load_pem_x509_certificate(pem_cert_data).public_key()
    aes_key = os.urandom(32)
    init_vector = os.urandom(12)
    encrypted_items: List[EncryptedItem] = []

    assert isinstance(public_key, rsa.RSAPublicKey), "Public key is not an RSA key"

    for secret in secrets:
        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(init_vector))
        encryptor = cipher.encryptor()
        encrypted_secret = (
            encryptor.update(secret.value.encode()) + encryptor.finalize()
        )
        tag = encryptor.tag
        encrypted_items.append(
            EncryptedItem(
                name=secret.name,
                value=base64.b64encode(encrypted_secret + tag).decode(),
            )
        )

    return EncryptedDataSet(
        init_vector=base64.b64encode(init_vector).decode(),
        encrypted_key=base64.b64encode(
            public_key.encrypt(
                aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
        ).decode(),
        encrypted_items=encrypted_items,
    )


def encrypt_secret_with_cert_path(*, secret: str, pem_cert_path: str):
    """
    Encrypts a secret using a certificate's public key

    Parameters
    ----------
    secret : str
        Secret to encrypt
    pem_cert_path : str
        Path to the PEM encoded certificate

    Returns
    -------
    EncryptedData
        Encrypted data containing the encrypted secret and AES key
    """
    pem_cert_data = read_bytes(pem_cert_path)
    return encrypt_secret_with_cert_data(secret=secret, pem_cert_data=pem_cert_data)


def encrypt_secrets_with_cert_path(
    *, secrets: List[UnencryptedItem], pem_cert_path: str
):
    """
    Encrypts a data set using a certificate's public key

    Parameters
    ----------
    secrets : List[UnencryptedItem]
        Secret items to encrypt
    pem_cert_path : str
        Path to the PEM encoded certificate

    Returns
    -------
    EncryptedDataSet
        Encrypted data set containing the encrypted items and AES key
    """
    pem_cert_data = read_bytes(pem_cert_path)
    return encrypt_secrets_with_cert_data(secrets=secrets, pem_cert_data=pem_cert_data)


def decrypt_secret(*, encrypted_data: EncryptedData, decrypt_info: DecryptionInfo):
    """
    Decrypts a secret using a private key.

    Parameters
    ----------
    encrypted_data : EncryptedData
        Encrypted data containing the encrypted secret and AES key.
    decrypt_info : DecryptionInfo
        Private key information.

    Returns
    -------
    str
        Decrypted secret.
    """
    private_key = serialization.load_pem_private_key(
        decrypt_info.pem_key.encode(),
        password=decrypt_info.password.encode() if decrypt_info.password else None,
    )

    init_vector = base64.b64decode(encrypted_data.init_vector)
    encrypted_key = base64.b64decode(encrypted_data.encrypted_key)
    encrypted_secret_with_tag = base64.b64decode(encrypted_data.encrypted_secret)

    assert isinstance(private_key, rsa.RSAPrivateKey), "Private key is not an RSA key"

    aes_key = private_key.decrypt(
        encrypted_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    encrypted_secret = encrypted_secret_with_tag[:-16]
    tag = encrypted_secret_with_tag[-16:]
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(init_vector, tag))
    decryptor = cipher.decryptor()
    secret = decryptor.update(encrypted_secret) + decryptor.finalize()

    return secret.decode()


def decrypt_secrets(
    *, encrypted_secrets: EncryptedDataSet, decrypt_info: DecryptionInfo
):
    """
    Decrypts a data set using a private key

    Parameters
    ----------
    encrypted_secrets : EncryptedDataSet
        Encrypted data set containing the encrypted items and AES key
    decrypt_info : DecryptionInfo
        Private key information.

    Returns
    -------
    List[UnencryptedItem]
        Decrypted secret items
    """
    private_key = serialization.load_pem_private_key(
        decrypt_info.pem_key.encode(),
        password=decrypt_info.password.encode() if decrypt_info.password else None,
    )

    init_vector = base64.b64decode(encrypted_secrets.init_vector)
    encrypted_key = base64.b64decode(encrypted_secrets.encrypted_key)

    assert isinstance(private_key, rsa.RSAPrivateKey), "Private key is not an RSA key"

    aes_key = private_key.decrypt(
        encrypted_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    secret_items: List[UnencryptedItem] = []

    for encrypted_item in encrypted_secrets.encrypted_items:
        encrypted_secret_with_tag = base64.b64decode(encrypted_item.value)
        encrypted_secret = encrypted_secret_with_tag[:-16]
        tag = encrypted_secret_with_tag[-16:]
        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(init_vector, tag))
        decryptor = cipher.decryptor()
        secret = decryptor.update(encrypted_secret) + decryptor.finalize()

        secret_items.append(
            UnencryptedItem(
                name=encrypted_item.name,
                value=secret.decode(),
            )
        )

    return secret_items


def generate_cert_key_pair(*, cert_info: CertificateInfo, output: CertKeyOutput):
    """
    Generates a certificate and a private key in PEM format

    Parameters
    ----------
    cert_info : CertificateInfo
        Information about the certificate
    output : CertKeyOutput
        Output file paths and password for the private key

    Returns
    -------
    None
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, cert_info.country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, cert_info.state),
            x509.NameAttribute(NameOID.LOCALITY_NAME, cert_info.locality),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, cert_info.organization),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, cert_info.department),
            x509.NameAttribute(NameOID.COMMON_NAME, cert_info.common_name),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(issuer)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(Chrono.get_current_utc_time())
        .not_valid_after(Chrono.get_current_utc_time() + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    encryption = serialization.NoEncryption()

    if output.password:
        encryption = serialization.BestAvailableEncryption(
            password=output.password.encode()
        )

    write_bytes(
        output.pem_key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            encryption,
        ),
        overwrite=output.overwrite,
    )

    write_bytes(
        output.pem_cert_path,
        cert.public_bytes(serialization.Encoding.PEM),
        overwrite=output.overwrite,
    )
