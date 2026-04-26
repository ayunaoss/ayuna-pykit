"""
basefuncs.py - Core utility functions for the Ayuna framework.

This module provides essential utility functions used throughout the ayuna_core
library, including:

- Async task management and gathering utilities
- Application initialization and configuration
- Dynamic model loading for polymorphic deserialization
- System information utilities (IP addresses, OS info)
- JSON serialization helpers
- Caching and hashing utilities
"""

import asyncio
import hashlib
import importlib
import inspect
import os
import re
import socket
import sys
from multiprocessing import get_context as mproc_get_context
from typing import Any, Coroutine, Dict, Iterable, List, Type

import netifaces
import orjson as json
import uvloop
from cachetools.func import ttl_cache
from pydantic import BaseModel

from .basetypes import (
    AioErrorItem,
    Awaitable,
    AwaitableDoneHandler,
    AwaitCondition,
    AyunaError,
    KeyIdxType,
    MprocContext,
)
from .constants import TYPE_MOD_NAME

# =============================================================================
# Global State
# =============================================================================

# Global multiprocessing context (fork or spawn), initialized by ayuna_app_init()
__mproc_ctx: MprocContext | None = None

# =============================================================================
# Internal Helper Functions for Async Operations
# =============================================================================


def _release_waiter(waiter: asyncio.Future):
    """
    Release a waiter Future by setting its result to None.

    Used as a timeout callback to unblock waiting operations.

    Parameters
    ----------
    waiter : asyncio.Future
        The Future to release.
    """
    if not waiter.done():
        waiter.set_result(None)


def _finalize_awaitables(
    awaitables: Dict[KeyIdxType, Awaitable], done_cb: AwaitableDoneHandler
):
    """
    Finalize a collection of awaitables and collect their results.

    Processes completed, cancelled, and pending awaitables, extracting
    their results or converting exceptions to AioErrorItem objects.
    Pending tasks are cancelled.

    Parameters
    ----------
    awaitables : Dict[KeyIdxType, Awaitable]
        Dictionary mapping keys to Future/Task objects.
    done_cb : AwaitableDoneHandler
        The completion callback to remove from each awaitable.

    Returns
    -------
    Dict[KeyIdxType, Any]
        Dictionary mapping keys to results or AioErrorItem objects.
    """
    results: Dict[KeyIdxType, Any] = {}

    for k, v in awaitables.items():
        v.remove_done_callback(done_cb)

        if v.done():
            if v.cancelled():
                results[k] = AioErrorItem(
                    name="CancelledError", message=f"Job {k} cancelled internally"
                )
            else:
                exc = v.exception()

                if not exc:
                    results[k] = v.result()
                else:
                    results[k] = AioErrorItem(name=type(exc).__name__, message=str(exc))
        else:
            v.cancel()
            results[k] = AioErrorItem(
                name="CancelledError", message=f"Pending job {k} cancelled"
            )

    return results


# =============================================================================
# Async Task Management Functions
# =============================================================================


def coros_to_tasks(coros: List[Coroutine]) -> List[asyncio.Task]:
    """
    Convert a list of coroutines to named asyncio Tasks.

    Each task is named using the coroutine's __name__ attribute
    with an incrementing index suffix (e.g., "my_coro_1", "my_coro_2").

    Parameters
    ----------
    coros : List[Coroutine]
        List of coroutine objects to convert.

    Returns
    -------
    List[asyncio.Task]
        List of created Task objects.
    """
    idx: int = 1
    tasks: List[asyncio.Task] = []

    for cr in coros:
        tasks.append(asyncio.create_task(coro=cr, name=f"{cr.__name__}_{idx}"))
        idx += 1

    return tasks


