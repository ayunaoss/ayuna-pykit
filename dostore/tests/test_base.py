"""Tests for base DoStore config models and factory."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from ayuna_creds.aws_config import CredConfigAuto as AwsCredConfigAuto
from ayuna_creds.gcp_config import CredConfigAuto as GcpCredConfigAuto
from pydantic import ValidationError

from ayuna_dostore import (
    AwsS3DoStoreConfig,
    AzureBlobDoStoreConfig,
    BaseDoStore,
    GCSDoStoreConfig,
    UnixFsDoStoreConfig,
    UnixFsStore,
)


class TestUnixFsDoStoreConfig:
    """Tests for UnixFsDoStoreConfig model."""

    def test_default_typid(self, tmp_path):
        config = UnixFsDoStoreConfig(sroot=str(tmp_path))
        assert config.typid == "unix-fs"

    def test_is_readonly_defaults_to_false(self, tmp_path):
        config = UnixFsDoStoreConfig(sroot=str(tmp_path))
        assert config.is_readonly is False

    def test_relative_sroot_raises(self):
        with pytest.raises(ValidationError, match="absolute"):
            UnixFsDoStoreConfig(sroot="relative/path")

    def test_trailing_slash_raises(self):
        with pytest.raises(ValidationError, match="slash"):
            UnixFsDoStoreConfig(sroot="/some/path/")

    def test_empty_sroot_raises(self):
        with pytest.raises(ValidationError):
            UnixFsDoStoreConfig(sroot="")


class TestAwsS3DoStoreConfig:
    """Tests for AwsS3DoStoreConfig model."""

    def test_default_typid(self):
        config = AwsS3DoStoreConfig(
            bucket_name="my-bucket",
            cred_config=AwsCredConfigAuto(),
        )
        assert config.typid == "aws-s3"

    def test_default_endpoint(self):
        config = AwsS3DoStoreConfig(
            bucket_name="my-bucket",
            cred_config=AwsCredConfigAuto(),
        )
        assert config.endpoint == "s3.amazonaws.com"

    def test_empty_bucket_name_raises(self):
        with pytest.raises(ValidationError):
            AwsS3DoStoreConfig(bucket_name="", cred_config=AwsCredConfigAuto())


class TestAzureBlobDoStoreConfig:
    """Tests for AzureBlobDoStoreConfig model."""

    def test_default_typid(self):
        config = AzureBlobDoStoreConfig(
            account_url="https://test.blob.core.windows.net/",
            container_name="my-container",
            connection_string="AccountName=test;AccountKey=dGVzdA==",
        )
        assert config.typid == "azure-blob"

    def test_missing_connection_string_and_cred_config_raises(self):
        with pytest.raises(ValidationError, match="connection_string or cred_config"):
            AzureBlobDoStoreConfig(
                account_url="https://test.blob.core.windows.net/",
                container_name="my-container",
            )

    def test_empty_container_name_raises(self):
        with pytest.raises(ValidationError):
            AzureBlobDoStoreConfig(
                account_url="https://test.blob.core.windows.net/",
                container_name="",
                connection_string="AccountName=test;AccountKey=dGVzdA==",
            )


class TestGCSDoStoreConfig:
    """Tests for GCSDoStoreConfig model."""

    def test_default_typid(self):
        config = GCSDoStoreConfig(
            project_id="my-project",
            bucket_name="my-bucket",
            cred_config=GcpCredConfigAuto(),
        )
        assert config.typid == "gcp-storage"

    def test_empty_project_id_raises(self):
        with pytest.raises(ValidationError):
            GCSDoStoreConfig(
                project_id="",
                bucket_name="my-bucket",
                cred_config=GcpCredConfigAuto(),
            )

    def test_empty_bucket_name_raises(self):
        with pytest.raises(ValidationError):
            GCSDoStoreConfig(
                project_id="my-project",
                bucket_name="",
                cred_config=GcpCredConfigAuto(),
            )


class TestBaseDoStoreFactory:
    """Tests for BaseDoStore.create() factory method."""

    async def test_create_unix_fs(self, tmp_path):
        loop = asyncio.get_running_loop()
        config = UnixFsDoStoreConfig(sroot=str(tmp_path))
        store = BaseDoStore.create(config, loop)

        assert isinstance(store, UnixFsStore)
        await store.close()

    async def test_create_unknown_typid_raises(self): # NOSONAR
        loop = asyncio.get_running_loop()
        config = MagicMock()
        config.typid = "nonexistent-backend"

        with pytest.raises(ValueError, match="Unknown store type"):
            BaseDoStore.create(config, loop)

    async def test_create_aws_s3(self): # NOSONAR
        loop = asyncio.get_running_loop()
        config = AwsS3DoStoreConfig(
            bucket_name="test-bucket",
            cred_config=AwsCredConfigAuto(),
        )

        with patch("ayuna_dostore.aws_s3.AwsS3Store") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            result = BaseDoStore.create(config, loop)

        assert result is mock_instance

    async def test_create_gcp(self): # NOSONAR
        loop = asyncio.get_running_loop()
        config = GCSDoStoreConfig(
            project_id="my-project",
            bucket_name="my-bucket",
            cred_config=GcpCredConfigAuto(),
        )

        with patch("ayuna_dostore.google_cs.GoogleCloudStore") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            result = BaseDoStore.create(config, loop)

        assert result is mock_instance

    async def test_create_azure(self): # NOSONAR
        loop = asyncio.get_running_loop()
        config = AzureBlobDoStoreConfig(
            account_url="https://test.blob.core.windows.net/",
            container_name="my-container",
            connection_string="AccountName=test;AccountKey=dGVzdA==",
        )

        with patch("ayuna_dostore.azure_blob.AzureBlobStore") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            result = BaseDoStore.create(config, loop)

        assert result is mock_instance


class TestBaseDoStoreHelpers:
    """Tests for BaseDoStore utility methods."""

    async def test_object_basename_with_path(self, tmp_path):
        loop = asyncio.get_running_loop()
        store = UnixFsStore(
            config=UnixFsDoStoreConfig(sroot=str(tmp_path)),
            aio_loop=loop,
        )
        assert store.object_basename("some/path/file.txt") == "file.txt"
        await store.close()

    async def test_object_basename_no_directory(self, tmp_path):
        loop = asyncio.get_running_loop()
        store = UnixFsStore(
            config=UnixFsDoStoreConfig(sroot=str(tmp_path)),
            aio_loop=loop,
        )
        assert store.object_basename("file.txt") == "file.txt"
        await store.close()

    async def test_object_dirname(self, tmp_path):
        loop = asyncio.get_running_loop()
        store = UnixFsStore(
            config=UnixFsDoStoreConfig(sroot=str(tmp_path)),
            aio_loop=loop,
        )
        assert store.object_dirname("some/path/file.txt") == "some/path"
        await store.close()

    async def test_store_id_is_deterministic(self, tmp_path):
        loop = asyncio.get_running_loop()
        config = UnixFsDoStoreConfig(sroot=str(tmp_path))
        store1 = UnixFsStore(config=config, aio_loop=loop)
        store2 = UnixFsStore(config=config, aio_loop=loop)

        assert store1.store_id == store2.store_id
        await store1.close()
        await store2.close()
