"""Tests for UnixFsStore implementation."""

import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from ayuna_core.basetypes import AyunaError

from ayuna_dostore import UnixFsDoStoreConfig, UnixFsStore


@pytest.fixture
async def store(tmp_path: Path):
    """Writable UnixFsStore backed by a temp directory."""
    loop = asyncio.get_running_loop()
    config = UnixFsDoStoreConfig(sroot=str(tmp_path))
    s = UnixFsStore(config=config, aio_loop=loop)
    yield s
    await s.close()


@pytest.fixture
async def readonly_store(tmp_path: Path):
    """Read-only UnixFsStore backed by a temp directory."""
    loop = asyncio.get_running_loop()
    config = UnixFsDoStoreConfig(sroot=str(tmp_path), is_readonly=True)
    s = UnixFsStore(config=config, aio_loop=loop)
    yield s
    await s.close()


class TestUnixFsStoreInit:
    """Tests for UnixFsStore initialization."""

    async def test_typid_is_unix_fs(self, store: UnixFsStore):  # NOSONAR
        assert store._config.typid == "unix-fs"

    async def test_nonexistent_readonly_root_raises(self, tmp_path: Path):  # NOSONAR
        loop = asyncio.get_running_loop()
        config = UnixFsDoStoreConfig(
            sroot=str(tmp_path / "nonexistent"), is_readonly=True
        )

        with pytest.raises(AyunaError, match="not readable"):
            UnixFsStore(config=config, aio_loop=loop)

    async def test_object_store_path_relative_key(  # NOSONAR
        self, store: UnixFsStore, tmp_path: Path
    ):
        assert store.object_store_path("data/file.bin") == f"{tmp_path}/data/file.bin"

    async def test_object_store_path_absolute_key(  # NOSONAR
        self, store: UnixFsStore, tmp_path: Path
    ):
        assert store.object_store_path("/data/file.bin") == f"{tmp_path}/data/file.bin"

    async def test_object_store_path_already_rooted(  # NOSONAR
        self, store: UnixFsStore, tmp_path: Path
    ):
        full_path = f"{tmp_path}/file.bin"
        assert store.object_store_path(full_path) == full_path


class TestUnixFsStoreGet:
    """Tests for UnixFsStore.get_object() and get_objects()."""

    async def test_get_nonexistent_returns_error(self, store: UnixFsStore):
        result = await store.get_object("missing.bin")
        assert isinstance(result, AyunaError)

    async def test_get_existing_object_returns_bytes_io(
        self, store: UnixFsStore, tmp_path: Path
    ):
        data = b"hello world"
        (tmp_path / "test.bin").write_bytes(data)

        result = await store.get_object("test.bin")
        assert isinstance(result, BytesIO)
        assert result.getvalue() == data

    async def test_get_objects_empty_keys_yields_error(self, store: UnixFsStore):
        results = [r async for r in store.get_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)

    async def test_get_objects_bulk(self, store: UnixFsStore, tmp_path: Path):
        (tmp_path / "a.bin").write_bytes(b"aaa")
        (tmp_path / "b.bin").write_bytes(b"bbb")

        results = [r async for r in store.get_objects(["a.bin", "b.bin"])]
        assert len(results) == 2
        assert all(isinstance(r, BytesIO) for r in results)
        values = {r.getvalue() for r in results}
        assert values == {b"aaa", b"bbb"}

    async def test_get_objects_mixed_results(self, store: UnixFsStore, tmp_path: Path):
        (tmp_path / "exists.bin").write_bytes(b"data")

        results = [r async for r in store.get_objects(["exists.bin", "missing.bin"])]
        assert isinstance(results[0], BytesIO)
        assert isinstance(results[1], AyunaError)


