"""
models.py - JSON-RPC 2.0 data models for the Ayuna framework.

This module provides Pydantic models implementing the JSON-RPC 2.0 specification:

- JsonRpcError: Standard JSON-RPC error object
- JsonRpcSuccess: Successful result wrapper
- JsonRpcRequest: Incoming JSON-RPC request
- JsonRpcResponse: Outgoing JSON-RPC response

All models follow the JSON-RPC 2.0 specification:
https://www.jsonrpc.org/specification
"""

from typing import Annotated, Any, Dict, Literal

import orjson as _json
from pydantic import AfterValidator, Field, model_serializer, model_validator

from ..basetypes import CoreData, FnParamsType, KeyIdxType
from ..constants import NODATA, NOID, _NoIdSentinel

# =============================================================================
# JSON-RPC 2.0 Error Codes
# =============================================================================

# Standard JSON-RPC 2.0 error codes
ERROR_PARSE_ERROR = -32700  # Invalid JSON was received
ERROR_INVALID_REQUEST = -32600  # JSON is not a valid Request object
ERROR_METHOD_NOT_FOUND = -32601  # Method does not exist / is not available
ERROR_INVALID_PARAMS = -32602  # Invalid method parameters
ERROR_INTERNAL_ERROR = -32603  # Internal JSON-RPC error
ERROR_SERVER_ERROR = -32000  # Server error (implementation-defined)


def _validate_error_code(v: int) -> int:
    """Validate that the error code is a standard or server-range JSON-RPC code."""
    standard_codes = {-32700, -32600, -32601, -32602, -32603}
    if v not in standard_codes and not (-32099 <= v <= -32000):
        raise ValueError(
            f"Invalid JSON-RPC error code: {v}. Must be a standard code "
            "(-32700/-32600/-32601/-32602/-32603) or in the server error range [-32099, -32000]."
        )
    return v


# Type for valid error codes: standard codes or the server error range -32000 to -32099
ErrorCode = Annotated[int, AfterValidator(_validate_error_code)]

# Human-readable names for error codes
ErrorCodeToName: Dict[int, str] = {
    ERROR_PARSE_ERROR: "Parse error",
    ERROR_INVALID_REQUEST: "Invalid request",
    ERROR_METHOD_NOT_FOUND: "Method not found",
    ERROR_INVALID_PARAMS: "Invalid params",
    ERROR_INTERNAL_ERROR: "Internal error",
    ERROR_SERVER_ERROR: "Server error",
}

# =============================================================================
# JSON-RPC Models
# =============================================================================


class JsonRpcError(CoreData):
    """
    JSON-RPC 2.0 error object.

    Represents an error that occurred during RPC method execution.

    Attributes
    ----------
    code : ErrorCode
        Numeric error code (see ERROR_* constants).
    message : str
        Short description of the error.
    data : Any
        Optional additional error data (omitted if NODATA).
    """

    code: ErrorCode = Field(description="Error code")
    message: str = Field(description="Error message")
    data: Any = Field(description="Optional, additional error data", default=NODATA)

    @model_serializer(when_used="always")
    def marshal_error(self):
        """Serialize error, omitting data field if not provided."""
        err: Dict = {"code": self.code, "message": self.message}

        if self.data != NODATA:
            err["data"] = self.data

        return err


class JsonRpcSuccess(CoreData):
    """
    Wrapper for successful RPC method results.

    Used internally to distinguish success from error responses.

    Attributes
    ----------
    data : Any | None
        The result data from the method call.
    """

    data: Any | None = Field(description="Method result", default=None)

    @model_serializer(when_used="always")
    def marshal_success(self):
        """Serialize success result."""
        return {"data": self.data}


class JsonRpcRequest(CoreData):
    """
    JSON-RPC 2.0 request object.

    Represents an incoming RPC request with method name and parameters.

    Attributes
    ----------
    jsonrpc : Literal["2.0"]
        Protocol version, always "2.0".
    method : str
        Name of the method to invoke.
    params : FnParamsType | None
        Method parameters (list or dict), optional.
    id : KeyIdxType
        Request identifier for correlating responses.
        If NOID, this is a notification (no response expected).
    """

    jsonrpc: Literal["2.0"] = "2.0"
    method: str = Field(description="RPC method name - should not begin with 'rpc.'")
    params: FnParamsType | None = Field(description="Method parameters", default=None)
    id: KeyIdxType | _NoIdSentinel = Field(description="Request id", default=NOID)

    @model_serializer(when_used="always")
    def marshal_request(self):
        """
        Serialize request per JSON-RPC spec.

        Omits params if None and id if NOID (notification).
        """
        req: Dict = {"jsonrpc": self.jsonrpc, "method": self.method}

        if self.params is not None:
            req["params"] = self.params

        if not isinstance(self.id, _NoIdSentinel):
            req["id"] = self.id

        return req


class JsonRpcResponse(CoreData):
    """
    JSON-RPC 2.0 response object.

    Represents an outgoing RPC response with either a result or error.
    Per the spec, exactly one of result or error must be present.

    Attributes
    ----------
    jsonrpc : Literal["2.0"]
        Protocol version, always "2.0".
    result : Any | None
        Method result (present on success).
    error : JsonRpcError | None
        Error object (present on failure).
    id : KeyIdxType | None
        Request identifier this response correlates to.
    """

    jsonrpc: Literal["2.0"] = "2.0"
    result: Any | None = Field(description="Method result", default=None)
    error: JsonRpcError | None = Field(description="Method error", default=None)
    id: KeyIdxType | None = Field(description="Request id", default=None)

    @model_validator(mode="after")
    def check_result_error(self):
        """Validate that result and error are not both explicitly set."""
        if "result" in self.model_fields_set and self.error is not None:
            raise ValueError("result and error cannot both be set")

        return self

    @model_serializer(when_used="always")
    def marshal_response(self):
        """
        Serialize response per JSON-RPC spec.

        Includes either result or error, never both.
        """
        res: Dict = {"jsonrpc": self.jsonrpc, "id": self.id}

        if self.error is not None:
            res["error"] = self.error
        else:
            res["result"] = self.result

        return res

    def to_json_dict(self) -> Dict:
        """Serialize to a JSON-compatible dict per JSON-RPC spec, without _typmod."""
        return _json.loads(self.model_dump_json(by_alias=True))
