"""
test_basefuncs.py - Tests for ayuna_core.basefuncs module.
"""

import asyncio

import pytest
from pydantic import BaseModel

from ayuna_core.basefuncs import (
    alphanum_sorted,
    ayuna_mproc_context,
    coros_to_tasks,
    filename_by_sysinfo,
    gather_awaitables,
    gather_coroutines,
    id_by_sysinfo,
    load_model_class_from_mod_name,
    os_uname_str,
    safe_json_dumps,
    safe_json_loads,
    sizeof_object,
    system_ip_addresses,
    unmarshal_json_with_type,
    wrapped_try,
)
from ayuna_core.basetypes import AioErrorItem, AwaitCondition, AyunaError
from ayuna_core.constants import TYPE_MOD_NAME


class TestCorosToTasks:
    """Tests for coros_to_tasks function."""

    @pytest.mark.asyncio
    async def test_converts_coroutines_to_tasks(self):
        """Should convert coroutines to named tasks."""

        async def my_coro():  # NOSONAR
            return 42

        coros = [my_coro(), my_coro(), my_coro()]
        tasks = coros_to_tasks(coros)

        assert len(tasks) == 3
        assert all(isinstance(t, asyncio.Task) for t in tasks)
        assert "my_coro_1" in tasks[0].get_name()
        assert "my_coro_2" in tasks[1].get_name()

        # Cleanup
        for task in tasks:
            await task


class TestGatherAwaitables:
    """Tests for gather_awaitables function."""

    @pytest.mark.asyncio
    async def test_gather_all_done(self):
        """Should gather all results when ALL_DONE."""

        async def coro(value):
            await asyncio.sleep(0.01)
            return value

        awaitables = {
            "a": coro(1),
            "b": coro(2),
            "c": coro(3),
        }

        results = await gather_awaitables(awaitables, wait_for=AwaitCondition.ALL_DONE)

        assert results["a"] == 1
        assert results["b"] == 2
        assert results["c"] == 3

    @pytest.mark.asyncio
    async def test_gather_any_done(self):
        """Should return when any task completes."""

        async def fast():  # NOSONAR
            return "fast"

        async def slow():
            await asyncio.sleep(10)
            return "slow"

        awaitables = {
            "fast": fast(),
            "slow": slow(),
        }

        results = await gather_awaitables(awaitables, wait_for=AwaitCondition.ANY_DONE)

        # Fast should be done
        assert results["fast"] == "fast"
        # Slow should be cancelled
        assert isinstance(results["slow"], AioErrorItem)

    @pytest.mark.asyncio
    async def test_gather_with_timeout(self):
        """Should timeout and cancel pending tasks."""

        async def slow():
            await asyncio.sleep(10)
            return "done"

        awaitables = {"slow": slow()}

        results = await gather_awaitables(awaitables, wait_till_sec=0.1)

        # Should be cancelled due to timeout
        assert isinstance(results["slow"], AioErrorItem)
        assert "cancelled" in results["slow"].message.lower()

    @pytest.mark.asyncio
    async def test_gather_handles_exceptions(self):
        """Should capture exceptions as AioErrorItem."""

        async def failing():
            raise ValueError("Test error")

        awaitables = {"fail": failing()}

        results = await gather_awaitables(awaitables)

        assert isinstance(results["fail"], AioErrorItem)
        assert results["fail"].name == "ValueError"

    @pytest.mark.asyncio
    async def test_gather_empty_raises(self):
        """Should raise AssertionError for empty dict."""
        with pytest.raises(AssertionError):
            await gather_awaitables({})

    @pytest.mark.asyncio
    async def test_gather_too_many_raises(self):
        """Should raise AyunaError for > 9999 awaitables."""

        async def coro():  # NOSONAR
            return 1

        awaitables = {i: coro() for i in range(10000)}

        with pytest.raises(AyunaError):
            await gather_awaitables(awaitables)

        # Cleanup
        for awt in awaitables.values():
            awt.close()


class TestGatherCoroutines:
    """Tests for gather_coroutines function."""

    @pytest.mark.asyncio
    async def test_gather_coroutines_all(self):
        """Should gather all coroutine results."""

        async def add(a, b):  # NOSONAR
            return a + b

        coros = [add(1, 2), add(3, 4), add(5, 6)]
        results = await gather_coroutines(coros)

        # Results are keyed by task name (coro_name_index)
        values = results.values()
        assert sorted(values) == [3, 7, 11]


class TestAyunaAppInit:
    """Tests for app initialization functions."""

    def test_ayuna_app_init(self, ayuna_app_initialized):
        """ayuna_app_init should set up uvloop and mproc context."""
        # Fixture already called ayuna_app_init
        assert ayuna_app_initialized

    def test_ayuna_mproc_context_after_init(self, ayuna_app_initialized):
        """ayuna_mproc_context should return context after init."""
        ctx = ayuna_mproc_context()
        assert ctx is not None
        # Should be either fork or spawn context
        assert hasattr(ctx, "Process")


class TestLoadModelClass:
    """Tests for dynamic model loading."""

    def test_load_valid_model(self):
        """Should load a valid Pydantic model class."""
        cls = load_model_class_from_mod_name("ayuna_core.basetypes.AioErrorItem")
        assert cls is AioErrorItem
        assert issubclass(cls, BaseModel)

    def test_load_invalid_module_raises(self):
        """Should raise ImportError for invalid module."""
        with pytest.raises(ImportError):
            load_model_class_from_mod_name("nonexistent.module.Class")

    def test_load_non_model_raises(self):
        """Should raise TypeError for non-BaseModel classes."""
        with pytest.raises(TypeError):
            load_model_class_from_mod_name("ayuna_core.basetypes.AyunaError")


