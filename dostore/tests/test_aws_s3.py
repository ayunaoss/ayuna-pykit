"""Tests for AwsS3Store implementation."""

import asyncio
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from ayuna_core.basetypes import AyunaError
from ayuna_creds.aws_config import CredConfigAuto as AwsCredConfigAuto
from botocore.exceptions import ClientError

from ayuna_dostore import AwsS3DoStoreConfig
from ayuna_dostore.aws_s3 import AwsS3Store


def _s3_error(code: str, op: str = "HeadBucket") -> ClientError:
    """Create a ClientError with the given error code."""
    return ClientError({"Error": {"Code": code, "Message": "error"}}, op)


async def make_s3_store( # NOSONAR
    bucket_exists: bool = True,
) -> tuple[AwsS3Store, MagicMock]:
    """Create an AwsS3Store with mocked boto3 session and S3 client."""
    loop = asyncio.get_running_loop()
    config = AwsS3DoStoreConfig(
        bucket_name="test-bucket",
        cred_config=AwsCredConfigAuto(),
    )

    mock_client = MagicMock()
    mock_session = MagicMock()
    mock_session.client.return_value = mock_client

    if not bucket_exists:
        mock_client.head_bucket.side_effect = _s3_error("404", "HeadBucket")

    with patch("ayuna_dostore.aws_s3.CredProvider") as mock_provider_class:
        mock_provider = MagicMock()
        mock_provider_class.return_value = mock_provider
        mock_provider.resolve_session.return_value = mock_session

        store = AwsS3Store(config=config, aio_loop=loop)

    return store, mock_client


class TestAwsS3StoreInit:
    """Tests for AwsS3Store initialization."""

    async def test_typid_is_aws_s3(self):
        store, _ = await make_s3_store()
        assert store._config.typid == "aws-s3"

    async def test_head_bucket_called_on_init(self):
        store, mock_client = await make_s3_store()
        mock_client.head_bucket.assert_called_once_with(Bucket="test-bucket")
        await store.close()

    async def test_bucket_not_found_creates_bucket(self):
        store, mock_client = await make_s3_store(bucket_exists=False)
        mock_client.create_bucket.assert_called_once()
        await store.close()

    async def test_non_404_head_bucket_error_raises(self): # NOSONAR
        config = AwsS3DoStoreConfig(
            bucket_name="test-bucket",
            cred_config=AwsCredConfigAuto(),
        )
        loop = asyncio.get_running_loop()
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_client.head_bucket.side_effect = _s3_error("403", "HeadBucket")

        with patch("ayuna_dostore.aws_s3.CredProvider") as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.resolve_session.return_value = mock_session

            with pytest.raises(ClientError):
                AwsS3Store(config=config, aio_loop=loop)

    async def test_object_store_path(self):
        store, _ = await make_s3_store()
        assert store.object_store_path("my/key") == "test-bucket/my/key"
        await store.close()


class TestAwsS3StoreGet:
    """Tests for AwsS3Store.get_object() and get_objects()."""

    async def test_get_existing_object(self):
        store, mock_client = await make_s3_store()

        mock_body = MagicMock()
        mock_body.read.return_value = b"test content"
        mock_client.get_object.return_value = {"Body": mock_body}

        result = await store.get_object("mykey")
        assert isinstance(result, BytesIO)
        assert result.getvalue() == b"test content"
        await store.close()

    async def test_get_raises_returns_error(self):
        store, mock_client = await make_s3_store()
        mock_client.get_object.side_effect = _s3_error("NoSuchKey", "GetObject")

        result = await store.get_object("missing")
        assert isinstance(result, AyunaError)
        await store.close()

    async def test_get_objects_empty_keys_yields_error(self):
        store, _ = await make_s3_store()
        results = [r async for r in store.get_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)
        await store.close()

    async def test_get_objects_bulk(self):
        store, mock_client = await make_s3_store()

        def _make_body(data):
            body = MagicMock()
            body.read.return_value = data
            return {"Body": body}

        mock_client.get_object.side_effect = [
            _make_body(b"aaa"),
            _make_body(b"bbb"),
        ]

        results = [r async for r in store.get_objects(["a", "b"])]
        assert len(results) == 2
        assert all(isinstance(r, BytesIO) for r in results)
        await store.close()


