"""Tests for GoogleCloudStore implementation."""

import asyncio
from io import BytesIO
from unittest.mock import MagicMock, patch

from ayuna_core.basetypes import AyunaError
from ayuna_creds.gcp_config import CredConfigAuto as GcpCredConfigAuto
from google.api_core.exceptions import Conflict, NotFound

from ayuna_dostore import GCSDoStoreConfig
from ayuna_dostore.google_cs import GoogleCloudStore


async def make_gcs_store( # NOSONAR
    bucket_exists: bool = True,
) -> tuple[GoogleCloudStore, MagicMock, MagicMock]:
    """
    Create a GoogleCloudStore with mocked GCP SDK clients.

    Returns (store, mock_client, mock_bucket).
    """
    loop = asyncio.get_running_loop()
    config = GCSDoStoreConfig(
        project_id="test-project",
        bucket_name="test-bucket",
        cred_config=GcpCredConfigAuto(),
    )

    mock_bucket = MagicMock()
    mock_client = MagicMock()

    if bucket_exists:
        mock_client.get_bucket.return_value = mock_bucket
    else:
        mock_client.get_bucket.side_effect = NotFound("not found")
        mock_client.create_bucket.return_value = mock_bucket

    with (
        patch("ayuna_dostore.google_cs.CredProvider") as mock_provider_class,
        patch("ayuna_dostore.google_cs.storage") as mock_storage,
    ):
        mock_provider = MagicMock()
        mock_provider_class.return_value = mock_provider
        mock_provider.resolve_credentials.return_value = MagicMock()
        mock_storage.Client.return_value = mock_client

        store = GoogleCloudStore(config=config, aio_loop=loop)

    return store, mock_client, mock_bucket


class TestGCSStoreInit:
    """Tests for GoogleCloudStore initialization."""

    async def test_typid_is_gcp_storage(self):
        store, _, _ = await make_gcs_store()
        assert store._config.typid == "gcp-storage"
        await store.close()

    async def test_existing_bucket_used_directly(self):
        store, mock_client, mock_bucket = await make_gcs_store(bucket_exists=True)
        assert store._bucket is mock_bucket
        mock_client.create_bucket.assert_not_called()
        await store.close()

    async def test_missing_bucket_created(self):
        store, mock_client, _ = await make_gcs_store(bucket_exists=False)
        mock_client.create_bucket.assert_called_once_with("test-bucket")
        await store.close()

    async def test_race_condition_on_create_falls_back_to_get(self):
        loop = asyncio.get_running_loop()
        config = GCSDoStoreConfig(
            project_id="p",
            bucket_name="b",
            cred_config=GcpCredConfigAuto(),
        )
        mock_bucket = MagicMock()
        mock_client = MagicMock()
        mock_client.get_bucket.side_effect = [NotFound("missing"), mock_bucket]
        mock_client.create_bucket.side_effect = Conflict("conflict")

        with (
            patch("ayuna_dostore.google_cs.CredProvider") as mock_provider_class,
            patch("ayuna_dostore.google_cs.storage") as mock_storage,
        ):
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.resolve_credentials.return_value = MagicMock()
            mock_storage.Client.return_value = mock_client

            store = GoogleCloudStore(config=config, aio_loop=loop)

        # Second get_bucket call should have returned the bucket
        assert mock_client.get_bucket.call_count == 2
        await store.close()

    async def test_object_store_path(self):
        store, _, _ = await make_gcs_store()
        assert store.object_store_path("my/key") == "test-bucket/my/key"
        await store.close()


class TestGCSStoreGet:
    """Tests for GoogleCloudStore.get_object() and get_objects()."""

    async def test_get_existing_object(self):
        store, _, mock_bucket = await make_gcs_store()

        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"hello gcs"
        mock_bucket.blob.return_value = mock_blob

        result = await store.get_object("mykey")
        assert isinstance(result, BytesIO)
        assert result.getvalue() == b"hello gcs"
        await store.close()

    async def test_get_missing_object_returns_error(self):
        store, _, mock_bucket = await make_gcs_store()

        mock_blob = MagicMock()
        mock_blob.download_as_bytes.side_effect = NotFound("not found")
        mock_bucket.blob.return_value = mock_blob

        result = await store.get_object("missing")
        assert isinstance(result, AyunaError)
        await store.close()

    async def test_get_objects_empty_keys_yields_error(self):
        store, _, _ = await make_gcs_store()
        results = [r async for r in store.get_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)
        await store.close()

    async def test_get_objects_bulk(self):
        store, _, mock_bucket = await make_gcs_store()

        blobs = [MagicMock(), MagicMock()]
        blobs[0].download_as_bytes.return_value = b"aaa"
        blobs[1].download_as_bytes.return_value = b"bbb"
        mock_bucket.blob.side_effect = blobs

        results = [r async for r in store.get_objects(["a", "b"])]
        assert len(results) == 2
        assert all(isinstance(r, BytesIO) for r in results)
        await store.close()


