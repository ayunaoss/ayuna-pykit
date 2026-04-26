"""
handlers.py - Custom logging handlers for the Ayuna framework.

This module provides multiprocess-safe logging handlers:

- MprocLogQueueListener: Runs in a separate process to handle log records
  from a multiprocessing queue
- MprocLogQueueHandler: Sends log records to a multiprocessing queue

Together, these enable safe logging from multiple processes to shared
handlers (console, files, etc.) without corruption or interleaving.

Usage
-----
1. Create a multiprocessing.Queue
2. In main process: Use mproc_qlog_config with is_main_process=True
3. In worker processes: Use mproc_qlog_config with is_main_process=False
"""

import asyncio
import atexit
import pickle
from logging import LogRecord, getLogger
from logging.config import dictConfig
from logging.handlers import QueueHandler
from multiprocessing import Queue as MprocQueue
from multiprocessing import current_process
from typing import Any, Dict

from ..basefuncs import ayuna_mproc_context
from ..constants import LOOP_BREAK_MSG

# Sentinel LogRecord used to signal the listener to stop
_LOG_SENTINEL = LogRecord(
    name="AYUNA_LOG_SENTINEL",
    level=0,
    pathname="",
    lineno=0,
    msg="AYUNA_LOG_SENTINEL",
    args=(),
    exc_info=None,
)

# =============================================================================
# Queue Listener
# =============================================================================


class MprocLogQueueListener:
    """
    Multiprocess log queue listener that runs in a separate process.

    Reads log records from a multiprocessing queue and dispatches them
    to configured handlers. This enables safe centralized logging from
    multiple worker processes.

    The listener runs in its own process (not a thread) to avoid GIL
    contention and ensure true parallelism with worker processes.

    Parameters
    ----------
    queue : MprocQueue
        Queue to read log records from.
    config : Dict[str, Any]
        Logging configuration for the actual handlers.
    """

    def __init__(self, queue: MprocQueue, config: Dict[str, Any]):
        """
        Initialize the multiprocessing queue listener.

        Parameters
        ----------
        queue : MprocQueue
            Multiprocessing queue to read log records from.
        config : Dict[str, Any]
            Logging configuration dictionary for the actual handlers.
            This should NOT contain the 'queue_listener' handler.
        """
        self.queue = queue
        self.config = config
        self._log_process = None

    def dequeue(self, block: bool = True, timeout: float | None = None):
        """
        Dequeue a log record from the queue.

        Parameters
        ----------
        block : bool, optional
            Whether to block waiting for a record (default: True).
        timeout : float | None, optional
            Maximum time to wait if blocking.

        Returns
        -------
        LogRecord
            The dequeued log record.
        """
        return self.queue.get(block=block, timeout=timeout)

    def start(self):
        """
        Start the listener process.

        Spawns a separate process that monitors the queue and
        dispatches records to the configured handlers.
        """
        mproc_context = ayuna_mproc_context()
        self._log_process = mproc_context.Process(
            name="ayuna-mproc-queue-listener", target=self._monitor
        )

        self._log_process.start()

    def prepare(self, record: LogRecord):
        """
        Prepare a log record for handling.

        Updates the processName to include the routing path from
        the originating process to the listener process.

        Parameters
        ----------
        record : LogRecord
            Record to prepare.

        Returns
        -------
        LogRecord
            The prepared record.
        """
        curr_proc_name = current_process().name

        if curr_proc_name != record.processName:
            record.processName = f"{curr_proc_name}->{record.processName}"

        return record

    def handle(self, record: LogRecord):
        """
        Dispatch a log record to the appropriate logger's handlers.

        Parameters
        ----------
        record : LogRecord
            Record to handle.
        """
        record = self.prepare(record)

        if record.name == "root":
            rec_logger = getLogger()
        else:
            rec_logger = getLogger(record.name)

        for handler in rec_logger.handlers:
            if record.levelno >= handler.level:
                handler.handle(record)

    def _monitor(self):
        """
        Main loop that monitors the queue and dispatches records.

        Runs in the listener process. Continues until a sentinel
        record or LOOP_BREAK_MSG is received.
        """
        dictConfig(config=self.config)

        while True:
            try:
                record = self.dequeue(True)

                if (record is not LOOP_BREAK_MSG) and (record is not _LOG_SENTINEL):
                    self.handle(record=record)
                    continue

                if record is LOOP_BREAK_MSG:
                    print("Received break-event, exiting...")
                else:
                    print("Received sentinel record, exiting...")

                root_handler = getLogger()

                for hndl in root_handler.handlers:
                    hndl.flush()
                    hndl.close()

                break
            except KeyboardInterrupt:
                self.enqueue_sentinel()
            except Exception:
                import sys
                import traceback

                print("Multi-process log processing failed", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

    def enqueue_sentinel(self):
        """Signal the listener to stop by enqueueing the sentinel record."""
        self.queue.put_nowait(_LOG_SENTINEL)

    def stop(self):
        """
        Stop the listener process.

        Sends the sentinel record and waits for the process to terminate.
        Should be called before application exit to ensure all records
        are processed.
        """
        if self._log_process and self._log_process.is_alive():
            self.enqueue_sentinel()
            self._log_process.join()
            self._log_process.close()

        self._log_process = None


# =============================================================================
# Queue Handler
# =============================================================================


class MprocLogQueueHandler(QueueHandler):
    """
    Log handler that sends records to a multiprocessing queue.

    In the main process, also starts a MprocLogQueueListener to
    consume records from the queue. In worker processes, simply
    enqueues records.

    Parameters
    ----------
    log_queue : MprocQueue
        Queue to send log records to.
    log_config : Dict[str, Any]
        Configuration for the listener's actual handlers.
    is_main_process : bool, optional
        True if this is the main process (starts listener).
    """

    def __init__(
        self,
        log_queue: MprocQueue,
        log_config: Dict[str, Any],
        is_main_process: bool = False,
    ):
        """Initialize the queue handler and optionally start the listener."""
        super().__init__(queue=log_queue)

        if is_main_process:
            self._listener = MprocLogQueueListener(queue=log_queue, config=log_config)
            self._listener.start()
            atexit.register(self._listener.stop)

    def emit(self, record: LogRecord):
        """
        Emit a log record by enqueueing it.

        Verifies the record is picklable before enqueueing to avoid
        breaking the queue with unpicklable objects.

        Parameters
        ----------
        record : LogRecord
            Record to emit.
        """
        try:
            pickle.dumps(obj=record, protocol=pickle.DEFAULT_PROTOCOL)
            self.enqueue(record=record)
        except asyncio.CancelledError:
            raise
        except (pickle.PickleError, TypeError, AttributeError):
            pass  # Silently drop unpicklable records
        except Exception:
            self.handleError(record=record)
