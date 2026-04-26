"""Tests for AzureBlobStore implementation."""

import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ayuna_core.basetypes import AyunaError
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from ayuna_dostore import AzureBlobDoStoreConfig
from ayuna_dostore.azure_blob import AzureBlobStore


async def _async_blobs(*items):
    """Async generator helper for mocking list_blobs."""
    for item in items:
        yield item


async def make_azure_store(
    container_exists: bool = True,
) -> tuple[AzureBlobStore, AsyncMock, AsyncMock]:
    """
    Create an AzureBlobStore with mocked Azure SDK clients.

    Returns (store, mock_service_client, mock_container_client).
    The store is fully initialized.
    """
    loop = asyncio.get_running_loop()
    config = AzureBlobDoStoreConfig(
        account_url="https://testaccount.blob.core.windows.net/",
        container_name="test-container",
        connection_string="AccountName=test;AccountKey=dGVzdA==",
    )

    mock_container_client = AsyncMock()
    mock_service_client = AsyncMock()

    # get_container_client is a sync call on service_client
    mock_service_client.get_container_client = MagicMock(
        return_value=mock_container_client
    )

    if not container_exists:
        mock_container_client.get_container_properties.side_effect = (
            ResourceNotFoundError("not found")
        )
        new_container_client = AsyncMock()
        mock_service_client.create_container = AsyncMock(
            return_value=new_container_client
        )
        # Replace mock_container_client reference for the returned store
        mock_container_client = new_container_client # NOSONAR

    with patch("ayuna_dostore.azure_blob.BlobServiceClient") as mock_bsc_class:
        mock_bsc_class.from_connection_string.return_value = mock_service_client
        store = AzureBlobStore(config=config, aio_loop=loop)
        await store._ensure_initialized()

    return store, mock_service_client, store._container_client


class TestAzureBlobStoreInit:
    """Tests for AzureBlobStore initialization."""

    async def test_typid_is_azure_blob(self):
        store, _, _ = await make_azure_store()
        assert store._config.typid == "azure-blob"
        await store.close()

    async def test_initialized_flag_set(self):
        store, _, _ = await make_azure_store()
        assert store._initialized is True
        await store.close()

    async def test_idempotent_ensure_initialized(self):
        store, mock_service_client, _ = await make_azure_store()

        # Calling again should be a no-op (initialized flag is True)
        call_count_before = mock_service_client.get_container_client.call_count
        await store._ensure_initialized()
        assert mock_service_client.get_container_client.call_count == call_count_before
        await store.close()

    async def test_azure_key_credential_raises_on_init(self):
        loop = asyncio.get_running_loop()
        from ayuna_creds.azure_config import CredConfigAuto as AzureCredConfigAuto

        config = AzureBlobDoStoreConfig(
            account_url="https://testaccount.blob.core.windows.net/",
            container_name="test-container",
            cred_config=AzureCredConfigAuto(),
        )

        from azure.core.credentials import AzureKeyCredential

        with (
            patch("ayuna_dostore.azure_blob.CredProvider") as mock_provider_class,
            patch("ayuna_dostore.azure_blob.BlobServiceClient"),
        ):
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.resolve_credential.return_value = AzureKeyCredential("key")

            store = AzureBlobStore(config=config, aio_loop=loop)

            with pytest.raises(AyunaError):
                await store._ensure_initialized()


