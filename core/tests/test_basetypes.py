"""
test_basetypes.py - Tests for ayuna_core.basetypes module.
"""

import asyncio
import datetime as dt

import pytest
from pydantic import ValidationError

from ayuna_core.basetypes import (
    AioErrorItem,
    AwaitCondition,
    AyunaError,
    CoreData,
    DateTimeRange,
    EmptyStr,
    FlexData,
    LogLevelName,
    LogLevelNumber,
    NonEmptyStr,
    RiSingletonMeta,
    SingletonMeta,
    SnakeCaseStr,
)
from ayuna_core.constants import TYPE_MOD_NAME


class TestConstrainedStringTypes:
    """Tests for constrained string type aliases."""

    def test_empty_str_accepts_empty(self):
        """EmptyStr should accept empty strings."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: EmptyStr

        model = TestModel(value="")
        assert model.value == ""

    def test_empty_str_rejects_non_empty(self):
        """EmptyStr should reject non-empty strings."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: EmptyStr

        with pytest.raises(ValidationError):
            TestModel(value="not empty")

    def test_non_empty_str_accepts_non_empty(self):
        """NonEmptyStr should accept non-empty strings."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: NonEmptyStr

        model = TestModel(value="hello")
        assert model.value == "hello"

    def test_non_empty_str_rejects_empty(self):
        """NonEmptyStr should reject empty strings."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: NonEmptyStr

        with pytest.raises(ValidationError):
            TestModel(value="")

    def test_snake_case_str_accepts_valid(self):
        """SnakeCaseStr should accept valid snake_case strings."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: SnakeCaseStr

        model = TestModel(value="hello_world_123")
        assert model.value == "hello_world_123"

    def test_snake_case_str_rejects_invalid(self):
        """SnakeCaseStr should reject invalid strings."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: SnakeCaseStr

        # Contains uppercase
        with pytest.raises(ValidationError):
            TestModel(value="Hello_World")

        # Contains hyphen
        with pytest.raises(ValidationError):
            TestModel(value="hello-world")


class TestAyunaError:
    """Tests for AyunaError exception class."""

    def test_basic_error(self):
        """AyunaError should store error message."""
        error = AyunaError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.exc_cause is None

    def test_error_with_cause(self):
        """AyunaError should include cause in string representation."""
        cause = ValueError("Original error")
        error = AyunaError("Wrapped error", exc_cause=cause)
        error_str = str(error)
        assert "Wrapped error" in error_str
        assert "caused by" in error_str
        assert "ValueError" in error_str

    def test_error_is_exception(self):
        """AyunaError should be raiseable."""
        with pytest.raises(AyunaError):
            raise AyunaError("Test error")


class TestLogLevelEnums:
    """Tests for log level enumerations."""

    def test_log_level_name_values(self):
        """LogLevelName should have correct string values."""
        assert LogLevelName.CRITICAL == "CRITICAL"
        assert LogLevelName.ERROR == "ERROR"
        assert LogLevelName.WARNING == "WARNING"
        assert LogLevelName.INFO == "INFO"
        assert LogLevelName.DEBUG == "DEBUG"
        assert LogLevelName.TRACE == "TRACE"

    def test_log_level_number_values(self):
        """LogLevelNumber should have correct numeric values."""
        assert LogLevelNumber.CRITICAL == 50
        assert LogLevelNumber.ERROR == 40
        assert LogLevelNumber.WARNING == 30
        assert LogLevelNumber.INFO == 20
        assert LogLevelNumber.DEBUG == 10
        assert LogLevelNumber.TRACE == 5

    def test_log_levels_are_ordered(self):
        """Log level numbers should be in descending order of severity."""
        assert LogLevelNumber.CRITICAL > LogLevelNumber.ERROR
        assert LogLevelNumber.ERROR > LogLevelNumber.WARNING
        assert LogLevelNumber.WARNING > LogLevelNumber.INFO
        assert LogLevelNumber.INFO > LogLevelNumber.DEBUG
        assert LogLevelNumber.DEBUG > LogLevelNumber.TRACE


class TestAwaitCondition:
    """Tests for AwaitCondition enumeration."""

    def test_await_condition_values(self):
        """AwaitCondition should map to asyncio constants."""
        assert AwaitCondition.ALL_DONE == asyncio.ALL_COMPLETED
        assert AwaitCondition.ANY_DONE == asyncio.FIRST_COMPLETED
        assert AwaitCondition.ANY_FAIL == asyncio.FIRST_EXCEPTION