class TestUnmarshalJsonWithType:
    """Tests for polymorphic JSON deserialization."""

    def test_unmarshal_valid_json(self):
        """Should unmarshal JSON with type info."""
        from ayuna_core.opdata import OpSuccess

        # Create model and serialize
        original = OpSuccess(code=0, result="test")
        json_str = original.to_json_str()

        # Unmarshal
        result = unmarshal_json_with_type(json_str)

        assert isinstance(result, OpSuccess)
        assert result.result == "test"
        assert result.code == 0

    def test_unmarshal_missing_type_raises(self):
        """Should raise ValueError if type info missing."""
        import orjson

        json_str = orjson.dumps({"name": "test"})

        with pytest.raises(ValueError) as exc:
            unmarshal_json_with_type(json_str)
        assert TYPE_MOD_NAME in str(exc.value)


class TestOsUname:
    """Tests for os_uname_str function."""

    def test_os_uname_str_format(self):
        """Should return pipe-delimited system info."""
        result = os_uname_str()

        assert isinstance(result, str)
        parts = result.split("|")
        assert len(parts) == 5  # hostname, os, release, version, machine


class TestAlphanumSorted:
    """Tests for alphanum_sorted function."""

    def test_natural_sort(self):
        """Should sort strings naturally."""
        data = ["a10", "a2", "a1", "a20"]
        result = alphanum_sorted(data)
        assert result == ["a1", "a2", "a10", "a20"]

    def test_mixed_sort(self):
        """Should handle mixed alphanumeric strings."""
        data = ["file1.txt", "file10.txt", "file2.txt"]
        result = alphanum_sorted(data)
        assert result == ["file1.txt", "file2.txt", "file10.txt"]


class TestSizeofObject:
    """Tests for sizeof_object function."""

    def test_sizeof_simple(self):
        """Should return size of simple objects."""
        obj = "hello"
        size = sizeof_object(obj)
        assert size > 0
        assert isinstance(size, int)

    def test_sizeof_nested(self):
        """Should calculate size of nested structures."""
        obj = {"a": [1, 2, 3], "b": {"c": "value"}}
        size = sizeof_object(obj)
        assert size > 0

    def test_sizeof_handles_cycles(self):
        """Should handle circular references."""
        obj = {"self": None}
        obj["self"] = obj  # Create cycle

        # Should not infinite loop
        size = sizeof_object(obj)
        assert size > 0


class TestSafeJson:
    """Tests for safe JSON functions."""

    def test_safe_json_dumps_valid(self):
        """safe_json_dumps should serialize valid objects."""
        obj = {"key": "value", "number": 42}
        result = safe_json_dumps(obj)
        assert '"key"' in result
        assert '"value"' in result

    def test_safe_json_dumps_invalid(self):
        """safe_json_dumps should return original on failure."""
        obj = {"func": lambda x: x}  # Not serializable
        result = safe_json_dumps(obj)
        assert result is obj

    def test_safe_json_loads_valid(self):
        """safe_json_loads should parse valid JSON."""
        result = safe_json_loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_safe_json_loads_invalid(self):
        """safe_json_loads should return original on failure."""
        result = safe_json_loads("not json")
        assert result == "not json"


class TestSystemIpAddresses:
    """Tests for system_ip_addresses function."""

    def test_returns_list(self):
        """Should return a list of IP addresses."""
        ips = system_ip_addresses()
        assert isinstance(ips, list)
        assert len(ips) > 0

    def test_includes_localhost(self):
        """Should include localhost."""
        ips = system_ip_addresses()
        assert "127.0.0.1" in ips


class TestIdBySysinfo:
    """Tests for id_by_sysinfo function."""

    def test_returns_hash(self):
        """Should return a hash string."""
        result = id_by_sysinfo()
        assert isinstance(result, str)
        assert len(result) == 32  # MD5 hash length

    def test_with_suffix(self):
        """Should append suffix to hash."""
        result = id_by_sysinfo(suffix="_test")
        assert result.endswith("_test")

    def test_with_pid(self):
        """Should include pid when requested."""
        result1 = id_by_sysinfo(use_pid=False)
        result2 = id_by_sysinfo(use_pid=True)
        # Results might differ (pid changes hash)
        assert isinstance(result1, str)
        assert isinstance(result2, str)


class TestFilenameBySysinfo:
    """Tests for filename_by_sysinfo function."""

    def test_returns_filename(self):
        """Should return a filename with hash."""
        result = filename_by_sysinfo("mylog")
        assert result.startswith("mylog_")
        assert result.endswith(".out")

    def test_custom_extension(self):
        """Should use custom extension."""
        result = filename_by_sysinfo("mylog", extension=".log")
        assert result.endswith(".log")


class TestWrappedTry:
    """Tests for wrapped_try function."""

    def test_wrapped_try_success(self):
        """Should return function result on success."""

        def add(a, b):
            return a + b

        wrapper = wrapped_try(add, 1, 2)
        assert wrapper() == 3

    def test_wrapped_try_failure(self):
        """Should return None on exception."""

        def failing():
            raise ValueError("error")

        wrapper = wrapped_try(failing)
        assert wrapper() is None