class TestAzureBlobStoreGet:
    """Tests for AzureBlobStore.get_object() and get_objects()."""

    async def test_get_existing_object(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_stream = AsyncMock()
        mock_stream.readall.return_value = b"blob content"
        mock_blob_client.download_blob.return_value = mock_stream
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        result = await store.get_object("myblob")
        assert isinstance(result, BytesIO)
        assert result.getvalue() == b"blob content"
        await store.close()

    async def test_get_object_error_returns_ayuna_error(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_blob_client.download_blob.side_effect = ResourceNotFoundError("not found")
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        result = await store.get_object("missing")
        assert isinstance(result, AyunaError)
        await store.close()

    async def test_get_objects_empty_keys_yields_error(self):
        store, _, _ = await make_azure_store()
        results = [r async for r in store.get_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)
        await store.close()

    async def test_get_objects_bulk(self):
        store, _, mock_container_client = await make_azure_store()

        def _make_blob_client(data: bytes) -> AsyncMock:
            bc = AsyncMock()
            stream = AsyncMock()
            stream.readall.return_value = data
            bc.download_blob.return_value = stream
            return bc

        mock_container_client.get_blob_client = MagicMock(
            side_effect=[_make_blob_client(b"aaa"), _make_blob_client(b"bbb")]
        )

        results = [r async for r in store.get_objects(["a", "b"])]
        assert len(results) == 2
        assert all(isinstance(r, BytesIO) for r in results)
        await store.close()


class TestAzureBlobStorePut:
    """Tests for AzureBlobStore.put_object() and put_objects()."""

    async def test_put_new_object_succeeds(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_blob_client.upload_blob.return_value = {"etag": "test-etag"}
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        result = await store.put_object("newblob", BytesIO(b"data"))
        assert isinstance(result, str)
        assert "Written" in result
        mock_blob_client.upload_blob.assert_called_once()
        await store.close()

    async def test_put_existing_object_returns_error(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_blob_client.upload_blob.side_effect = ResourceExistsError("exists")
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        result = await store.put_object("existingblob", BytesIO(b"data"))
        assert isinstance(result, AyunaError)
        assert "already exists" in str(result)
        await store.close()

    async def test_put_with_overwrite_passes_flag(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        await store.put_object("key", BytesIO(b"data"), overwrite=True)
        mock_blob_client.upload_blob.assert_called_once_with(b"data", overwrite=True)
        await store.close()

    async def test_put_objects_empty_entries_yields_error(self):
        store, _, _ = await make_azure_store()
        results = [r async for r in store.put_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)
        await store.close()

    async def test_put_objects_bulk(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        entries = [("a", BytesIO(b"aaa"), False), ("b", BytesIO(b"bbb"), False)]
        results = [r async for r in store.put_objects(entries)]
        assert all(isinstance(r, str) for r in results)
        assert mock_blob_client.upload_blob.call_count == 2
        await store.close()


class TestAzureBlobStoreDelete:
    """Tests for AzureBlobStore.delete_object() and delete_objects()."""

    async def test_delete_object_succeeds(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        result = await store.delete_object("myblob")
        assert isinstance(result, str)
        assert "Deleted" in result
        mock_blob_client.delete_blob.assert_called_once()
        await store.close()

    async def test_delete_object_error_returns_ayuna_error(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_blob_client.delete_blob.side_effect = ResourceNotFoundError("not found")
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        result = await store.delete_object("missing")
        assert isinstance(result, AyunaError)
        await store.close()

    async def test_delete_objects_empty_keys_yields_error(self):
        store, _, _ = await make_azure_store()
        results = [r async for r in store.delete_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)
        await store.close()

    async def test_delete_objects_bulk(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        results = [r async for r in store.delete_objects(["a", "b"])]
        assert all(isinstance(r, str) for r in results)
        assert mock_blob_client.delete_blob.call_count == 2
        await store.close()


class TestAzureBlobStoreMisc:
    """Tests for AzureBlobStore.object_exists() and total_objects()."""

    async def test_object_exists_true(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_blob_client.exists.return_value = True
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        assert await store.object_exists("myblob") is True
        await store.close()

    async def test_object_exists_false(self):
        store, _, mock_container_client = await make_azure_store()

        mock_blob_client = AsyncMock()
        mock_blob_client.exists.return_value = False
        mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)

        assert await store.object_exists("missing") is False
        await store.close()

    async def test_total_objects_empty_container(self):
        store, _, mock_container_client = await make_azure_store()
        # list_blobs is a sync method returning an async iterable, not a coroutine
        mock_container_client.list_blobs = MagicMock(return_value=_async_blobs())

        assert await store.total_objects() == 0
        await store.close()

    async def test_total_objects_counts_blobs(self):
        store, _, mock_container_client = await make_azure_store()
        mock_container_client.list_blobs = MagicMock(
            return_value=_async_blobs(MagicMock(), MagicMock(), MagicMock())
        )

        assert await store.total_objects() == 3
        await store.close()
