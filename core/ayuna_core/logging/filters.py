"""
filters.py - Log level filters for the Ayuna framework.

This module provides log filter classes that filter records based on
their log level. Each filter passes records at or above its level.

The filters are used in logging configurations to control which
messages are processed by each handler.
"""

from logging import Filter as LogFilter
from typing import Dict

from ..basetypes import LogLevelName, LogLevelNumber

# =============================================================================
# Log Level Filter Classes
# =============================================================================


class CriticalLogFilter(LogFilter):
    """Filter that passes records with level >= CRITICAL (50)."""

    def filter(self, record):
        return record.levelno >= LogLevelNumber.CRITICAL


class ErrorLogFilter(LogFilter):
    """Filter that passes records with level >= ERROR (40)."""

    def filter(self, record):
        return record.levelno >= LogLevelNumber.ERROR


class WarningLogFilter(LogFilter):
    """Filter that passes records with level >= WARNING (30)."""

    def filter(self, record):
        return record.levelno >= LogLevelNumber.WARNING


class InfoLogFilter(LogFilter):
    """Filter that passes records with level >= INFO (20)."""

    def filter(self, record):
        return record.levelno >= LogLevelNumber.INFO


class DebugLogFilter(LogFilter):
    """Filter that passes records with level >= DEBUG (10)."""

    def filter(self, record):
        return record.levelno >= LogLevelNumber.DEBUG


class TraceLogFilter(LogFilter):
    """Filter that passes records with level >= TRACE (5)."""

    def filter(self, record):
        return record.levelno >= LogLevelNumber.TRACE


# Mapping from log level names to their corresponding filter classes
FilterForLogLevel: Dict[LogLevelName, type[LogFilter]] = {
    LogLevelName.CRITICAL: CriticalLogFilter,
    LogLevelName.ERROR: ErrorLogFilter,
    LogLevelName.WARNING: WarningLogFilter,
    LogLevelName.INFO: InfoLogFilter,
    LogLevelName.DEBUG: DebugLogFilter,
    LogLevelName.TRACE: TraceLogFilter,
}


def get_filter_class_for_level(log_level: str):
    """
    Returns the filter class for a given log level

    Parameters
    ----------
    log_level: str
        The log level

    Returns
    -------
    type[LogFilter]
        The filter class
    """
    _level = log_level

    if _level == "WARN":
        _level = LogLevelName.WARNING
    elif _level == "FATAL":
        _level = LogLevelName.CRITICAL

    ## Check if _level is a valid LogLevelName
    if not isinstance(_level, LogLevelName):
        try:
            _level = LogLevelName(_level)
        except ValueError:
            return InfoLogFilter

    if _level in FilterForLogLevel:
        return FilterForLogLevel[_level]

    return InfoLogFilter