class TestAwsS3StorePut:
    """Tests for AwsS3Store.put_object() and put_objects()."""

    async def test_put_new_object_succeeds(self):
        store, mock_client = await make_s3_store()
        # head_object raises 404 → object does not exist
        mock_client.head_object.side_effect = _s3_error("404", "HeadObject")

        result = await store.put_object("new_key", BytesIO(b"data"))
        assert isinstance(result, str)
        assert "Written" in result
        mock_client.put_object.assert_called_once()
        await store.close()

    async def test_put_existing_object_returns_error(self):
        store, mock_client = await make_s3_store()
        # head_object succeeds → object already exists
        mock_client.head_object.return_value = {"ContentLength": 4}

        result = await store.put_object("existing_key", BytesIO(b"data"))
        assert isinstance(result, AyunaError)
        assert "already exists" in str(result)
        mock_client.put_object.assert_not_called()
        await store.close()

    async def test_put_with_overwrite_skips_head_check(self):
        store, mock_client = await make_s3_store()

        result = await store.put_object("key", BytesIO(b"data"), overwrite=True)
        assert isinstance(result, str)
        mock_client.head_object.assert_not_called()
        mock_client.put_object.assert_called_once()
        await store.close()

    async def test_put_objects_empty_entries_yields_error(self):
        store, _ = await make_s3_store()
        results = [r async for r in store.put_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)
        await store.close()

    async def test_put_objects_bulk(self):
        store, mock_client = await make_s3_store()
        mock_client.head_object.side_effect = _s3_error("404", "HeadObject")

        entries = [("a", BytesIO(b"aaa"), False), ("b", BytesIO(b"bbb"), False)]
        results = [r async for r in store.put_objects(entries)]
        assert all(isinstance(r, str) for r in results)
        await store.close()


class TestAwsS3StoreDelete:
    """Tests for AwsS3Store.delete_object() and delete_objects()."""

    async def test_delete_object_succeeds(self):
        store, mock_client = await make_s3_store()
        result = await store.delete_object("mykey")

        assert isinstance(result, str)
        assert "Deleted" in result
        mock_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="mykey"
        )
        await store.close()

    async def test_delete_object_sdk_error_returns_error(self):
        store, mock_client = await make_s3_store()
        mock_client.delete_object.side_effect = _s3_error(
            "AccessDenied", "DeleteObject"
        )

        result = await store.delete_object("mykey")
        assert isinstance(result, AyunaError)
        await store.close()

    async def test_delete_objects_empty_keys_yields_error(self):
        store, _ = await make_s3_store()
        results = [r async for r in store.delete_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)
        await store.close()

    async def test_delete_objects_bulk(self):
        store, mock_client = await make_s3_store()
        results = [r async for r in store.delete_objects(["a", "b"])]
        assert all(isinstance(r, str) for r in results)
        assert mock_client.delete_object.call_count == 2
        await store.close()


class TestAwsS3StoreMisc:
    """Tests for AwsS3Store.object_exists() and total_objects()."""

    async def test_object_exists_true(self):
        store, mock_client = await make_s3_store()
        mock_client.head_object.return_value = {"ContentLength": 4}

        assert await store.object_exists("exists") is True
        await store.close()

    async def test_object_exists_false_on_404(self):
        store, mock_client = await make_s3_store()
        mock_client.head_object.side_effect = _s3_error("404", "HeadObject")

        assert await store.object_exists("missing") is False
        await store.close()

    async def test_object_exists_raises_on_non_404_error(self):
        store, mock_client = await make_s3_store()
        mock_client.head_object.side_effect = _s3_error("403", "HeadObject")

        with pytest.raises(ClientError):
            await store.object_exists("key")
        await store.close()

    async def test_total_objects_empty_bucket(self):
        store, mock_client = await make_s3_store()

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{}]  # no Contents key
        mock_client.get_paginator.return_value = mock_paginator

        assert await store.total_objects() == 0
        await store.close()

    async def test_total_objects_counts_across_pages(self):
        store, mock_client = await make_s3_store()

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": "a"}, {"Key": "b"}]},
            {"Contents": [{"Key": "c"}]},
        ]
        mock_client.get_paginator.return_value = mock_paginator

        assert await store.total_objects() == 3
        await store.close()