async def gather_awaitables(
    awaitables: Dict[KeyIdxType, Awaitable],
    *,
    wait_for: AwaitCondition = AwaitCondition.ALL_DONE,
    wait_till_sec: float = -1.0,
) -> Dict[KeyIdxType, Any]:
    """
    Gather results from multiple awaitables with configurable wait conditions.

    A more flexible alternative to asyncio.gather() that supports:
    - Named awaitables via dictionary keys
    - Configurable wait conditions (all done, any done, any fail)
    - Optional timeout
    - Graceful handling of cancellations and exceptions

    Parameters
    ----------
    awaitables : Dict[KeyIdxType, Awaitable]
        Dictionary mapping keys to Future, Task, or Coroutine objects.
        Coroutines are automatically converted to Tasks.
    wait_for : AwaitCondition, optional
        When to return results:
        - ALL_DONE: Wait for all tasks to complete (default)
        - ANY_DONE: Return when any task completes
        - ANY_FAIL: Return when any task raises an exception
    wait_till_sec : float, optional
        Maximum time to wait in seconds. -1.0 means no timeout (default).

    Returns
    -------
    Dict[KeyIdxType, Any]
        Dictionary mapping keys to results or AioErrorItem objects for failures.

    Raises
    ------
    AssertionError
        If awaitables dictionary is empty.
    AyunaError
        If more than 9999 awaitables are provided.
    """
    awt_counter = len(awaitables)
    assert awt_counter > 0, "Awaitables dictionary is empty"

    if awt_counter > 9999:
        raise AyunaError("Maximum number of awaitables allowed is 9999")

    run_loop = asyncio.get_running_loop()
    waiter = run_loop.create_future()
    timeout_hndl = None

    if wait_till_sec > 0:
        timeout_hndl = run_loop.call_later(wait_till_sec, _release_waiter, waiter)

    def completion_cb(f: asyncio.Future):
        """Callback invoked when each awaitable completes."""
        nonlocal awt_counter
        awt_counter -= 1

        if (
            awt_counter <= 0
            or (wait_for == AwaitCondition.ANY_DONE)
            or (
                (wait_for == AwaitCondition.ANY_FAIL)
                and (not f.cancelled() and f.exception() is not None)
            )
        ):
            if timeout_hndl is not None:
                timeout_hndl.cancel()

            if not waiter.done():
                waiter.set_result(None)

    for k, v in awaitables.items():
        # NOTE: We must convert a Coroutine into a Task
        if asyncio.coroutines.iscoroutine(v):
            v = asyncio.create_task(v)
            awaitables[k] = v

        v.add_done_callback(completion_cb)

    try:
        await waiter
    except asyncio.CancelledError:  # NOSONAR
        print("Awaitables result cancelled")
    finally:
        if timeout_hndl is not None:
            timeout_hndl.cancel()

    return _finalize_awaitables(awaitables=awaitables, done_cb=completion_cb)


async def gather_coroutines(
    coros: List[Coroutine],
    *,
    wait_for: AwaitCondition = AwaitCondition.ALL_DONE,
    wait_till_sec: float = -1.0,
) -> Dict[str, Any]:
    """
    Gather results from multiple coroutines with configurable wait conditions.

    Simpler interface than gather_awaitables() when you have a list of
    coroutines and don't need custom keys. Tasks are automatically named
    based on the coroutine name with an index suffix.

    Parameters
    ----------
    coros : List[Coroutine]
        List of coroutine objects to execute concurrently.
    wait_for : AwaitCondition, optional
        When to return results (default: ALL_DONE).
    wait_till_sec : float, optional
        Maximum time to wait in seconds. -1.0 means no timeout (default).

    Returns
    -------
    Dict[str, Any]
        Dictionary mapping task names to results or AioErrorItem objects.
    """
    tasks = coros_to_tasks(coros)
    results: Dict[str, Any] = {}

    if wait_till_sec > 0:
        done, pending = await asyncio.wait(
            tasks, timeout=wait_till_sec, return_when=wait_for
        )
    else:
        done, pending = await asyncio.wait(tasks, return_when=wait_for)

    for dtask in done:
        tn = dtask.get_name()

        if dtask.cancelled():
            results[tn] = AioErrorItem(
                name="CancelledError", message=f"Job {tn} cancelled internally"
            )
        else:
            exc = dtask.exception()

            if not exc:
                results[tn] = dtask.result()
            else:
                results[tn] = AioErrorItem(name=type(exc).__name__, message=str(exc))

    for ptask in pending:
        tn = ptask.get_name()
        ptask.cancel()

        results[tn] = AioErrorItem(
            name="CancelledError", message=f"Pending job {tn} cancelled"
        )

    return results


# =============================================================================
# Application Initialization Functions
# =============================================================================


def ayuna_app_init():
    """
    Initialize the Ayuna application runtime configuration.

    This function should be called once at application startup before
    using any multiprocessing or async features. It performs:

    1. Sets uvloop as the asyncio event loop policy for better performance
    2. Configures the multiprocessing context (fork or spawn) based on
       the MULTI_PROCESS_CONTEXT environment variable

    The multiprocessing context defaults to "spawn" which is safer and
    works across all platforms. Set MULTI_PROCESS_CONTEXT=fork for
    better performance on Unix systems where fork is safe to use.

    Note
    ----
    Calling this function multiple times has no effect after the first call.
    """
    global __mproc_ctx

    if __mproc_ctx:
        print("Ayuna app configuration already initialized")
        return

    print("Initializing Ayuna app configuration")
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    mproc_ctx_env = os.getenv("MULTI_PROCESS_CONTEXT", "spawn").lower().strip()

    if mproc_ctx_env == "fork":
        __mproc_ctx = mproc_get_context("fork")
    else:
        __mproc_ctx = mproc_get_context("spawn")


