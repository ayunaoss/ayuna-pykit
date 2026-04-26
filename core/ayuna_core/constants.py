"""
constants.py - Core constants and configuration values for the Ayuna framework.

This module defines global constants used throughout the ayuna_core library,
including worker pool sizes, sentinel values, logging configuration,
datetime formats, and other framework-wide settings.
"""

from os import cpu_count
from typing import List

# =============================================================================
# System Resource Constants
# =============================================================================

# Get the number of CPU cores available on the system, defaulting to 1 if unavailable
_OS_CPU_COUNT = cpu_count() or 1

# Number of worker processes for multiprocessing pools (matches CPU core count)
NUM_PROCESS_WORKERS = _OS_CPU_COUNT

# Number of worker threads for thread pools
# Uses cpu_count + 4 to account for I/O-bound tasks, capped at 32 to prevent
# excessive resource consumption on high-core systems
NUM_THREAD_WORKERS = min(32, _OS_CPU_COUNT + 4)

# Sentinel value used to signal loop termination in async queues and workers
LOOP_BREAK_MSG = None

# =============================================================================
# Type Sentinel Constants
# =============================================================================
# These sentinel values are used to represent "not provided" or "missing"
# states in a way that's distinguishable from None or empty values

class _NoIdSentinel:
    """Singleton sentinel representing an absent JSON-RPC id field (notification marker)."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "NOID"

    def __str__(self):
        return "NOID"


# Sentinel indicating no identifier was provided (JSON-RPC notification marker)
NOID = _NoIdSentinel()

# Sentinel indicating no context was provided
NOCTX = "<TypNoCtx>"

# Sentinel indicating no data was provided
NODATA = "<TypNoData>"

# =============================================================================
# Serialization Constants
# =============================================================================

# Key name used to store the fully qualified type/module name in serialized
# Pydantic models for polymorphic deserialization
TYPE_MOD_NAME = "_typmod"

# Default word delimiters used in string case conversion utilities
DEFAULT_WORD_DELIMITERS = " -_"

# Regex template for matching all occurrences of specified characters
# Used with .format() to insert escaped delimiter characters
ALLCHARS_REGEX = r"[{}]+"

# =============================================================================
# Logging Constants
# =============================================================================

# OpenTelemetry resource attribute key for service instance identification
SERVICE_INST_ID_KEY = "service.instance.id"

# Fully qualified class name for the standard stream (console) log handler
STREAM_LOG_HANDLER_CLS = "logging.StreamHandler"

# Fully qualified class name for the rotating file log handler
# Used for log rotation based on file size
ROTATING_FILE_HANDLER_CLS = "logging.handlers.RotatingFileHandler"

# Default log message format string
# Includes: log level, timestamp, logger name, module name, and message
DEFAULT_LOG_FORMAT = "%(levelname)s - %(asctime)s - %(name)s - %(module)s - %(message)s"

# =============================================================================
# Compression Constants
# =============================================================================

# Default compression level for archiving utilities (gzip, lz4, zstd)
# Range typically 0-9 for gzip, 0-16 for lz4, 0-22 for zstd
DEFAULT_COMPRESS_LEVEL = 6

# =============================================================================
# DateTime Format Constants
# =============================================================================

# List of supported datetime string formats for parsing
# Ordered from most specific (with timezone) to least specific
# Used by Chrono.str_to_datetime() to attempt parsing in order
ALLOWED_DATETIME_FORMATS: List[str] = [
    "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO 8601 with numeric timezone offset
    "%Y-%m-%dT%H:%M:%S.%f%Z",  # ISO 8601 with timezone name
    "%Y-%m-%dT%H:%M:%S.%f",  # ISO 8601 without timezone
    "%Y-%m-%d %H:%M:%S.%f",  # Space-separated with microseconds
    "%Y-%m-%d %H:%M:%S",  # Space-separated without microseconds
]
