"""
test_constants.py - Tests for ayuna_core.constants module.
"""

from ayuna_core.constants import (
    ALLCHARS_REGEX,
    ALLOWED_DATETIME_FORMATS,
    DEFAULT_COMPRESS_LEVEL,
    DEFAULT_LOG_FORMAT,
    DEFAULT_WORD_DELIMITERS,
    LOOP_BREAK_MSG,
    NOCTX,
    NODATA,
    NOID,
    NUM_PROCESS_WORKERS,
    NUM_THREAD_WORKERS,
    ROTATING_FILE_HANDLER_CLS,
    SERVICE_INST_ID_KEY,
    STREAM_LOG_HANDLER_CLS,
    TYPE_MOD_NAME,
)


class TestSystemResourceConstants:
    """Tests for system resource constants."""

    def test_num_process_workers_is_positive(self):
        """NUM_PROCESS_WORKERS should be a positive integer."""
        assert isinstance(NUM_PROCESS_WORKERS, int)
        assert NUM_PROCESS_WORKERS >= 1

    def test_num_thread_workers_is_positive(self):
        """NUM_THREAD_WORKERS should be a positive integer."""
        assert isinstance(NUM_THREAD_WORKERS, int)
        assert NUM_THREAD_WORKERS >= 1

    def test_num_thread_workers_capped_at_32(self):
        """NUM_THREAD_WORKERS should not exceed 32."""
        assert NUM_THREAD_WORKERS <= 32

    def test_loop_break_msg_is_none(self):
        """LOOP_BREAK_MSG should be None (used as sentinel)."""
        assert LOOP_BREAK_MSG is None


class TestSentinelConstants:
    """Tests for type sentinel constants."""

    def test_noid_is_singleton_sentinel(self):
        """NOID should be a singleton sentinel (not a plain string)."""
        from ayuna_core.constants import _NoIdSentinel

        assert isinstance(NOID, _NoIdSentinel)
        assert NOID is _NoIdSentinel()  # singleton: same instance every time

    def test_noctx_is_string(self):
        """NOCTX should be a non-empty string."""
        assert isinstance(NOCTX, str)
        assert len(NOCTX) > 0

    def test_nodata_is_string(self):
        """NODATA should be a non-empty string."""
        assert isinstance(NODATA, str)
        assert len(NODATA) > 0

    def test_sentinels_are_unique(self):
        """All sentinel values should be unique."""
        sentinels = {NOID, NOCTX, NODATA}
        assert len(sentinels) == 3


class TestSerializationConstants:
    """Tests for serialization constants."""

    def test_type_mod_name_is_string(self):
        """TYPE_MOD_NAME should be a string."""
        assert isinstance(TYPE_MOD_NAME, str)
        assert TYPE_MOD_NAME == "_typmod"

    def test_default_word_delimiters(self):
        """DEFAULT_WORD_DELIMITERS should contain common delimiters."""
        assert " " in DEFAULT_WORD_DELIMITERS
        assert "-" in DEFAULT_WORD_DELIMITERS
        assert "_" in DEFAULT_WORD_DELIMITERS

    def test_allchars_regex_is_valid_pattern(self):
        """ALLCHARS_REGEX should be a valid regex pattern template."""
        import re

        # Should be formattable and result in valid regex
        pattern = ALLCHARS_REGEX.format(re.escape(" -_"))
        compiled = re.compile(pattern)
        assert compiled.match("   ") is not None


class TestLoggingConstants:
    """Tests for logging constants."""

    def test_service_inst_id_key(self):
        """SERVICE_INST_ID_KEY should be a valid OTEL key."""
        assert SERVICE_INST_ID_KEY == "service.instance.id"

    def test_stream_log_handler_cls(self):
        """STREAM_LOG_HANDLER_CLS should be valid class path."""
        assert STREAM_LOG_HANDLER_CLS == "logging.StreamHandler"

    def test_rotating_file_handler_cls(self):
        """ROTATING_FILE_HANDLER_CLS should be valid class path."""
        assert ROTATING_FILE_HANDLER_CLS == "logging.handlers.RotatingFileHandler"

    def test_default_log_format_contains_placeholders(self):
        """DEFAULT_LOG_FORMAT should contain common log placeholders."""
        assert "%(levelname)s" in DEFAULT_LOG_FORMAT
        assert "%(asctime)s" in DEFAULT_LOG_FORMAT
        assert "%(message)s" in DEFAULT_LOG_FORMAT


class TestCompressionConstants:
    """Tests for compression constants."""

    def test_default_compress_level_in_range(self):
        """DEFAULT_COMPRESS_LEVEL should be in valid range."""
        assert isinstance(DEFAULT_COMPRESS_LEVEL, int)
        assert 0 <= DEFAULT_COMPRESS_LEVEL <= 9


class TestDateTimeFormatConstants:
    """Tests for datetime format constants."""

    def test_allowed_datetime_formats_is_list(self):
        """ALLOWED_DATETIME_FORMATS should be a list of strings."""
        assert isinstance(ALLOWED_DATETIME_FORMATS, list)
        assert len(ALLOWED_DATETIME_FORMATS) > 0
        assert all(isinstance(fmt, str) for fmt in ALLOWED_DATETIME_FORMATS)

    def test_datetime_formats_are_valid(self):
        """All datetime formats should be valid strptime formats."""
        import datetime

        test_date = datetime.datetime(2024, 1, 15, 10, 30, 45, 123456)

        for fmt in ALLOWED_DATETIME_FORMATS:
            # Some formats require timezone, skip those for basic validation
            if "%z" not in fmt and "%Z" not in fmt:
                formatted = test_date.strftime(fmt)
                parsed = datetime.datetime.strptime(formatted, fmt)
                assert parsed is not None
