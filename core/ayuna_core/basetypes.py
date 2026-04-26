"""
basetypes.py - Core type definitions and base classes for the Ayuna framework.

This module provides foundational types, type aliases, enumerations, metaclasses,
and Pydantic base models used throughout the ayuna_core library. It defines:

- Type aliases for common patterns (strings, JSON types, async types)
- Custom exception classes
- Logging level enumerations
- Singleton metaclasses for controlled instantiation
- Base Pydantic models with serialization support
"""

import asyncio
import datetime as dt
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from enum import IntEnum, StrEnum
from io import BytesIO
from multiprocessing.context import ForkContext, SpawnContext
from threading import Lock
from typing import Annotated, Any, Callable, Dict, List, TypeVar

import orjson as json
from pydantic import (
    BaseModel,
    ConfigDict,
    PrivateAttr,
    StringConstraints,
    model_validator,
)

from .constants import TYPE_MOD_NAME

# =============================================================================
# Constrained String Type Aliases
# =============================================================================

# A string that must be empty after whitespace stripping
EmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=0)]

# A string that must have at least one character after whitespace stripping
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# A string that must follow snake_case convention (lowercase letters, numbers, underscores)
SnakeCaseStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[a-z0-9_]+$")
]

# =============================================================================
# Common Type Aliases
# =============================================================================

# JSON-compatible types: either a dictionary or a list
JsonType = Dict | List

# Type for keys/indices: can be string (named) or integer (positional)
KeyIdxType = str | int

# Function parameters type: supports both positional (list) and keyword (dict) arguments
FnParamsType = List[Any] | Dict[str, Any]

# Async awaitable types: either a Future or a Task
Awaitable = asyncio.Future | asyncio.Task

# Multiprocessing context types: either fork or spawn based process creation
MprocContext = ForkContext | SpawnContext

# Executor pool types: either process-based or thread-based
PoolExecutor = ProcessPoolExecutor | ThreadPoolExecutor

# Type variable for Pydantic BaseModel subclasses
BaseModelT = TypeVar("BaseModelT", bound=BaseModel)

# =============================================================================
# Callback Type Aliases
# =============================================================================

# Callback function type for handling completed awaitables
AwaitableDoneHandler = Callable[[asyncio.Future], None]

# Initializer function type for pool executors
PoolExecutorInitFunc = Callable[[Any], object]

# =============================================================================
# Exception Classes
# =============================================================================


class AyunaError(Exception):
    """
    Base exception class for the Ayuna framework.

    Provides enhanced error reporting by optionally storing the underlying
    cause of the exception for chain-of-cause error tracking.

    Attributes
    ----------
    exc_cause : BaseException | None
        The original exception that caused this error, if any.

    Examples
    --------
    >>> raise AyunaError("Failed to process data")
    >>> raise AyunaError("File read failed", exc_cause=IOError("File not found"))
    """

    def __init__(self, error: NonEmptyStr, exc_cause: BaseException | None = None):
        """
        Initialize an AyunaError with an error message and optional cause.

        Parameters
        ----------
        error : NonEmptyStr
            The error message describing what went wrong.
        exc_cause : BaseException | None, optional
            The underlying exception that caused this error.
        """
        super().__init__(error)
        self.exc_cause = exc_cause

    def __str__(self):
        """Return string representation including the cause if present."""
        if self.exc_cause:
            exc_str = super().__str__()
            return f"{exc_str} (caused by {repr(self.exc_cause)})"

        return super().__str__()


# Result type aliases for operations that may fail
ErrorOrBytesIO = AyunaError | BytesIO
ErrorOrStr = AyunaError | str

# =============================================================================
# Logging Enumerations
# =============================================================================


class LogLevelName(StrEnum):
    """
    String enumeration of log level names.

    Provides human-readable log level names that align with Python's
    logging module, plus an additional TRACE level for extra verbosity.
    """

    CRITICAL = "CRITICAL"  # Severe errors that may cause program termination
    ERROR = "ERROR"  # Error conditions that should be investigated
    WARNING = "WARNING"  # Warning conditions that may require attention
    INFO = "INFO"  # Informational messages for normal operation
    DEBUG = "DEBUG"  # Detailed debugging information
    TRACE = "TRACE"  # Most verbose level for tracing execution


class LogLevelNumber(IntEnum):
    """
    Integer enumeration of log level numeric values.

    These values correspond to Python's logging module levels,
    with TRACE being a custom level below DEBUG.
    """

    CRITICAL = 50  # Corresponds to logging.CRITICAL
    ERROR = 40  # Corresponds to logging.ERROR
    WARNING = 30  # Corresponds to logging.WARNING
    INFO = 20  # Corresponds to logging.INFO
    DEBUG = 10  # Corresponds to logging.DEBUG
    TRACE = 5  # Custom level below DEBUG for ultra-verbose output


