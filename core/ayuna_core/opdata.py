"""
opdata.py - Operation result models for the Ayuna framework.

This module provides standardized result types for operations that can
either succeed or fail. The discriminated union pattern allows for
type-safe handling of results.

Classes
-------
OpSuccess : Success result with optional result data
OpFailure : Failure result with error information
OpResult : Discriminated union type for either outcome

Functions
---------
ensure_result_from_json : Parse JSON to OpSuccess or OpFailure
ensure_result_from_dict : Parse dictionary to OpSuccess or OpFailure
"""

from typing import Annotated, Any, Dict, Literal, Union

import orjson as json
from pydantic import Field, ValidationError

from .basefuncs import unmarshal_json_with_type
from .basetypes import CoreData

# =============================================================================
# Result Models
# =============================================================================


class OpSuccess(CoreData):
    """
    Model representing a successful operation result.

    Attributes
    ----------
    typid : Literal["success"]
        Discriminator field, always "success".
    code : int
        Success code (default: 0).
    result : Any | None
        Optional result data from the operation.
    """

    typid: Literal["success"] = "success"
    code: int = Field(description="Success code", default=0)
    result: Any | None = Field(description="Ops result", default=None)


class OpFailure(CoreData):
    """
    Model representing a failed operation result.

    Attributes
    ----------
    typid : Literal["failure"]
        Discriminator field, always "failure".
    code : int
        Error code (default: -1).
    error : Any | None
        Optional error details or message.
    """

    typid: Literal["failure"] = "failure"
    code: int = Field(description="Failure code", default=-1)
    error: Any | None = Field(description="Ops error", default=None)


# Discriminated union type for operation results
# The "typid" field determines whether it's OpSuccess or OpFailure
OpResult = Annotated[Union[OpSuccess, OpFailure], Field(discriminator="typid")]

# =============================================================================
# Result Parsing Functions
# =============================================================================


def ensure_result_from_json(json_str: str | bytes | bytearray):
    """
    Parse JSON string to an OpSuccess or OpFailure model.

    Attempts to deserialize using embedded type information first,
    then falls back to trying OpSuccess, then OpFailure. If all
    parsing fails, returns an OpFailure with the error message.

    Parameters
    ----------
    json_str : str | bytes | bytearray
        JSON string to parse.

    Returns
    -------
    OpSuccess | OpFailure
        Parsed result model, guaranteed to be one of these types.
    """
    try:
        json_data = json.loads(json_str)
    except Exception as e:
        return OpFailure(code=400, error=str(e))

    try:
        model_obj = unmarshal_json_with_type(json_str)
        assert isinstance(model_obj, (OpSuccess, OpFailure))
    except (ValueError, TypeError):
        # Try directly setting to one of the result types
        try:
            model_obj = OpSuccess(**json_data)
        except ValidationError:
            model_obj = OpFailure(**json_data)
    except Exception as e:
        model_obj = OpFailure(code=400, error=str(e))

    return model_obj


def ensure_result_from_dict(json_data: Dict):
    """
    Parse dictionary to an OpSuccess or OpFailure model.

    Attempts to deserialize using embedded type information first,
    then falls back to trying OpSuccess, then OpFailure. If all
    parsing fails, returns an OpFailure with the error message.

    Parameters
    ----------
    json_data : Dict
        Dictionary to parse.

    Returns
    -------
    OpSuccess | OpFailure
        Parsed result model, guaranteed to be one of these types.
    """
    try:
        json_str = json.dumps(json_data).decode("utf-8")
        model_obj = unmarshal_json_with_type(json_str)
        assert isinstance(model_obj, (OpSuccess, OpFailure))
    except (ValueError, TypeError):
        # Try directly setting to one of the result types
        try:
            model_obj = OpSuccess(**json_data)
        except ValidationError:
            model_obj = OpFailure(**json_data)
    except Exception as e:
        model_obj = OpFailure(code=400, error=str(e))

    return model_obj
