"""
aioqueue.py - Async/sync queue bridges for the Ayuna framework.

This module provides queue-based pub/sub patterns that bridge synchronous
and asynchronous code:

- AsyncPubSyncSub: Async publisher with sync subscriber (consumer runs in executor)
- SyncPubAsyncSub: Sync publisher with async subscriber (consumer is a coroutine)

Both classes use the Janus queue which provides both sync and async interfaces
to the same underlying queue, enabling safe communication between sync and
async contexts.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Coroutine

from janus import Queue as _Queue

from ..constants import LOOP_BREAK_MSG

# =============================================================================
# Type Definitions
# =============================================================================

# Synchronous consumer function type
SyncConsumer = Callable[[Any], None]

# Asynchronous consumer coroutine type
AsyncConsumer = Callable[[Any], Coroutine[Any, Any, None]]

_logger = logging.getLogger("ayuna.core.aioqueue")

# =============================================================================
# Queue Classes
# =============================================================================


class AsyncPubSyncSub:
    """
    Async publisher with synchronous subscriber pattern.

    Messages are published asynchronously and consumed by a synchronous
    function running in a thread pool executor. Useful when async code
    needs to send work to synchronous processing logic.

    Parameters
    ----------
    max_queue_size : int
        Maximum number of items in the queue (default: 1000).
    sync_consumer : SyncConsumer
        Synchronous function to process each item.
    sync_executor : ThreadPoolExecutor | None
        Optional executor for running the consumer. If None, uses default.

    Example
    -------
    >>> def process(item):
    ...     print(f"Processing: {item}")
    ...
    >>> queue = AsyncPubSyncSub(sync_consumer=process)
    >>> asyncio.create_task(queue.run())  # Start consumer loop
    >>> await queue.publish("item1")
    >>> await queue.close()
    """

    def __init__(
        self,
        *,
        max_queue_size: int = 1000,
        sync_consumer: SyncConsumer,
        sync_executor: ThreadPoolExecutor | None = None,
    ):
        """Initialize the async-pub/sync-sub queue."""
        self.__queue: _Queue[Any] = _Queue(maxsize=max_queue_size)
        self.__consumer = sync_consumer
        self.__executor = sync_executor

        self.__aio_loop = asyncio.get_event_loop()
        self.__is_consuming = False

    async def close(self):
        """Stop the consumer loop and close the queue."""
        if self.__is_consuming:
            await self.__queue.async_q.put(LOOP_BREAK_MSG)
            self.__is_consuming = False

        self.__queue.sync_q.join()
        await self.__queue.async_q.join()
        await self.__queue.aclose()

    async def publish(self, item: Any):
        """
        Asynchronously publish an item to the queue.

        Parameters
        ----------
        item : Any
            Item to publish.
        """
        await self.__queue.async_q.put(item)

    async def run(self):
        """
        Start the consumer loop.

        Continuously reads from the queue and processes items with
        the sync consumer. Runs until close() is called.
        """
        if self.__is_consuming:
            _logger.warning("AsyncPubSyncSub is already running")
            return

        self.__is_consuming = True

        while True:
            item = self.__queue.sync_q.get()

            if item is LOOP_BREAK_MSG:
                self.__queue.sync_q.task_done()
                break

            try:
                await self.__aio_loop.run_in_executor(
                    self.__executor, self.__consumer, item
                )
            except Exception as ex:
                _logger.error("Unhandled error while consuming message", exc_info=ex)

            self.__queue.sync_q.task_done()

        self.__is_consuming = False


class SyncPubAsyncSub:
    """
    Synchronous publisher with async subscriber pattern.

    Messages are published synchronously and consumed by an async
    coroutine. Useful when sync code needs to send work to async
    processing logic.

    Parameters
    ----------
    max_queue_size : int
        Maximum number of items in the queue (default: 1000).
    async_consumer : AsyncConsumer
        Async coroutine function to process each item.

    Example
    -------
    >>> async def process(item):
    ...     print(f"Processing: {item}")
    ...
    >>> queue = SyncPubAsyncSub(async_consumer=process)
    >>> asyncio.create_task(queue.run())  # Start consumer loop
    >>> queue.publish("item1")  # Sync publish
    >>> await queue.close()
    """

    def __init__(self, *, max_queue_size: int = 1000, async_consumer: AsyncConsumer):
        """Initialize the sync-pub/async-sub queue."""
        self.__queue: _Queue[Any] = _Queue(maxsize=max_queue_size)
        self.__consumer = async_consumer

        self.__is_consuming = False

    async def close(self):
        """Stop the consumer loop and close the queue."""
        if self.__is_consuming:
            self.__queue.sync_q.put(LOOP_BREAK_MSG)
            self.__is_consuming = False

        self.__queue.sync_q.join()
        await self.__queue.async_q.join()
        await self.__queue.aclose()

    def publish(self, item: Any):
        """
        Synchronously publish an item to the queue.

        Parameters
        ----------
        item : Any
            Item to publish.
        """
        self.__queue.sync_q.put(item)

    async def run(self):
        """
        Start the consumer loop.

        Continuously reads from the queue and processes items with
        the async consumer. Runs until close() is called.
        """
        if self.__is_consuming:
            _logger.warning("SyncPubAsyncSub is already running")
            return

        self.__is_consuming = True

        while True:
            item = await self.__queue.async_q.get()

            if item is LOOP_BREAK_MSG:
                self.__queue.async_q.task_done()
                break

            try:
                await self.__consumer(item)
            except Exception as ex:
                _logger.error("Unhandled error while consuming message", exc_info=ex)

            self.__queue.async_q.task_done()

        self.__is_consuming = False