class TestUnixFsStorePut:
    """Tests for UnixFsStore.put_object() and put_objects()."""

    async def test_put_new_object_succeeds(self, store: UnixFsStore, tmp_path: Path):
        result = await store.put_object("new.bin", BytesIO(b"test data"))
        assert isinstance(result, str)
        assert "Written" in result
        assert (tmp_path / "new.bin").read_bytes() == b"test data"

    async def test_put_duplicate_returns_error(self, store: UnixFsStore):
        await store.put_object("dup.bin", BytesIO(b"original"))
        result = await store.put_object("dup.bin", BytesIO(b"second"))
        assert isinstance(result, AyunaError)

    async def test_put_with_overwrite_succeeds(
        self, store: UnixFsStore, tmp_path: Path
    ):
        await store.put_object("overwrite.bin", BytesIO(b"original"))
        result = await store.put_object(
            "overwrite.bin", BytesIO(b"updated"), overwrite=True
        )

        assert isinstance(result, str)
        assert (tmp_path / "overwrite.bin").read_bytes() == b"updated"

    async def test_put_to_readonly_returns_error(self, readonly_store: UnixFsStore):
        result = await readonly_store.put_object("k", BytesIO(b"v"))
        assert isinstance(result, AyunaError)
        assert "read-only" in str(result)

    async def test_put_objects_empty_entries_yields_error(self, store: UnixFsStore):
        results = [r async for r in store.put_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)

    async def test_put_objects_readonly_yields_error(self, readonly_store: UnixFsStore):
        results = [
            r async for r in readonly_store.put_objects([("k", BytesIO(b"v"), False)])
        ]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)

    async def test_put_objects_bulk(self, store: UnixFsStore, tmp_path: Path):
        entries = [
            ("a.bin", BytesIO(b"aaa"), False),
            ("b.bin", BytesIO(b"bbb"), False),
        ]
        results = [r async for r in store.put_objects(entries)]

        assert all(isinstance(r, str) for r in results)
        assert (tmp_path / "a.bin").exists()
        assert (tmp_path / "b.bin").exists()


class TestUnixFsStoreDelete:
    """Tests for UnixFsStore.delete_object() and delete_objects()."""

    async def test_delete_existing_object(self, store: UnixFsStore, tmp_path: Path):
        (tmp_path / "to_delete.bin").write_bytes(b"data")

        result = await store.delete_object("to_delete.bin")
        assert isinstance(result, str)
        assert not (tmp_path / "to_delete.bin").exists()

    async def test_delete_nonexistent_returns_error(self, store: UnixFsStore):
        result = await store.delete_object("missing.bin")
        assert isinstance(result, AyunaError)

    async def test_delete_readonly_returns_error(self, readonly_store: UnixFsStore):
        result = await readonly_store.delete_object("k")
        assert isinstance(result, AyunaError)
        assert "read-only" in str(result)

    async def test_delete_objects_empty_keys_yields_error(self, store: UnixFsStore):
        results = [r async for r in store.delete_objects([])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)

    async def test_delete_objects_readonly_yields_error(
        self, readonly_store: UnixFsStore
    ):
        results = [r async for r in readonly_store.delete_objects(["k"])]
        assert len(results) == 1
        assert isinstance(results[0], AyunaError)

    async def test_delete_objects_bulk(self, store: UnixFsStore, tmp_path: Path):
        (tmp_path / "a.bin").write_bytes(b"aaa")
        (tmp_path / "b.bin").write_bytes(b"bbb")

        results = [r async for r in store.delete_objects(["a.bin", "b.bin"])]
        assert all(isinstance(r, str) for r in results)
        assert not (tmp_path / "a.bin").exists()
        assert not (tmp_path / "b.bin").exists()


class TestUnixFsStoreMisc:
    """Tests for UnixFsStore.object_exists() and total_objects()."""

    async def test_object_exists_when_present(self, store: UnixFsStore, tmp_path: Path):
        (tmp_path / "exists.bin").write_bytes(b"data")
        assert await store.object_exists("exists.bin") is True

    async def test_object_exists_when_absent(self, store: UnixFsStore):
        assert await store.object_exists("missing.bin") is False

    async def test_total_objects_empty_store(self, store: UnixFsStore):
        assert await store.total_objects() == 0

    async def test_total_objects_counts_files(self, store: UnixFsStore, tmp_path: Path):
        (tmp_path / "a.bin").write_bytes(b"a")
        (tmp_path / "b.bin").write_bytes(b"b")
        (tmp_path / "c.bin").write_bytes(b"c")

        assert await store.total_objects() == 3

    async def test_roundtrip_put_get_delete(self, store: UnixFsStore):
        data = b"roundtrip content"
        await store.put_object("roundtrip.bin", BytesIO(data))

        assert await store.object_exists("roundtrip.bin") is True

        got = await store.get_object("roundtrip.bin")
        assert isinstance(got, BytesIO)
        assert got.getvalue() == data

        await store.delete_object("roundtrip.bin")
        assert await store.object_exists("roundtrip.bin") is False