# =============================================================================
# Async Operation Enumerations
# =============================================================================


class AwaitCondition(StrEnum):
    """
    Enumeration of conditions for awaiting multiple async operations.

    Maps to asyncio.wait() return conditions for controlling when
    a batch of awaitables should return control to the caller.
    """

    ALL_DONE = asyncio.ALL_COMPLETED  # Wait until all tasks complete
    ANY_DONE = asyncio.FIRST_COMPLETED  # Return when any task completes
    ANY_FAIL = asyncio.FIRST_EXCEPTION  # Return when any task raises an exception


# =============================================================================
# Async Error Models
# =============================================================================


class AioErrorItem(BaseModel):
    """
    Pydantic model representing an error from an async operation.

    Used to capture and serialize error information from failed
    asyncio tasks or futures in a structured format.

    Attributes
    ----------
    name : str
        The exception class name (e.g., "ValueError", "CancelledError").
    message : str
        The error message or description.
    """

    name: str
    message: str


# =============================================================================
# Singleton Metaclasses
# =============================================================================


class SingletonMeta(type):
    """
    Thread-safe singleton metaclass for creating single-instance classes.

    When a class uses this metaclass, only one instance of that class
    will ever be created. Subsequent instantiation attempts return
    the existing instance. Uses double-checked locking for thread safety.

    The singleton instance can be accessed via the dynamically added
    `get_instance()` class method after first instantiation.

    Example
    -------
    >>> class MyService(metaclass=SingletonMeta):
    ...     def __init__(self, config):
    ...         self.config = config
    ...
    >>> s1 = MyService({"key": "value"})
    >>> s2 = MyService({"different": "config"})  # Returns same instance as s1
    >>> s1 is s2  # True
    """

    __instances = {}
    __lock: Lock = Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """
        Create or return the singleton instance of the class.

        Uses double-checked locking pattern to ensure thread-safe
        instantiation while minimizing lock contention.

        Parameters
        ----------
        *args : Any
            Positional arguments for the class constructor (only used on first call).
        **kwargs : Any
            Keyword arguments for the class constructor (only used on first call).

        Returns
        -------
        Any
            The singleton instance of the class.
        """
        if cls not in cls.__instances:
            with cls.__lock:
                if cls not in cls.__instances:
                    instance = super().__call__(*args, **kwargs)

                    @classmethod
                    def get_instance(cls):
                        return instance

                    setattr(cls, "get_instance", get_instance)
                    cls.__instances[cls] = instance

        return cls.__instances[cls]


class RiSingletonMeta(type):
    """
    Reinitializable singleton metaclass for creating single-instance classes
    that can be reconfigured.

    Similar to SingletonMeta, but allows the singleton instance to be
    reinitialized with new parameters on subsequent calls. The same
    object instance is returned, but its __init__ is called again
    with the new arguments.

    Useful for services that need to maintain singleton identity but
    allow configuration updates during runtime.

    Example
    -------
    >>> class ConfigurableService(metaclass=RiSingletonMeta):
    ...     def __init__(self, setting):
    ...         self.setting = setting
    ...
    >>> s1 = ConfigurableService("initial")
    >>> s2 = ConfigurableService("updated")  # Same instance, but setting = "updated"
    >>> s1 is s2  # True
    >>> s1.setting  # "updated"
    """

    __instances = {}
    __inst_lock: Lock = Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """
        Create or reinitialize the singleton instance of the class.

        On first call, creates the instance. On subsequent calls,
        calls __init__ again with the new arguments to reconfigure
        the existing instance.

        Parameters
        ----------
        *args : Any
            Positional arguments for the class constructor.
        **kwargs : Any
            Keyword arguments for the class constructor.

        Returns
        -------
        Any
            The singleton instance of the class (possibly reinitialized).
        """
        is_fresh = False

        if cls not in cls.__instances:
            with cls.__inst_lock:
                if cls not in cls.__instances:
                    is_fresh = True
                    instance = super().__call__(*args, **kwargs)

                    @classmethod
                    def get_instance(cls):
                        return instance

                    setattr(cls, "get_instance", get_instance)
                    cls.__instances[cls] = instance

        instance = cls.__instances[cls]

        if not is_fresh:
            instance.__init__(*args, **kwargs)

        return instance


# =============================================================================
# Base Pydantic Models
# =============================================================================


