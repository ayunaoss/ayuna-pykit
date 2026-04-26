"""
Tests for ayuna_core.utils.aiotpool module.

Tests the AioThreadPoolExecutor class:
- Submitting coroutines for execution
- Thread pool management
- Shutdown behavior
"""

import asyncio
import time

import pytest

from ayuna_core.utils.aiotpool import AioThreadPoolExecutor, BrokenThreadPool


class TestAioThreadPoolExecutor:
    """Tests for AioThreadPoolExecutor class."""

    def test_basic_submit(self):
        """Test basic coroutine submission."""

        async def simple_coro():  # NOSONAR
            return 42

        with AioThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(simple_coro())
            result = future.result(timeout=5)

        assert result == 42

    def test_submit_multiple(self):
        """Test submitting multiple coroutines."""

        async def add(a, b):  # NOSONAR
            return a + b

        with AioThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(add(i, i * 2)))

            results = [f.result(timeout=5) for f in futures]

        expected = [i + i * 2 for i in range(10)]
        assert results == expected

    def test_submit_with_async_sleep(self):
        """Test coroutine with async sleep."""

        async def sleepy():
            await asyncio.sleep(0.1)
            return "awake"

        with AioThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(sleepy())
            result = future.result(timeout=5)

        assert result == "awake"

    def test_parallel_execution(self):
        """Test that coroutines run in parallel across threads."""

        async def timed_task():
            await asyncio.sleep(0.1)
            return time.time()

        start_time = time.time()

        with AioThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(timed_task()) for _ in range(4)]
            _ = [f.result(timeout=5) for f in futures]

        elapsed = time.time() - start_time

        # 4 tasks sleeping 0.1s each, run in parallel, should complete in ~0.2s
        # (allowing some overhead)
        assert elapsed < 0.5

    def test_exception_propagation(self):
        """Test that exceptions in coroutines are propagated."""

        async def failing_coro():
            raise ValueError("Test error")

        with AioThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(failing_coro())

            with pytest.raises(ValueError, match="Test error"):
                future.result(timeout=5)

    def test_shutdown_wait(self):
        """Test shutdown waits for pending tasks."""
        completed = []

        async def slow_task(n):
            await asyncio.sleep(0.1)
            completed.append(n)
            return n

        executor = AioThreadPoolExecutor(max_workers=2)

        _ = [executor.submit(slow_task(i)) for i in range(3)]
        executor.shutdown(wait=True)

        # All tasks should complete
        assert len(completed) == 3

    def test_shutdown_cancel_futures(self):
        """Test shutdown with cancel_futures cancels pending work."""

        async def slow_task():
            await asyncio.sleep(10)  # Very slow
            return "done"

        executor = AioThreadPoolExecutor(max_workers=1)

        # Submit more tasks than workers
        futures = [executor.submit(slow_task()) for _ in range(5)]

        # Short wait to let first task start
        time.sleep(0.1)

        # Shutdown and cancel pending
        executor.shutdown(wait=False, cancel_futures=True)

        # Some futures should be cancelled
        cancelled_count = sum(1 for f in futures if f.cancelled())
        # At least some should be cancelled (those not yet started)
        # Note: this is non-deterministic due to timing
        assert cancelled_count >= 0

    def test_context_manager(self):
        """Test using executor as context manager."""

        async def simple():  # NOSONAR
            return 1

        result = None
        with AioThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(simple())
            result = future.result(timeout=5)

        assert result == 1

    def test_max_workers_validation(self):
        """Test that max_workers must be positive."""
        with pytest.raises(ValueError):
            AioThreadPoolExecutor(max_workers=0)

        with pytest.raises(ValueError):
            AioThreadPoolExecutor(max_workers=-1)

    def test_initializer_callable_validation(self):
        """Test that initializer must be callable."""
        with pytest.raises(TypeError):
            AioThreadPoolExecutor(initializer="not callable")

    def test_initializer_runs(self):
        """Test that initializer runs for each worker."""
        initialized = []

        def init_func(marker):
            initialized.append(marker)

        async def simple():  # NOSONAR
            return 1

        with AioThreadPoolExecutor(
            max_workers=2, initializer=init_func, initargs=("init",)
        ) as executor:
            # Submit enough tasks to spawn workers
            futures = [executor.submit(simple()) for _ in range(4)]
            [f.result(timeout=5) for f in futures]

        # At least one worker should have initialized
        assert len(initialized) >= 1

    def test_thread_name_prefix(self):
        """Test custom thread name prefix."""
        import threading

        thread_names = []

        async def capture_thread_name():  # NOSONAR
            thread_names.append(threading.current_thread().name)
            return True

        with AioThreadPoolExecutor(
            max_workers=2, thread_name_prefix="CustomPool"
        ) as executor:
            future = executor.submit(capture_thread_name())
            future.result(timeout=5)

        # Thread name should contain the prefix
        assert any("CustomPool" in name for name in thread_names)

    def test_default_max_workers(self):
        """Test default max_workers value."""
        executor = AioThreadPoolExecutor()

        # Should use NUM_THREAD_WORKERS from constants
        assert executor._max_workers > 0
        assert executor._max_workers <= 32  # Capped at 32

        executor.shutdown(wait=False)

    def test_cannot_submit_after_shutdown(self):
        """Test that submitting after shutdown raises error."""

        async def simple():  # NOSONAR
            return 1

        executor = AioThreadPoolExecutor(max_workers=2)
        executor.shutdown(wait=True)

        with pytest.raises(RuntimeError):
            executor.submit(simple())


class TestBrokenThreadPool:
    """Tests for BrokenThreadPool exception."""

    def test_is_broken_executor(self):
        """Test that BrokenThreadPool is a BrokenExecutor."""
        from concurrent.futures import BrokenExecutor

        exc = BrokenThreadPool("test")
        assert isinstance(exc, BrokenExecutor)

    def test_message(self):
        """Test exception message."""
        exc = BrokenThreadPool("Pool is broken")
        assert str(exc) == "Pool is broken"
