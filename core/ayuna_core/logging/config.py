"""
config.py - Logging configuration utilities for the Ayuna framework.

This module provides functions for creating logging configuration
dictionaries suitable for use with logging.config.dictConfig():

- default_log_config(): Creates a standard logging config with console
  and optional rotating file handlers
- mproc_qlog_config(): Creates a multiprocess-safe logging config using
  a queue-based handler for cross-process logging

The configurations use JSON formatting and integrate with OpenTelemetry
for trace correlation.
"""

import os
from multiprocessing import Queue as MprocQueue
from typing import Any, Dict

from ..basefuncs import filename_by_sysinfo
from ..constants import (
    DEFAULT_LOG_FORMAT,
    ROTATING_FILE_HANDLER_CLS,
    STREAM_LOG_HANDLER_CLS,
)
from ..fileops import is_dir_writable
from ..settings import logging_env
from .filters import get_filter_class_for_level
from .formatters import DefaultLogFormatter, effective_log_level

# Load global logging settings
__log_settings = logging_env()
__log_level = effective_log_level()

# =============================================================================
# Configuration Functions
# =============================================================================


def get_logfile_path(log_name: str):
    """
    Determine the path for a log file based on the log name.

    Creates the log directory if it doesn't exist. Falls back to
    current working directory if the configured log directory is
    not writable.

    Parameters
    ----------
    log_name : str
        Base name for the log file.

    Returns
    -------
    str
        Full path to the log file.
    """
    base_dir = __log_settings.logs_base_dir
    filename = filename_by_sysinfo(basename=log_name, extension=".log")

    if is_dir_writable(dir_path=base_dir, check_creatable=True):
        os.makedirs(base_dir, exist_ok=True)
        logfile_path = os.path.join(base_dir, filename)

        return logfile_path

    return os.path.join(os.getcwd(), filename)


def default_log_config(log_name: str, log_format: str = DEFAULT_LOG_FORMAT):
    """
    Create a standard logging configuration dictionary.

    Creates a configuration suitable for logging.config.dictConfig() with:
    - Console handler for stdout logging
    - Optional rotating file handler (if ENABLE_FILE_LOGGING is set)
    - JSON formatting via DefaultLogFormatter
    - Log level filtering

    Parameters
    ----------
    log_name : str
        Base name for log files (used if file logging is enabled).
    log_format : str, optional
        Log format string (default: DEFAULT_LOG_FORMAT).

    Returns
    -------
    Dict[str, Any]
        Logging configuration dictionary for dictConfig().
    """
    log_handlers: Dict[str, Dict[str, Any]] = {
        "console": {
            "formatter": "standard",
            "filters": ["standard"],
            "class": STREAM_LOG_HANDLER_CLS,
            "level": __log_level,
        }
    }
    root_handlers = ["console"]

    if __log_settings.enable_file_logging:
        log_handlers["rotated_file"] = {
            "class": ROTATING_FILE_HANDLER_CLS,
            "formatter": "standard",
            "filters": ["standard"],
            "level": __log_level,
            "filename": get_logfile_path(log_name=log_name),
            "encoding": "utf-8",
            "maxBytes": __log_settings.log_max_file_bytes,
            "backupCount": __log_settings.log_max_file_count,
            "mode": "a",
        }

        root_handlers.append("rotated_file")

    log_config = {
        "version": 1,
        "disable_existing_loggers": True,
        "filters": {"standard": {"()": get_filter_class_for_level(__log_level)}},
        "formatters": {"standard": {"()": DefaultLogFormatter, "format": log_format}},
        "handlers": log_handlers,
        "root": {"handlers": root_handlers, "level": __log_level},
    }

    return log_config


# Pre-built default configuration for ayuna applications
__default_log_config = default_log_config(log_name="ayuna-app")


def mproc_qlog_config(
    log_queue: MprocQueue,
    *,
    log_config: Dict[str, Any] = __default_log_config,
    log_format: str = DEFAULT_LOG_FORMAT,
    is_main_process: bool = False,
):
    """
    Create a multiprocess-safe logging configuration.

    Creates a configuration that uses a queue-based handler for
    safe logging across multiple processes. The main process runs
    a listener that reads from the queue and forwards to actual handlers.

    Parameters
    ----------
    log_queue : MprocQueue
        Multiprocessing queue for log record communication.
    log_config : Dict[str, Any], optional
        Configuration for the actual handlers (used by the listener).
    log_format : str, optional
        Log format string.
    is_main_process : bool, optional
        True if this is the main process (starts the listener).

    Returns
    -------
    Dict[str, Any]
        Logging configuration dictionary for dictConfig().
    """
    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": is_main_process,
        "filters": {"standard": {"()": get_filter_class_for_level(__log_level)}},
        "formatters": {"standard": {"()": DefaultLogFormatter, "format": log_format}},
        "handlers": {
            "queue_listener": {
                "class": "ayuna_core.logging.handlers.MprocLogQueueHandler",
                "log_queue": log_queue,
                "log_config": log_config,
                "is_main_process": is_main_process,
            }
        },
        "root": {"handlers": ["queue_listener"], "level": __log_level},
    }

    return config