class BaseData(BaseModel):
    """
    Abstract base class for Pydantic models with type-aware serialization.

    Provides methods for serializing model instances to dictionaries and
    JSON strings while preserving the fully qualified type name for
    polymorphic deserialization. The type information is stored under
    the TYPE_MOD_NAME key (default: "_typmod").

    This enables deserializing JSON back to the correct Pydantic model
    subclass without knowing the type in advance.

    Attributes
    ----------
    _tmod_name : str (private)
        The fully qualified module.class name for this model instance.
    """

    _tmod_name: str = PrivateAttr()

    def __init__(self, **data):
        """
        Initialize the model and capture the fully qualified type name.

        Parameters
        ----------
        **data : Any
            Field values for the Pydantic model.
        """
        super().__init__(**data)
        self._tmod_name = f"{self.__class__.__module__}.{self.__class__.__name__}"

    def to_python_dict(self) -> Dict:
        """
        Convert the model to a Python dictionary with type information.

        Uses Pydantic's model_dump() with alias resolution, then adds
        the type module name for polymorphic deserialization.

        Returns
        -------
        Dict
            Dictionary representation including the _typmod key.
        """
        data = self.model_dump(by_alias=True)
        data[TYPE_MOD_NAME] = self._tmod_name

        return data

    def to_json_dict(self) -> Dict:
        """
        Convert the model to a JSON-compatible dictionary with type information.

        Similar to to_python_dict() but ensures all values are JSON-serializable
        by round-tripping through JSON serialization.

        Returns
        -------
        Dict
            JSON-compatible dictionary including the _typmod key.
        """
        data = json.loads(self.model_dump_json(by_alias=True))
        data[TYPE_MOD_NAME] = self._tmod_name

        return data

    def to_json_str(self) -> str:
        """
        Convert the model to a JSON string with type information.

        Returns
        -------
        str
            JSON string representation including the _typmod key.
        """
        data = json.loads(self.model_dump_json(by_alias=True))
        data[TYPE_MOD_NAME] = self._tmod_name

        return json.dumps(data).decode("utf-8")


class CoreData(BaseData):
    """
    Base class for strict Pydantic models that ignore extra fields.

    Use this as the base class for models where the schema is well-defined
    and extra fields should be silently ignored during parsing.

    Configuration
    -------------
    - extra="ignore": Extra fields in input data are ignored
    - arbitrary_types_allowed=True: Allows non-Pydantic types as field types
    - allow_inf_nan=False: Rejects infinity and NaN float values
    - populate_by_name=True: Allows population by field name or alias
    - loc_by_alias=True: Error locations use alias names
    """

    model_config = ConfigDict(
        extra="ignore",
        arbitrary_types_allowed=True,
        allow_inf_nan=False,
        populate_by_name=True,
        loc_by_alias=True,
    )


class FlexData(BaseData):
    """
    Base class for flexible Pydantic models that preserve extra fields.

    Use this as the base class for models that need to accept and preserve
    additional fields beyond the defined schema. Extra fields are accessible
    via the extra_fields and extra_properties properties.

    Configuration
    -------------
    - extra="allow": Extra fields are preserved in model_extra
    - arbitrary_types_allowed=True: Allows non-Pydantic types as field types
    - allow_inf_nan=False: Rejects infinity and NaN float values
    - populate_by_name=True: Allows population by field name or alias
    - loc_by_alias=True: Error locations use alias names
    """

    model_config = ConfigDict(
        extra="allow",
        arbitrary_types_allowed=True,
        allow_inf_nan=False,
        populate_by_name=True,
        loc_by_alias=True,
    )

    @property
    def extra_fields(self) -> set[str]:
        """
        Get the names of extra fields that were provided but not in the schema.

        Returns
        -------
        set[str]
            Set of extra field names, empty set if none.
        """
        return set(self.model_extra.keys()) if self.model_extra else set()

    @property
    def extra_properties(self) -> dict[str, Any] | None:
        """
        Get the extra field values as a dictionary.

        Returns
        -------
        dict[str, Any] | None
            Dictionary of extra field names to values, or None if no extras.
        """
        return self.model_extra


# =============================================================================
# Common Data Models
# =============================================================================


class DateTimeRange(CoreData):
    """
    Model representing a datetime range with start and end timestamps.

    Validates that the start datetime is not after the end datetime.

    Attributes
    ----------
    start : datetime
        The beginning of the time range.
    end : datetime
        The end of the time range.

    Raises
    ------
    ValueError
        If start is greater than end.
    """

    start: dt.datetime
    end: dt.datetime

    @model_validator(mode="after")
    def check_start_end(self):
        """Validate that start datetime is not after end datetime."""
        if self.start > self.end:
            raise ValueError("start must be less than or equal to end")

        return self
