"""
aiotpool.py - Async-aware thread pool executor for the Ayuna framework.

This module provides AioThreadPoolExecutor, a thread pool executor that
can execute coroutines in worker threads. Each worker thread runs its
own asyncio event loop via asyncio.run().

This is useful when you need to run async code from a synchronous context
or when you want to parallelize async operations across multiple threads.

Note: This differs from standard ThreadPoolExecutor which can only run
synchronous functions.
"""

import asyncio
import atexit
import itertools
import logging
import os
import queue
import threading
import types
import weakref
from concurrent.futures import BrokenExecutor
from concurrent.futures import Executor as BaseExecutor
from concurrent.futures import Future as BaseFuture
from typing import Coroutine, MutableSet

from ..constants import NUM_THREAD_WORKERS

_logger = logging.getLogger("ayuna.core.aiopool")

# Weak dictionary mapping threads to their work queues for cleanup
_threads_queues = weakref.WeakKeyDictionary()

# Global shutdown flag for interpreter exit handling
_shutdown = False

# Lock that ensures that new workers are not created while the interpreter is
# shutting down. Must be held while mutating _threads_queues and _shutdown.
_global_shutdown_lock = threading.Lock()

# =============================================================================
# Module-level Functions
# =============================================================================


def _python_exit():
    """
    Cleanup handler called at Python interpreter shutdown.

    Signals all worker threads to exit and waits for them to complete.
    """
    global _shutdown

    with _global_shutdown_lock:
        _shutdown = True

    items = list(_threads_queues.items())

    for t, q in items:
        q.put(None)

    for t, q in items:
        t.join()


# Register cleanup handler for interpreter shutdown
atexit.register(_python_exit)


# At fork, reinitialize the `_global_shutdown_lock` lock in the child process
if hasattr(os, "register_at_fork"):
    os.register_at_fork(
        before=_global_shutdown_lock.acquire,
        after_in_parent=_global_shutdown_lock.release,
    )

# =============================================================================
# Internal Classes and Functions
# =============================================================================


class _WorkItem(object):
    """
    Internal class representing a unit of async work to be executed.

    Wraps a coroutine and its associated Future for result delivery.
    """

    def __init__(self, future: BaseFuture, coro: Coroutine) -> None:
        """
        Initialize a work item.

        Parameters
        ----------
        future : BaseFuture
            Future to set with the coroutine result.
        coro : Coroutine
            Coroutine to execute.
        """
        self.future = future
        self.coro = coro

    async def run(self):
        """Execute the coroutine and set the result on the future."""
        if not self.future.set_running_or_notify_cancel():
            return

        try:
            result = await self.coro
        except Exception as ex:
            self.future.set_exception(ex)
            # Break a reference cycle with the exception 'ex'
            self = None
        else:
            self.future.set_result(result)

    __class_getitem__ = classmethod(types.GenericAlias)


def _worker(
    executor_reference: weakref.ReferenceType["AioThreadPoolExecutor"],
    work_queue: queue.SimpleQueue,
    initializer,
    initargs,
):
    """
    Worker thread function that processes work items from the queue.

    Each work item's coroutine is run in a fresh event loop via asyncio.run().

    Parameters
    ----------
    executor_reference : weakref.ReferenceType
        Weak reference to the executor for lifecycle management.
    work_queue : queue.SimpleQueue
        Queue to pull work items from.
    initializer : callable
        Optional initialization function to run on thread start.
    initargs : tuple
        Arguments to pass to the initializer.
    """
    if initializer is not None:
        try:
            initializer(*initargs)
        except Exception:
            _logger.critical("Exception in initializer:", exc_info=True)
            ref_instance = executor_reference()

            if ref_instance is not None:
                ref_instance._initializer_failed()

            return

    try:
        while True:
            work_item: _WorkItem = work_queue.get(block=True)

            if work_item is not None:
                asyncio.run(work_item.run())
                # Delete references to object. See issue16284
                del work_item

                # attempt to increment idle count
                ref_instance = executor_reference()

                if ref_instance is not None:
                    ref_instance._idle_semaphore.release()
                    del ref_instance

                continue

            ref_instance = executor_reference()
            # Exit if:
            #   - The interpreter is shutting down OR
            #   - The executor that owns the worker has been collected OR
            #   - The executor that owns the worker has been shutdown.
            if _shutdown or ref_instance is None or ref_instance._shutdown:
                # Flag the executor as shutting down as early as possible if it
                # is not gc-ed yet.
                if ref_instance is not None:
                    ref_instance._shutdown = True

                # Notice other workers
                work_queue.put(None)
                return

            del ref_instance
    except Exception:
        _logger.critical("Exception in worker", exc_info=True)


# =============================================================================
# Public Classes
# =============================================================================


class BrokenThreadPool(BrokenExecutor):
    """
    Exception raised when a worker thread in AioThreadPoolExecutor failed initializing.

    When this exception is raised, the executor is no longer usable and
    all pending futures will receive this exception.
    """

    pass


