"""
Tests for ayuna_core.logging module.

Tests the logging components:
- Log filters (CriticalLogFilter, ErrorLogFilter, etc.)
- DefaultLogFormatter
- Log configuration functions
"""

import json
import logging

import pytest

from ayuna_core.basetypes import LogLevelName, LogLevelNumber
from ayuna_core.logging.filters import (
    CriticalLogFilter,
    DebugLogFilter,
    ErrorLogFilter,
    FilterForLogLevel,
    InfoLogFilter,
    TraceLogFilter,
    WarningLogFilter,
    get_filter_class_for_level,
)
from ayuna_core.logging.formatters import (
    DefaultLogFormatter,
    effective_log_level,
)


class TestLogFilters:
    """Tests for log filter classes."""

    @pytest.fixture
    def log_records(self):
        """Fixture that provides log records at different levels."""
        records = {}
        for level_name, level_no in [
            ("TRACE", 5),
            ("DEBUG", 10),
            ("INFO", 20),
            ("WARNING", 30),
            ("ERROR", 40),
            ("CRITICAL", 50),
        ]:
            record = logging.LogRecord(
                name="test",
                level=level_no,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            records[level_name] = record
        return records

    def test_critical_filter(self, log_records):
        """Test CriticalLogFilter only passes CRITICAL level."""
        filter_obj = CriticalLogFilter()

        assert filter_obj.filter(log_records["CRITICAL"]) is True
        assert filter_obj.filter(log_records["ERROR"]) is False
        assert filter_obj.filter(log_records["WARNING"]) is False
        assert filter_obj.filter(log_records["INFO"]) is False
        assert filter_obj.filter(log_records["DEBUG"]) is False
        assert filter_obj.filter(log_records["TRACE"]) is False

    def test_error_filter(self, log_records):
        """Test ErrorLogFilter passes ERROR and above."""
        filter_obj = ErrorLogFilter()

        assert filter_obj.filter(log_records["CRITICAL"]) is True
        assert filter_obj.filter(log_records["ERROR"]) is True
        assert filter_obj.filter(log_records["WARNING"]) is False
        assert filter_obj.filter(log_records["INFO"]) is False
        assert filter_obj.filter(log_records["DEBUG"]) is False

    def test_warning_filter(self, log_records):
        """Test WarningLogFilter passes WARNING and above."""
        filter_obj = WarningLogFilter()

        assert filter_obj.filter(log_records["CRITICAL"]) is True
        assert filter_obj.filter(log_records["ERROR"]) is True
        assert filter_obj.filter(log_records["WARNING"]) is True
        assert filter_obj.filter(log_records["INFO"]) is False
        assert filter_obj.filter(log_records["DEBUG"]) is False

    def test_info_filter(self, log_records):
        """Test InfoLogFilter passes INFO and above."""
        filter_obj = InfoLogFilter()

        assert filter_obj.filter(log_records["CRITICAL"]) is True
        assert filter_obj.filter(log_records["ERROR"]) is True
        assert filter_obj.filter(log_records["WARNING"]) is True
        assert filter_obj.filter(log_records["INFO"]) is True
        assert filter_obj.filter(log_records["DEBUG"]) is False

    def test_debug_filter(self, log_records):
        """Test DebugLogFilter passes DEBUG and above."""
        filter_obj = DebugLogFilter()

        assert filter_obj.filter(log_records["CRITICAL"]) is True
        assert filter_obj.filter(log_records["ERROR"]) is True
        assert filter_obj.filter(log_records["WARNING"]) is True
        assert filter_obj.filter(log_records["INFO"]) is True
        assert filter_obj.filter(log_records["DEBUG"]) is True
        assert filter_obj.filter(log_records["TRACE"]) is False

    def test_trace_filter(self, log_records):
        """Test TraceLogFilter passes all levels."""
        filter_obj = TraceLogFilter()

        assert filter_obj.filter(log_records["CRITICAL"]) is True
        assert filter_obj.filter(log_records["ERROR"]) is True
        assert filter_obj.filter(log_records["WARNING"]) is True
        assert filter_obj.filter(log_records["INFO"]) is True
        assert filter_obj.filter(log_records["DEBUG"]) is True
        assert filter_obj.filter(log_records["TRACE"]) is True


class TestFilterForLogLevel:
    """Tests for FilterForLogLevel mapping."""

    def test_mapping_contains_all_levels(self):
        """Test that all log levels have a filter mapping."""
        assert LogLevelName.CRITICAL in FilterForLogLevel
        assert LogLevelName.ERROR in FilterForLogLevel
        assert LogLevelName.WARNING in FilterForLogLevel
        assert LogLevelName.INFO in FilterForLogLevel
        assert LogLevelName.DEBUG in FilterForLogLevel
        assert LogLevelName.TRACE in FilterForLogLevel

    def test_mapping_returns_correct_filters(self):
        """Test that mapping returns correct filter classes."""
        assert FilterForLogLevel[LogLevelName.CRITICAL] is CriticalLogFilter
        assert FilterForLogLevel[LogLevelName.ERROR] is ErrorLogFilter
        assert FilterForLogLevel[LogLevelName.WARNING] is WarningLogFilter
        assert FilterForLogLevel[LogLevelName.INFO] is InfoLogFilter
        assert FilterForLogLevel[LogLevelName.DEBUG] is DebugLogFilter
        assert FilterForLogLevel[LogLevelName.TRACE] is TraceLogFilter


class TestGetFilterClassForLevel:
    """Tests for get_filter_class_for_level function."""

    def test_get_filter_for_valid_levels(self):
        """Test getting filter for valid log levels."""
        assert get_filter_class_for_level("CRITICAL") is CriticalLogFilter
        assert get_filter_class_for_level("ERROR") is ErrorLogFilter
        assert get_filter_class_for_level("WARNING") is WarningLogFilter
        assert get_filter_class_for_level("INFO") is InfoLogFilter
        assert get_filter_class_for_level("DEBUG") is DebugLogFilter
        assert get_filter_class_for_level("TRACE") is TraceLogFilter

    def test_get_filter_for_aliases(self):
        """Test getting filter for level aliases."""
        # WARN is alias for WARNING
        assert get_filter_class_for_level("WARN") is WarningLogFilter
        # FATAL is alias for CRITICAL
        assert get_filter_class_for_level("FATAL") is CriticalLogFilter

    def test_get_filter_for_invalid_level(self):
        """Test getting filter for invalid level returns InfoLogFilter."""
        assert get_filter_class_for_level("INVALID") is InfoLogFilter
        assert get_filter_class_for_level("UNKNOWN") is InfoLogFilter


class TestDefaultLogFormatter:
    """Tests for DefaultLogFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Fixture that provides a DefaultLogFormatter instance."""
        return DefaultLogFormatter()

    @pytest.fixture
    def log_record(self):
        """Fixture that provides a basic log record."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.asctime = "2024-01-01 12:00:00"
        return record

    def test_format_returns_json(self, formatter, log_record):
        """Test that format returns valid JSON."""
        result = formatter.format(log_record)

        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_format_contains_message(self, formatter, log_record):
        """Test that formatted output contains the message."""
        result = formatter.format(log_record)
        parsed = json.loads(result)

        assert parsed["message"] == "Test message"

    def test_format_contains_level(self, formatter, log_record):
        """Test that formatted output contains the log level."""
        result = formatter.format(log_record)
        parsed = json.loads(result)

        assert parsed["levelname"] == "INFO"

    def test_format_contains_logger_name(self, formatter, log_record):
        """Test that formatted output contains the logger name."""
        result = formatter.format(log_record)
        parsed = json.loads(result)

        assert parsed["name"] == "test.logger"

    def test_format_with_extra_fields(self, formatter):
        """Test that extra fields are included in output."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.asctime = "2024-01-01 12:00:00"
        record.custom_field = "custom_value"
        record.request_id = "req-123"

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["custom_field"] == "custom_value"
        assert parsed["request_id"] == "req-123"

    def test_extra_from_record(self, formatter, log_record):
        """Test extracting extra fields from record."""
        log_record.extra_field = "extra_value"

        extra = formatter.extra_from_record(log_record)

        assert "extra_field" in extra
        assert extra["extra_field"] == "extra_value"
        # Standard fields should not be in extra
        assert "msg" not in extra
        assert "levelno" not in extra

    def test_to_json_handles_errors(self, formatter):
        """Test that to_json handles serialization errors gracefully."""
        # Create a dict with circular reference
        circular = {}
        circular["self"] = circular

        result = formatter.to_json(circular)

        # Should return empty JSON object instead of raising
        assert result == "{}"


class TestEffectiveLogLevel:
    """Tests for effective_log_level function."""

    def test_returns_log_level_name(self):
        """Test that effective_log_level returns a LogLevelName."""
        level = effective_log_level()
        assert isinstance(level, LogLevelName)

    def test_returns_valid_level(self):
        """Test that effective_log_level returns a valid level."""
        level = effective_log_level()
        assert level in [
            LogLevelName.CRITICAL,
            LogLevelName.ERROR,
            LogLevelName.WARNING,
            LogLevelName.INFO,
            LogLevelName.DEBUG,
            LogLevelName.TRACE,
        ]


class TestLogLevelNumbers:
    """Tests for LogLevelNumber enum values."""

    def test_level_numbers_are_correct(self):
        """Test that level numbers match Python logging standard."""
        assert LogLevelNumber.CRITICAL == 50
        assert LogLevelNumber.ERROR == 40
        assert LogLevelNumber.WARNING == 30
        assert LogLevelNumber.INFO == 20
        assert LogLevelNumber.DEBUG == 10
        assert LogLevelNumber.TRACE == 5

    def test_levels_are_ordered(self):
        """Test that levels are properly ordered."""
        assert LogLevelNumber.TRACE < LogLevelNumber.DEBUG
        assert LogLevelNumber.DEBUG < LogLevelNumber.INFO
        assert LogLevelNumber.INFO < LogLevelNumber.WARNING
        assert LogLevelNumber.WARNING < LogLevelNumber.ERROR
        assert LogLevelNumber.ERROR < LogLevelNumber.CRITICAL


class TestGetLogfilePath:
    """Tests for get_logfile_path function."""

    def test_returns_string(self):
        """Should return a string path."""
        from ayuna_core.logging.config import get_logfile_path

        result = get_logfile_path("test-app")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_path_ends_with_log_extension(self):
        """Should return a path ending with .log."""
        from ayuna_core.logging.config import get_logfile_path

        result = get_logfile_path("my-service")

        assert result.endswith(".log")

    def test_different_names_different_paths(self):
        """Different log names should give different paths."""
        from ayuna_core.logging.config import get_logfile_path

        path1 = get_logfile_path("service-a")
        path2 = get_logfile_path("service-b")

        assert path1 != path2


class TestDefaultLogConfig:
    """Tests for default_log_config function."""

    def test_returns_dict(self):
        """Should return a dictionary."""
        from ayuna_core.logging.config import default_log_config

        config = default_log_config(log_name="test-app")

        assert isinstance(config, dict)

    def test_has_required_keys(self):
        """Should have required logging config keys."""
        from ayuna_core.logging.config import default_log_config

        config = default_log_config(log_name="test-app")

        assert config["version"] == 1
        assert "handlers" in config
        assert "formatters" in config
        assert "filters" in config
        assert "root" in config

    def test_has_console_handler(self):
        """Should include console handler by default."""
        from ayuna_core.logging.config import default_log_config

        config = default_log_config(log_name="test-app")

        assert "console" in config["handlers"]

    def test_root_includes_console(self):
        """Root logger should include console handler."""
        from ayuna_core.logging.config import default_log_config

        config = default_log_config(log_name="test-app")

        assert "console" in config["root"]["handlers"]

    def test_has_standard_formatter(self):
        """Should have a standard formatter."""
        from ayuna_core.logging.config import default_log_config

        config = default_log_config(log_name="test-app")

        assert "standard" in config["formatters"]

    def test_has_standard_filter(self):
        """Should have a standard filter."""
        from ayuna_core.logging.config import default_log_config

        config = default_log_config(log_name="test-app")

        assert "standard" in config["filters"]


class TestMprocQlogConfig:
    """Tests for mproc_qlog_config function."""

    def test_returns_dict(self):
        """Should return a dictionary."""
        from multiprocessing import Queue

        from ayuna_core.logging.config import mproc_qlog_config

        q = Queue()
        try:
            config = mproc_qlog_config(log_queue=q)
            assert isinstance(config, dict)
        finally:
            q.close()

    def test_has_required_keys(self):
        """Should have required logging config keys."""
        from multiprocessing import Queue

        from ayuna_core.logging.config import mproc_qlog_config

        q = Queue()
        try:
            config = mproc_qlog_config(log_queue=q)
            assert config["version"] == 1
            assert "handlers" in config
            assert "root" in config
        finally:
            q.close()

    def test_has_queue_listener_handler(self):
        """Should include queue_listener handler."""
        from multiprocessing import Queue

        from ayuna_core.logging.config import mproc_qlog_config

        q = Queue()
        try:
            config = mproc_qlog_config(log_queue=q)
            assert "queue_listener" in config["handlers"]
        finally:
            q.close()

    def test_main_process_disables_existing_loggers(self):
        """Should set disable_existing_loggers=True for main process."""
        from multiprocessing import Queue

        from ayuna_core.logging.config import mproc_qlog_config

        q = Queue()
        try:
            config = mproc_qlog_config(log_queue=q, is_main_process=True)
            assert config["disable_existing_loggers"] is True
        finally:
            q.close()

    def test_worker_process_keeps_existing_loggers(self):
        """Should set disable_existing_loggers=False for worker process."""
        from multiprocessing import Queue

        from ayuna_core.logging.config import mproc_qlog_config

        q = Queue()
        try:
            config = mproc_qlog_config(log_queue=q, is_main_process=False)
            assert config["disable_existing_loggers"] is False
        finally:
            q.close()


class TestMprocLogQueueListener:
    """Tests for MprocLogQueueListener class."""

    def test_instantiation(self):
        """Should instantiate with queue and config."""
        from multiprocessing import Queue

        from ayuna_core.logging.handlers import MprocLogQueueListener

        q = Queue()
        try:
            listener = MprocLogQueueListener(queue=q, config={})
            assert listener is not None
            assert listener._log_process is None
        finally:
            q.close()

    def test_dequeue_returns_item(self):
        """Should return items placed in the queue."""
        from multiprocessing import Queue

        from ayuna_core.logging.handlers import MprocLogQueueListener

        q = Queue()
        try:
            listener = MprocLogQueueListener(queue=q, config={})

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )
            q.put(record)

            dequeued = listener.dequeue(block=True, timeout=2.0)
            assert dequeued.msg == "test message"
        finally:
            q.close()

    def test_prepare_updates_process_name(self):
        """Should update processName when processes differ."""
        from multiprocessing import Queue

        from ayuna_core.logging.handlers import MprocLogQueueListener

        q = Queue()
        try:
            listener = MprocLogQueueListener(queue=q, config={})

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test",
                args=(),
                exc_info=None,
            )
            record.processName = "OtherProcess"

            prepared = listener.prepare(record)
            assert "OtherProcess" in prepared.processName
        finally:
            q.close()

    def test_enqueue_sentinel_puts_sentinel(self):
        """Should put the sentinel record onto the queue."""
        from multiprocessing import Queue

        from ayuna_core.logging.handlers import _LOG_SENTINEL, MprocLogQueueListener

        q = Queue()
        try:
            listener = MprocLogQueueListener(queue=q, config={})
            listener.enqueue_sentinel()

            item = q.get(block=True, timeout=2.0)
            # After multiprocessing queue pickling/unpickling, identity check fails;
            # use attribute equality instead.
            assert item.name == _LOG_SENTINEL.name
            assert item.msg == _LOG_SENTINEL.msg
        finally:
            q.close()

    def test_stop_without_start_is_safe(self):
        """Should not raise when stop() is called without start()."""
        from multiprocessing import Queue

        from ayuna_core.logging.handlers import MprocLogQueueListener

        q = Queue()
        try:
            listener = MprocLogQueueListener(queue=q, config={})
            listener.stop()  # Should not raise
            assert listener._log_process is None
        finally:
            q.close()


