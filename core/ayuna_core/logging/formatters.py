"""
formatters.py - Log formatters for the Ayuna framework.

This module provides custom log formatters that produce JSON-formatted
log output with OpenTelemetry trace correlation.

The DefaultLogFormatter converts log records to JSON objects containing:
- Standard log fields (message, level, timestamp, etc.)
- Extra fields passed to the logger
- OpenTelemetry trace and span IDs (when in a traced context)
- Extended debug information when in DEBUG/TRACE mode
"""

import logging
from decimal import Decimal
from typing import Dict

import orjson as json
from opentelemetry import trace
from opentelemetry.trace.span import INVALID_SPAN

from ..basetypes import LogLevelName
from ..settings import logging_env
from ..utils.chrono import Chrono, dt

# DateTime format for log timestamps
_LOG_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

# Standard LogRecord attributes that should not be treated as "extra" fields
_LOG_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "otelTraceID",
    "otelSpanID",
}

_log_settings = logging_env()

# =============================================================================
# Utility Functions
# =============================================================================


def effective_log_level():
    """
    Determine the effective log level based on settings.

    Returns DEBUG if either LOG_LEVEL is DEBUG/TRACE or DEBUG mode is enabled.

    Returns
    -------
    LogLevelName
        The effective log level to use.
    """
    if _log_settings.log_level in [LogLevelName.DEBUG, LogLevelName.TRACE]:
        return _log_settings.log_level

    if _log_settings.debug:
        return LogLevelName.DEBUG

    return _log_settings.log_level


# =============================================================================
# Log Formatter
# =============================================================================


class DefaultLogFormatter(logging.Formatter):
    """
    JSON log formatter with OpenTelemetry trace correlation.

    Converts log records to JSON objects containing structured log data.
    Automatically includes OpenTelemetry trace and span IDs when logging
    occurs within a traced context.

    In DEBUG/TRACE mode, includes additional fields like module, pathname,
    filename, function name, line number, process ID, thread ID, etc.
    """

    # Types that should be preserved as-is in JSON output
    _keep_attr_types = (bool, int, float, Decimal, complex, str, dt.datetime)

    def format(self, record):
        message = record.getMessage()
        extra = self.extra_from_record(record)
        json_record = self.json_record(message, extra, record)
        mutated_record = self.marshal_time_attrs(json_record)

        # Backwards compatibility: Functions that overwrite marshal_time_attrs
        #  but don't return a new value will return None because they modified
        # the argument passed in.
        if mutated_record is None:
            mutated_record = json_record

        return self.to_json(mutated_record)

    def to_json(self, record: Dict):
        """Converts record dict to a JSON string.

        It makes best effort to serialize a record (represents an object as a string)
        instead of raising TypeError if json library supports default argument.
        Note, ujson doesn't support it.
        ValueError and OverflowError are also caught to avoid crashing an app,
        e.g., due to circular reference.

        Override this method to change the way dict is converted to JSON.
        """
        try:
            return json.dumps(record).decode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return "{}"

    def extra_from_record(self, record: logging.LogRecord):
        """Returns `extra` dict you passed to logger.

        The `extra` keyword argument is used to populate the `__dict__` of
        the `LogRecord`.
        """
        return {
            attr_name: record.__dict__[attr_name]
            for attr_name in record.__dict__
            if attr_name not in _LOG_RECORD_ATTRS
        }

    def json_record(self, message: str, extra: Dict, record: logging.LogRecord):
        """
        Prepares a JSON payload which will be logged.
        Override this method to change JSON log format.

        Parameters
        ----------
        message: str
            Log message, e.g., `logger.info(msg='Sign up')`.
        extra: Dict
            Dictionary that was passed as `extra` param
            `logger.info('Sign up', extra={'referral_code': '52d6ce'})`.
        record: LogRecord
            `LogRecord` we got from `JSONFormatter.format()`.

        Returns
        -------
        Dict
            Dictionary which will be passed to JSON lib
        """
        extra["message"] = message
        extra["levelname"] = record.levelname
        extra["name"] = record.name
        extra["processName"] = record.processName

        effective_level = effective_log_level()

        if effective_level in [LogLevelName.DEBUG, LogLevelName.TRACE]:
            extra["module"] = record.module
            extra["pathname"] = record.pathname
            extra["filename"] = record.filename
            extra["funcName"] = record.funcName
            extra["lineno"] = record.lineno
            extra["process"] = record.process
            extra["thread"] = record.thread
            extra["threadName"] = record.threadName

        if hasattr(record, "stack_info"):
            extra["stack_info"] = record.stack_info
        else:
            extra["stack_info"] = None

        if "asctime" not in extra:
            extra["asctime"] = record.asctime

        if "utctime" not in extra:
            extra["utctime"] = Chrono.get_current_utc_time()

        if record.exc_info:
            extra["exc_info"] = self.formatException(record.exc_info)

        curr_span = trace.get_current_span()

        if curr_span != INVALID_SPAN:
            span_context = curr_span.get_span_context()

            if "otelTraceID" not in extra:
                extra["otelTraceID"] = trace.format_trace_id(span_context.trace_id)

            if "otelSpanID" not in extra:
                extra["otelSpanID"] = trace.format_span_id(span_context.span_id)

        return {
            k: v if (v is None) or isinstance(v, self._keep_attr_types) else str(v)
            for k, v in extra.items()
        }

    def marshal_time_attrs(self, json_record: Dict):
        """Override it to convert fields of `json_record` to needed types."""
        for attr_name in json_record:
            attr = json_record[attr_name]

            if isinstance(attr, dt.datetime):
                attr_str = attr.strftime(_LOG_DATETIME_FORMAT)[:-3]
                json_record[attr_name] = attr_str + attr.strftime("%z")

        return json_record