def ayuna_mproc_context():
    """
    Get the configured multiprocessing context.

    Returns the multiprocessing context (fork or spawn) that was
    configured during ayuna_app_init(). This context should be used
    when creating Process objects to ensure consistent behavior.

    Returns
    -------
    MprocContext
        The configured ForkContext or SpawnContext.

    Raises
    ------
    AssertionError
        If ayuna_app_init() has not been called.
    """
    global __mproc_ctx
    assert __mproc_ctx is not None

    return __mproc_ctx


# =============================================================================
# Dynamic Model Loading Functions
# =============================================================================


def load_model_class_from_mod_name(mod_name: str) -> Type[BaseModel]:
    """
    Dynamically load a Pydantic model class from its fully qualified name.

    This function enables polymorphic deserialization by loading the
    appropriate model class at runtime based on the stored type name.

    Parameters
    ----------
    mod_name : str
        Fully qualified class name in the format "module.path.ClassName".

    Returns
    -------
    Type[BaseModel]
        The Pydantic model class.

    Raises
    ------
    ImportError
        If the module cannot be imported or the class cannot be found.
    TypeError
        If the resolved object is not a BaseModel subclass.

    Example
    -------
    >>> cls = load_model_class_from_mod_name("ayuna_core.opdata.OpSuccess")
    >>> instance = cls(code=0, result="ok")
    """
    try:
        module_path, class_name = mod_name.rsplit(".", 1)
    except ValueError as e:
        raise ImportError(
            f"'{mod_name}' is not a valid fully qualified class name"
        ) from e

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ImportError(f"Could not import module '{module_path}'") from e

    try:
        cls = getattr(module, class_name)
    except AttributeError as e:
        raise ImportError(
            f"Module '{module_path}' has no attribute '{class_name}'"
        ) from e

    if not inspect.isclass(cls):
        raise TypeError(f"{mod_name} does not point to a class")

    if not issubclass(cls, BaseModel):
        raise TypeError(f"{mod_name} is not a subclass of BaseModel")

    return cls


def unmarshal_json_with_type(json_str: str | bytes | bytearray) -> BaseModel:
    """
    Deserialize JSON to the appropriate Pydantic model using embedded type info.

    Reads the TYPE_MOD_NAME field from the JSON data to determine which
    Pydantic model class to instantiate. This enables polymorphic
    deserialization of BaseData subclasses.

    Parameters
    ----------
    json_str : str | bytes | bytearray
        JSON string containing a serialized Pydantic model with type info.

    Returns
    -------
    BaseModel
        An instance of the appropriate Pydantic model subclass.

    Raises
    ------
    ValueError
        If the TYPE_MOD_NAME field is missing from the JSON data.
    ImportError
        If the model class cannot be loaded.
    ValidationError
        If the data doesn't match the model's schema.
    """
    data = json.loads(json_str)

    if not isinstance(data, dict):
        raise TypeError("JSON payload must be an object")

    mod_name = data.pop(TYPE_MOD_NAME, None)

    if not mod_name:
        raise ValueError(f"Missing {TYPE_MOD_NAME} in json data")

    if not isinstance(mod_name, str):
        raise TypeError(f"{TYPE_MOD_NAME} must be a string")

    model_class = load_model_class_from_mod_name(mod_name)

    # Let Pydantic do all field/type validation
    return model_class.model_validate(data)


# =============================================================================
# System Information Utilities
# =============================================================================


def os_uname_str():
    """
    Get a string representation of the OS system information.

    Combines hostname, OS name, release, version, and machine architecture
    into a single pipe-delimited string useful for system identification.

    Returns
    -------
    str
        Pipe-delimited system info: "hostname|os|release|version|machine"
    """
    uname_info = os.uname()
    return f"{uname_info.nodename}|{uname_info.sysname}|{uname_info.release}|{uname_info.version}|{uname_info.machine}"


# =============================================================================
# General Utility Functions
# =============================================================================