class AioThreadPoolExecutor(BaseExecutor):
    """
    A thread pool executor that can execute coroutines.

    Similar to concurrent.futures.ThreadPoolExecutor, but accepts
    coroutines instead of regular functions. Each worker thread runs
    coroutines in its own event loop via asyncio.run().

    This is useful for parallelizing async operations across threads
    or running async code from synchronous contexts.

    Parameters
    ----------
    max_workers : int, optional
        Maximum number of worker threads. Defaults to NUM_THREAD_WORKERS.
    thread_name_prefix : str, optional
        Prefix for worker thread names.
    initializer : callable, optional
        Function to call when starting each worker thread.
    initargs : tuple, optional
        Arguments to pass to the initializer.

    Example
    -------
    >>> async def fetch_data(url):
    ...     # async HTTP request
    ...     return data
    ...
    >>> with AioThreadPoolExecutor(max_workers=4) as executor:
    ...     future = executor.submit(fetch_data("http://example.com"))
    ...     result = future.result()
    """

    # Used to assign unique thread names when thread_name_prefix is not supplied.
    _counter = itertools.count().__next__

    def __init__(
        self, max_workers=None, thread_name_prefix="", initializer=None, initargs=()
    ):
        """
        Initialize a new AioThreadPoolExecutor instance.

        Parameters
        ----------
        max_workers : int, optional
            Maximum number of threads. Defaults to NUM_THREAD_WORKERS.
        thread_name_prefix : str, optional
            Prefix for worker thread names.
        initializer : callable, optional
            Function to call when starting each worker thread.
        initargs : tuple, optional
            Arguments to pass to the initializer.
        """
        if max_workers is None:
            # ThreadPoolExecutor is often used to:
            # * CPU bound task which releases GIL
            # * I/O bound task (which releases GIL, of course)
            #
            # We use cpu_count + 4 for both types of tasks.
            # But we limit it to 32 to avoid consuming surprisingly large resource
            # on many core machine.
            max_workers = NUM_THREAD_WORKERS

        if max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")

        if initializer is not None and not callable(initializer):
            raise TypeError("initializer must be a callable")

        self._max_workers = max_workers
        self._work_queue = queue.SimpleQueue()
        self._idle_semaphore = threading.Semaphore(0)
        self._threads: MutableSet[threading.Thread] = set()
        self._broken = False
        self._shutdown = False
        self._shutdown_lock = threading.Lock()

        self._thread_name_prefix = thread_name_prefix or (
            "AioThreadPoolExecutor-%d" % self._counter()
        )

        self._initializer = initializer
        self._initargs = initargs

    def submit(self, coro: Coroutine, /, *args, **kwargs):
        with self._shutdown_lock, _global_shutdown_lock:
            if self._broken:
                raise BrokenThreadPool(self._broken)

            if self._shutdown:
                raise RuntimeError("cannot schedule new futures after shutdown")

            if _shutdown:
                raise RuntimeError(
                    "cannot schedule new futures after interpreter shutdown"
                )

            fut = BaseFuture()
            witem = _WorkItem(future=fut, coro=coro)

            self._work_queue.put(witem)
            self._adjust_thread_count()

            return fut

    submit.__doc__ = BaseExecutor.submit.__doc__

    def _adjust_thread_count(self):
        # if idle threads are available, don't spin new threads
        if self._idle_semaphore.acquire(timeout=0):
            return

        # When the executor gets lost, the weakref callback will wake up
        # the worker threads.
        def weakref_cb(_, q=self._work_queue):
            q.put(None)

        num_threads = len(self._threads)

        if num_threads < self._max_workers:
            thread_name = "%s_%d" % (self._thread_name_prefix or self, num_threads)
            t = threading.Thread(
                name=thread_name,
                target=_worker,
                args=(
                    weakref.ref(self, weakref_cb),
                    self._work_queue,
                    self._initializer,
                    self._initargs,
                ),
            )

            t.start()
            self._threads.add(t)

            _threads_queues[t] = self._work_queue

    def _initializer_failed(self):
        with self._shutdown_lock:
            self._broken = (
                "A thread initializer failed, the thread pool is not usable anymore"
            )

            # Drain work queue and mark pending futures failed
            while True:
                try:
                    work_item: _WorkItem = self._work_queue.get_nowait()
                except queue.Empty:
                    break

                if work_item is not None:
                    work_item.future.set_exception(BrokenThreadPool(self._broken))

    def shutdown(self, wait=True, *, cancel_futures=False):
        with self._shutdown_lock:
            self._shutdown = True

            if cancel_futures:
                # Drain all work items from the queue, and then cancel their
                # associated futures.
                while True:
                    try:
                        work_item: _WorkItem = self._work_queue.get_nowait()
                    except queue.Empty:
                        break

                    if work_item is not None:
                        work_item.future.cancel()

            # Send a wake-up to prevent threads calling
            # _work_queue.get(block=True) from permanently blocking.
            self._work_queue.put(None)

        if wait:
            for t in self._threads:
                t.join()

    shutdown.__doc__ = BaseExecutor.shutdown.__doc__
