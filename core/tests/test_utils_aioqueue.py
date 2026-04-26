"""
Tests for ayuna_core.utils.aioqueue module.

Tests the queue class interfaces and basic functionality.
Note: Full integration tests for these queue classes are better done
in an application context where the event loop is properly managed.
"""

from ayuna_core.utils.aioqueue import AsyncPubSyncSub, SyncPubAsyncSub


class TestAsyncPubSyncSubInterface:
    """Tests for AsyncPubSyncSub class interface."""

    async def test_can_create_instance(self):  # NOSONAR
        """Test that AsyncPubSyncSub can be instantiated."""

        # The consumer must be a synchronous function for AsyncPubSyncSub
        def consumer(item):
            pass

        queue = AsyncPubSyncSub(sync_consumer=consumer)
        assert queue is not None

    async def test_can_create_with_max_queue_size(self):  # NOSONAR
        """Test creating with custom queue size."""

        # The consumer must be a synchronous function for AsyncPubSyncSub
        def consumer(item):
            pass

        queue = AsyncPubSyncSub(max_queue_size=100, sync_consumer=consumer)
        assert queue is not None

    async def test_can_create_with_executor(self):  # NOSONAR
        """Test creating with custom executor."""
        from concurrent.futures import ThreadPoolExecutor

        # The consumer must be a synchronous function for AsyncPubSyncSub
        def consumer(item):
            pass

        executor = ThreadPoolExecutor(max_workers=2)
        try:
            queue = AsyncPubSyncSub(sync_consumer=consumer, sync_executor=executor)
            assert queue is not None
        finally:
            executor.shutdown(wait=False)


class TestSyncPubAsyncSubInterface:
    """Tests for SyncPubAsyncSub class interface."""

    def test_can_create_instance(self):
        """Test that SyncPubAsyncSub can be instantiated."""

        # The consumer must be an asynchronous function for SyncPubAsyncSub
        async def consumer(item):
            pass

        queue = SyncPubAsyncSub(async_consumer=consumer)
        assert queue is not None

    def test_can_create_with_max_queue_size(self):
        """Test creating with custom queue size."""

        # The consumer must be an asynchronous function for SyncPubAsyncSub
        async def consumer(item):
            pass

        queue = SyncPubAsyncSub(max_queue_size=100, async_consumer=consumer)
        assert queue is not None

    def test_publish_method_exists(self):
        """Test that publish method exists and is callable."""

        # The consumer must be an asynchronous function for SyncPubAsyncSub
        async def consumer(item):
            pass

        queue = SyncPubAsyncSub(async_consumer=consumer)
        assert callable(queue.publish)

    def test_run_method_exists(self):
        """Test that run method exists."""

        # The consumer must be an asynchronous function for SyncPubAsyncSub
        async def consumer(item):
            pass

        queue = SyncPubAsyncSub(async_consumer=consumer)
        assert hasattr(queue, "run")

    def test_close_method_exists(self):
        """Test that close method exists."""

        # The consumer must be an asynchronous function for SyncPubAsyncSub
        async def consumer(item):
            pass

        queue = SyncPubAsyncSub(async_consumer=consumer)
        assert hasattr(queue, "close")


class TestSyncPubAsyncSubFlow:
    """Full flow tests for SyncPubAsyncSub."""

    async def test_publish_and_consume(self):
        """Published items should be consumed by the async consumer."""
        import asyncio

        results = []

        async def consumer(item):  # NOSONAR
            results.append(item)

        queue = SyncPubAsyncSub(async_consumer=consumer)
        task = asyncio.create_task(queue.run())

        queue.publish("item1")
        queue.publish("item2")

        # Wait until both items are consumed (or timeout)
        deadline = asyncio.get_event_loop().time() + 2.0
        while len(results) < 2 and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.02)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:  # NOSONAR
            pass

        assert "item1" in results
        assert "item2" in results

    async def test_consumer_error_does_not_stop_loop(self):
        """Consumer exceptions should be logged but not stop the loop."""
        import asyncio

        results = []
        call_count = [0]

        async def consumer(item):  # NOSONAR
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Consumer error")
            results.append(item)

        queue = SyncPubAsyncSub(async_consumer=consumer)
        task = asyncio.create_task(queue.run())

        queue.publish("item1")  # Will raise
        queue.publish("item2")  # Should still be consumed

        # Wait for item2 to be consumed
        deadline = asyncio.get_event_loop().time() + 2.0
        while "item2" not in results and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.02)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:  # NOSONAR
            pass

        assert "item2" in results


class TestAsyncPubSyncSubPublish:
    """Tests for AsyncPubSyncSub publish behavior."""

    async def test_publish_does_not_raise(self):
        """publish() should not raise for valid items."""

        # The consumer must be a synchronous function for AsyncPubSyncSub
        def consumer(item):
            pass

        queue = AsyncPubSyncSub(sync_consumer=consumer)
        # publish should complete without error
        await queue.publish("test_item")

    async def test_publish_multiple_items(self):
        """publish() should handle multiple items."""

        # The consumer must be a synchronous function for AsyncPubSyncSub
        def consumer(item):
            pass

        queue = AsyncPubSyncSub(sync_consumer=consumer)
        for i in range(5):
            await queue.publish(f"item-{i}")