def alphanum_sorted(data: Iterable):
    """
    Sort strings in natural alphanumeric order (human-friendly sorting).

    Sorts strings so that numeric portions are compared numerically
    rather than lexicographically. For example: ["a1", "a10", "a2"]
    becomes ["a1", "a2", "a10"].

    Parameters
    ----------
    data : Iterable
        Collection of strings to sort.

    Returns
    -------
    list
        Sorted list of strings in natural order.
    """

    def convert(text: str):
        return int(text) if text.isdigit() else text.lower()

    def alphanum_key(key):
        return [convert(c) for c in re.split("(\\d+)", key)]

    return sorted(data, key=alphanum_key)


def sizeof_object(obj, seen=None):
    """
    Recursively calculate the total memory size of an object.

    Traverses the object's structure to sum the memory used by
    the object and all its contents, handling circular references.

    Parameters
    ----------
    obj : Any
        The object to measure.
    seen : set, optional
        Set of already-visited object IDs (used internally for recursion).

    Returns
    -------
    int
        Total size in bytes.
    """
    size = sys.getsizeof(obj)

    if seen is None:
        seen = set()

    obj_id = id(obj)

    if obj_id in seen:
        return 0

    seen.add(obj_id)

    if isinstance(obj, dict):
        size += sum([sizeof_object(k, seen) for k in obj.keys()])
        size += sum([sizeof_object(v, seen) for v in obj.values()])
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum([sizeof_object(i, seen) for i in obj])

    return size


# =============================================================================
# JSON Utilities
# =============================================================================


def safe_json_dumps(obj: Any):
    """
    Safely serialize an object to JSON, returning the original on failure.

    Parameters
    ----------
    obj : Any
        Object to serialize.

    Returns
    -------
    str | Any
        JSON string if serialization succeeds, original object otherwise.
    """
    try:
        return json.dumps(obj).decode("utf-8")
    except Exception:
        return obj


def safe_json_loads(value: str):
    """
    Safely parse a JSON string, returning the original on failure.

    Parameters
    ----------
    value : str
        JSON string to parse.

    Returns
    -------
    Any
        Parsed object if valid JSON, original string otherwise.
    """
    try:
        return json.loads(value)
    except Exception:
        return value


def system_ip_addresses():
    """
    Get all IP addresses of the machine.

    Returns
    -------
    list
        List of IP addresses
    """

    ip_addresses = ["127.0.0.1"]

    for interface in netifaces.interfaces():
        try:
            addresses = netifaces.ifaddresses(interface)

            for addr in addresses:
                if addr == socket.AF_INET:
                    ip_addresses.append(addresses[addr][0]["addr"])
        except ValueError:
            pass

    ip_addresses = list(set(ip_addresses))
    ip_addresses.sort()

    return ip_addresses


@ttl_cache(maxsize=128, ttl=600)
def id_by_sysinfo(suffix: str = "", use_pid: bool = False, hash_algo: str = "md5"):
    """
    Generate an identifier combined with pid and ip-addresses.

    Parameters
    ----------
    suffix: str
        The suffix to be added to the identifier. Default is "".
    use_pid: bool
        True to include pid in the identifier, False otherwise. Default is False.
    hash_algo: str
        The hash algorithm to be used. Default is "md5".

    Returns
    -------
    str
        The generated identifier
    """

    ip_addresses = system_ip_addresses()
    sysid = "".join(ip_addresses) + os_uname_str()

    if use_pid:
        sysid += str(os.getpid())

    if hash_algo and hash_algo in hashlib.algorithms_guaranteed:
        sysid = hashlib.new(hash_algo, sysid.encode()).hexdigest() + suffix
    else:
        sysid = hashlib.md5(sysid.encode()).hexdigest() + suffix

    return sysid


@ttl_cache(maxsize=128, ttl=600)
def filename_by_sysinfo(basename: str, extension: str = ".out"):
    """
    Get filename suffixed with hashed system info.

    Parameters
    ----------
    basename: str
        The base name of the filename
    extension: str
        The extension of the filename. Default is ".out"

    Returns
    -------
    str
        The generated filename
    """

    ip_addresses = system_ip_addresses()

    suffix = "".join(ip_addresses) + os_uname_str()
    suffix = hashlib.md5(suffix.encode()).hexdigest()

    return f"{basename}_{suffix}{extension}"


def wrapped_try(func, *args, **kwargs):
    """
    Wrap a function call in a try-except block.

    Parameters
    ----------
    func: callable
        The function to be called
    *args
        The positional arguments to be passed to the function
    **kwargs
        The keyword arguments to be passed to the function

    Returns
    -------
    Callable
        The wrapped function
    """

    def wrapper():
        try:
            return func(*args, **kwargs)
        except Exception:
            return None

    return wrapper