class TestGCSStorePut:
    """Tests for GoogleCloudStore.put_object() and put_objects()."""

    async def test_put_new_object_succeeds(self):
        store, _, mock_bucket = await make_gcs_store()

        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob

        result = await store.put_object("newkey", BytesIO(b"data"))
        assert isinstance(result, str)
        assert "Written" in result
        mock_blob.upload_from_string.assert_called_once()
        await store.close()

    async def test_put_existing_object_returns_error(self):
        store, _, mock_bucket = await make_gcs_store()

        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob

        result = await store.put_object("existingkey", BytesIO(b"data"))
        assert isinstance(result, AyunaError)
        assert "already exists" in str(result)
        mock_blob.upload_from_string.assert_not_called()
        await store.close()

    async def test_put_with_overwrite_skips_exists_check(self):
        store, _, mock_bucket = await make_gcs_store()

        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        result = await store.put_object("key", BytesIO(b"data"), overwrite=True)
        assert isinstance(result, str)
        mock_blob.exists.assert_not_called()
        mock_blob.upload_from_string.assert_called_once()
        await store.close()

    async def test_put_objects_empty_entries_yields_error(self):
        store, _, _ = await make_gcs_store()
        results = [r async for r in store.put_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)
        await store.close()

    async def test_put_objects_bulk(self):
        store, _, mock_bucket = await make_gcs_store()

        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob

        entries = [("a", BytesIO(b"aaa"), False), ("b", BytesIO(b"bbb"), False)]
        results = [r async for r in store.put_objects(entries)]
        assert all(isinstance(r, str) for r in results)
        await store.close()


class TestGCSStoreDelete:
    """Tests for GoogleCloudStore.delete_object() and delete_objects()."""

    async def test_delete_object_succeeds(self):
        store, _, mock_bucket = await make_gcs_store()

        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        result = await store.delete_object("mykey")
        assert isinstance(result, str)
        assert "Deleted" in result
        mock_blob.delete.assert_called_once()
        await store.close()

    async def test_delete_object_error_returns_error(self):
        store, _, mock_bucket = await make_gcs_store()

        mock_blob = MagicMock()
        mock_blob.delete.side_effect = NotFound("not found")
        mock_bucket.blob.return_value = mock_blob

        result = await store.delete_object("missing")
        assert isinstance(result, AyunaError)
        await store.close()

    async def test_delete_objects_empty_keys_yields_error(self):
        store, _, _ = await make_gcs_store()
        results = [r async for r in store.delete_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)
        await store.close()

    async def test_delete_objects_bulk(self):
        store, _, mock_bucket = await make_gcs_store()
        mock_bucket.blob.return_value = MagicMock()

        results = [r async for r in store.delete_objects(["a", "b"])]
        assert all(isinstance(r, str) for r in results)
        await store.close()


class TestGCSStoreMisc:
    """Tests for GoogleCloudStore.object_exists() and total_objects()."""

    async def test_object_exists_true(self):
        store, _, mock_bucket = await make_gcs_store()

        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob

        assert await store.object_exists("mykey") is True
        await store.close()

    async def test_object_exists_false(self):
        store, _, mock_bucket = await make_gcs_store()

        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob

        assert await store.object_exists("missing") is False
        await store.close()

    async def test_total_objects_empty_bucket(self):
        store, mock_client, _ = await make_gcs_store()
        mock_client.list_blobs.return_value = iter([])

        assert await store.total_objects() == 0
        await store.close()

    async def test_total_objects_counts_blobs(self):
        store, mock_client, _ = await make_gcs_store()
        mock_client.list_blobs.return_value = iter(
            [MagicMock(), MagicMock(), MagicMock()]
        )

        assert await store.total_objects() == 3
        await store.close()