class TestAioErrorItem:
    """Tests for AioErrorItem model."""

    def test_create_error_item(self):
        """Should create AioErrorItem with name and message."""
        item = AioErrorItem(name="ValueError", message="Invalid value")
        assert item.name == "ValueError"
        assert item.message == "Invalid value"

    def test_error_item_serialization(self):
        """AioErrorItem should serialize to dict."""
        item = AioErrorItem(name="TestError", message="Test message")
        data = item.model_dump()
        assert data["name"] == "TestError"
        assert data["message"] == "Test message"


class TestSingletonMeta:
    """Tests for SingletonMeta metaclass."""

    def test_singleton_returns_same_instance(self):
        """SingletonMeta should return the same instance."""

        class MySingleton(metaclass=SingletonMeta):
            def __init__(self, value):
                self.value = value

        instance1 = MySingleton(1)
        instance2 = MySingleton(2)

        assert instance1 is instance2
        assert instance1.value == 1  # First value is kept

    def test_singleton_get_instance(self):
        """SingletonMeta should add get_instance class method."""

        class MySingleton2(metaclass=SingletonMeta):
            def __init__(self, value):
                self.value = value

        instance = MySingleton2(42)
        assert MySingleton2.get_instance() is instance


class TestRiSingletonMeta:
    """Tests for RiSingletonMeta (reinitializable singleton) metaclass."""

    def test_ri_singleton_returns_same_instance(self):
        """RiSingletonMeta should return the same instance."""

        class MyRiSingleton(metaclass=RiSingletonMeta):
            def __init__(self, value):
                self.value = value

        instance1 = MyRiSingleton(1)
        instance2 = MyRiSingleton(2)

        assert instance1 is instance2

    def test_ri_singleton_reinitializes(self):
        """RiSingletonMeta should reinitialize with new values."""

        class MyRiSingleton2(metaclass=RiSingletonMeta):
            def __init__(self, value):
                self.value = value

        instance1 = MyRiSingleton2(1)
        assert instance1.value == 1

        instance2 = MyRiSingleton2(2)
        assert instance2.value == 2
        assert instance1.value == 2  # Same instance, reinitialized


class TestBaseData:
    """Tests for BaseData Pydantic model."""

    def test_to_python_dict(self):
        """to_python_dict should include type module name."""

        class TestData(CoreData):
            name: str
            value: int

        data = TestData(name="test", value=42)
        result = data.to_python_dict()

        assert result["name"] == "test"
        assert result["value"] == 42
        assert TYPE_MOD_NAME in result

    def test_to_json_dict(self):
        """to_json_dict should return JSON-compatible dict."""

        class TestData(CoreData):
            name: str
            value: int

        data = TestData(name="test", value=42)
        result = data.to_json_dict()

        assert result["name"] == "test"
        assert result["value"] == 42
        assert TYPE_MOD_NAME in result

    def test_to_json_str(self):
        """to_json_str should return valid JSON string."""
        import json

        class TestData(CoreData):
            name: str

        data = TestData(name="test")
        result = data.to_json_str()

        parsed = json.loads(result)
        assert parsed["name"] == "test"
        assert TYPE_MOD_NAME in parsed


class TestCoreData:
    """Tests for CoreData model."""

    def test_ignores_extra_fields(self):
        """CoreData should ignore extra fields."""

        class TestCore(CoreData):
            name: str

        data = TestCore(name="test", extra_field="ignored")
        assert data.name == "test"
        assert not hasattr(data, "extra_field")


class TestFlexData:
    """Tests for FlexData model."""

    def test_preserves_extra_fields(self):
        """FlexData should preserve extra fields."""

        class TestFlex(FlexData):
            name: str

        data = TestFlex(name="test", extra_field="preserved")
        assert data.name == "test"
        assert "extra_field" in data.extra_fields

    def test_extra_properties(self):
        """FlexData.extra_properties should return extra field values."""

        class TestFlex(FlexData):
            name: str

        data = TestFlex(name="test", extra1="value1", extra2="value2")
        extras = data.extra_properties

        assert extras["extra1"] == "value1"
        assert extras["extra2"] == "value2"


class TestDateTimeRange:
    """Tests for DateTimeRange model."""

    def test_valid_range(self):
        """DateTimeRange should accept valid ranges."""
        start = dt.datetime(2024, 1, 1)
        end = dt.datetime(2024, 12, 31)

        range_obj = DateTimeRange(start=start, end=end)
        assert range_obj.start == start
        assert range_obj.end == end

    def test_same_start_end(self):
        """DateTimeRange should accept same start and end."""
        same_time = dt.datetime(2024, 6, 15)

        range_obj = DateTimeRange(start=same_time, end=same_time)
        assert range_obj.start == range_obj.end

    def test_invalid_range_raises(self):
        """DateTimeRange should reject start > end."""
        start = dt.datetime(2024, 12, 31)
        end = dt.datetime(2024, 1, 1)

        with pytest.raises(ValidationError):
            DateTimeRange(start=start, end=end)