class TestMprocLogQueueHandler:
    """Tests for MprocLogQueueHandler class."""

    def test_instantiation_worker_mode(self):
        """Should instantiate in worker mode without starting listener."""
        from multiprocessing import Queue

        from ayuna_core.logging.config import default_log_config
        from ayuna_core.logging.handlers import MprocLogQueueHandler

        q = Queue()
        try:
            config = default_log_config(log_name="test")
            handler = MprocLogQueueHandler(
                log_queue=q, log_config=config, is_main_process=False
            )
            assert handler is not None
        finally:
            q.close()

    def test_emit_picklable_record(self):
        """Should enqueue picklable log records."""
        from multiprocessing import Queue

        from ayuna_core.logging.config import default_log_config
        from ayuna_core.logging.handlers import MprocLogQueueHandler

        q = Queue()
        try:
            config = default_log_config(log_name="test")
            handler = MprocLogQueueHandler(
                log_queue=q, log_config=config, is_main_process=False
            )

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="hello world",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

            queued = q.get(block=True, timeout=2.0)
            assert queued.msg == "hello world"
        finally:
            q.close()

    def test_emit_unpicklable_record_is_dropped(self):
        """Should silently drop unpicklable records."""
        from multiprocessing import Queue

        from ayuna_core.logging.config import default_log_config
        from ayuna_core.logging.handlers import MprocLogQueueHandler

        q = Queue()
        try:
            config = default_log_config(log_name="test")
            handler = MprocLogQueueHandler(
                log_queue=q, log_config=config, is_main_process=False
            )

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test",
                args=(),
                exc_info=None,
            )
            # Lambdas are not picklable
            record.unpicklable = lambda: None

            handler.emit(record)

            # Queue should be empty — record was dropped
            assert q.empty()
        finally:
            q.close()
