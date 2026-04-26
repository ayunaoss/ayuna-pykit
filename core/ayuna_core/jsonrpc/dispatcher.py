"""
dispatcher.py - JSON-RPC 2.0 method dispatcher for the Ayuna framework.

This module provides the infrastructure for implementing JSON-RPC 2.0 servers:

- @json_rpc_method decorator for registering RPC methods
- process_rpc() function for dispatching requests to handlers
- build_openrpc_document() for generating OpenRPC schema documentation
- Automatic parameter validation using Pydantic models

Usage
-----
>>> @json_rpc_method(name="add")
... def add(a: int, b: int) -> int:
...     return a + b
...
>>> response = await process_rpc({"jsonrpc": "2.0", "method": "add", "params": [1, 2], "id": 1})
>>> # {"jsonrpc": "2.0", "result": 3, "id": 1}
"""

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, Dict, List, Type, get_type_hints

from pydantic import BaseModel, Field, ValidationError, create_model

from ..basefuncs import gather_awaitables
from ..basetypes import AioErrorItem, Awaitable, JsonType
from ..constants import _NoIdSentinel
from .models import (
    ERROR_INTERNAL_ERROR,
    ERROR_INVALID_PARAMS,
    ERROR_INVALID_REQUEST,
    ERROR_METHOD_NOT_FOUND,
    ErrorCodeToName,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcSuccess,
    KeyIdxType,
)

# =============================================================================
# Type Definitions and Registry
# =============================================================================

# Return type for RPC handlers
RpcReturnType = JsonRpcSuccess | JsonRpcError

# Global registry mapping method names to handler functions
json_rpc_registry: Dict[str, Callable] = {}


def _get_handler(method_name: str) -> Callable | None:
    """
    Resolve a handler for the given method name.

    Handles the built-in ``rpc.discover`` method natively so it is always
    available regardless of registry state (e.g. cleared in tests).

    Parameters
    ----------
    method_name : str
        JSON-RPC method name.

    Returns
    -------
    Callable | None
        Handler coroutine, or None if the method is not registered.
    """
    if method_name == "rpc.discover":

        async def _discover(_raw_params):  # NOSONAR
            return JsonRpcSuccess(data=build_openrpc_document())

        return _discover

    return json_rpc_registry.get(method_name)


# =============================================================================
# Internal Helper Functions
# =============================================================================


def _prepared_response(
    result: RpcReturnType, request_id: KeyIdxType | _NoIdSentinel | None
):
    """
    Create a JsonRpcResponse from a handler result.

    Returns None for notifications (NOID), as per JSON-RPC spec.

    Parameters
    ----------
    result : RpcReturnType
        Handler result (success or error).
    request_id : KeyIdxType | _NoIdSentinel | None
        Request ID to include in response. Pass NOID to suppress the response
        (notification). Pass None to produce a response with a null id (error
        cases where the id could not be determined).

    Returns
    -------
    JsonRpcResponse | None
        Response object, or None for notifications.
    """
    if isinstance(request_id, _NoIdSentinel):
        return

    if isinstance(result, JsonRpcError):
        return JsonRpcResponse(error=result, id=request_id)

    return JsonRpcResponse(result=result.data, id=request_id)


async def _dispatch_single(payload: Dict):
    """
    Dispatch a single JSON-RPC request to its handler.

    Parameters
    ----------
    payload : Dict
        Parsed JSON-RPC request object.

    Returns
    -------
    JsonRpcResponse | None
        Response object, or None for notifications.
    """
    try:
        request = JsonRpcRequest(**payload)
        handler = _get_handler(request.method)

        if not handler:
            error = JsonRpcError(
                code=ERROR_METHOD_NOT_FOUND,
                message=ErrorCodeToName[ERROR_METHOD_NOT_FOUND],
            )

            return _prepared_response(result=error, request_id=request.id)

        result = await handler(request.params)
        return _prepared_response(result=result, request_id=request.id)
    except ValidationError as ex:
        error = JsonRpcError(
            code=ERROR_INVALID_REQUEST,
            message=ErrorCodeToName[ERROR_INVALID_REQUEST],
            data=ex.errors(),
        )

        return _prepared_response(result=error, request_id=None)


# =============================================================================
# Type Conversion Utilities
# =============================================================================


def python_type_to_json_type(tp: Any) -> str:
    """
    Convert a Python type annotation to a JSON Schema type name.

    Parameters
    ----------
    tp : Any
        Python type or type annotation.

    Returns
    -------
    str
        JSON Schema type name ("string", "integer", "number", "boolean", "array", "object").
    """
    origin = getattr(tp, "__origin__", None)

    if origin is list or tp is list:
        return "array"

    elif origin is dict or tp is dict:
        return "object"

    elif tp in (int, float, bool, str):
        return {int: "integer", float: "number", bool: "boolean", str: "string"}[tp]

    return "string"


# =============================================================================
# Model Builder
# =============================================================================


def build_param_model_from_fn(fn: Callable) -> Type[BaseModel] | None:
    """
    Dynamically create a Pydantic model for a function's parameters.

    Inspects the function signature and creates a model that can be
    used for parameter validation in RPC handlers.

    Parameters
    ----------
    fn : Callable
        Function to create parameter model for.

    Returns
    -------
    Type[BaseModel] | None
        Generated Pydantic model class, or None if function has no parameters.
    """
    sig = inspect.signature(fn)
    fields = {}

    for name, param in sig.parameters.items():
        if name == "self":
            continue

        annotation = param.annotation if param.annotation is not inspect._empty else Any
        default = param.default if param.default is not inspect._empty else ...
        fields[name] = (annotation, Field(default=default))

    if not fields:
        return None

    model_name = f"{fn.__name__.title().replace('_', '')}Params"
    return create_model(model_name, **fields)  # type: ignore


# =============================================================================
# JSON-RPC Method Decorator
# =============================================================================


def json_rpc_method(
    name: str | None = None, param_model: Type[BaseModel] | None = None
):
    """
    Decorator for registering a function as a JSON-RPC method.

    The decorated function is registered in the global json_rpc_registry
    and can be invoked via process_rpc(). Parameters are automatically
    validated using a Pydantic model derived from the function signature
    or a custom model if provided.

    Parameters
    ----------
    name : str | None, optional
        Method name to register. Defaults to the function's __name__.
    param_model : Type[BaseModel] | None, optional
        Custom Pydantic model for parameter validation.
        If None, a model is generated from the function signature.

    Returns
    -------
    Callable
        Decorator function.

    Example
    -------
    >>> @json_rpc_method(name="math.add")
    ... def add(a: int, b: int) -> int:
    ...     return a + b
    ...
    >>> @json_rpc_method()
    ... async def fetch_data(url: str) -> dict:
    ...     # async implementation
    ...     return {"data": "..."}
    """

    def decorator(fn: Callable):
        method_name = name or fn.__name__
        if method_name.startswith("rpc."):
            raise ValueError(
                f"Method name '{method_name}' uses the reserved 'rpc.' prefix. "
                "Names starting with 'rpc.' are reserved for JSON-RPC internals."
            )
        is_async = inspect.iscoroutinefunction(fn)

        auto_model = param_model or build_param_model_from_fn(fn)
        param_names = list(inspect.signature(fn).parameters)

        @wraps(fn)
        async def handler(raw_params):
            """Internal handler that validates params and invokes the method."""
            try:
                args, kwargs = [], {}

                if isinstance(raw_params, list):
                    if auto_model:
                        kwargs = dict(zip(param_names, raw_params))
                        validated = auto_model(**kwargs)
                        kwargs = validated.model_dump()
                    else:
                        args = raw_params
                elif isinstance(raw_params, dict):
                    if auto_model:
                        validated = auto_model(**raw_params)
                        kwargs = validated.model_dump()
                    else:
                        kwargs = raw_params
                elif raw_params is not None:
                    return JsonRpcError(
                        code=ERROR_INVALID_PARAMS,
                        message=ErrorCodeToName[ERROR_INVALID_PARAMS],
                        data="Parameters must be a list or a dict",
                    )

                result = await fn(*args, **kwargs) if is_async else fn(*args, **kwargs)

                return JsonRpcSuccess(data=result)
            except ValidationError as ve:
                return JsonRpcError(
                    code=ERROR_INVALID_PARAMS,
                    message=ErrorCodeToName[ERROR_INVALID_PARAMS],
                    data=ve.errors(),
                )
            except Exception as e:
                return JsonRpcError(
                    code=ERROR_INTERNAL_ERROR,
                    message=ErrorCodeToName[ERROR_INTERNAL_ERROR],
                    data=str(e),
                )

        json_rpc_registry[method_name] = handler
        return fn

    return decorator


# =============================================================================
# OpenRPC Schema Builder
# =============================================================================


def build_openrpc_document(title: str = "JSON-RPC API", version: str = "1.0.0"):
    """
    Generate an OpenRPC specification document for registered methods.

    Creates a JSON-serializable document describing all registered
    JSON-RPC methods, their parameters, and return types following
    the OpenRPC specification.

    Parameters
    ----------
    title : str, optional
        API title for the document (default: "JSON-RPC API").
    version : str, optional
        API version string (default: "1.0.0").

    Returns
    -------
    Dict
        OpenRPC specification document.

    See Also
    --------
    https://spec.open-rpc.org/
    """
    methods = []

    for method_name, handler in json_rpc_registry.items():
        if method_name == "rpc.discover":
            continue

        original_fn = getattr(handler, "__wrapped__", handler)
        sig = inspect.signature(original_fn)
        type_hints = get_type_hints(original_fn)

        param_schemas = []

        for name, param in sig.parameters.items():
            if name == "self":
                continue

            hint = type_hints.get(name, Any)
            param_schema = {
                "name": name,
                "required": param.default == inspect.Parameter.empty,
                "schema": {"type": python_type_to_json_type(hint)},
            }

            param_schemas.append(param_schema)

        return_type = type_hints.get("return", Any)
        result_schema = {
            "name": "result",
            "schema": {"type": python_type_to_json_type(return_type)},
        }

        methods.append(
            {"name": method_name, "params": param_schemas, "result": result_schema}
        )

    return {
        "openrpc": "1.2.6",
        "info": {"title": title, "version": version},
        "methods": methods,
    }


# =============================================================================
# JSON-RPC Request Dispatcher
# =============================================================================


async def process_rpc(payload: JsonType):
    """
    Process one or more JSON-RPC requests.

    Handles both single requests (dict) and batch requests (list).
    Dispatches each request to the appropriate registered handler
    and returns the response(s).

    Parameters
    ----------
    payload : JsonType
        Parsed JSON payload - either a single request dict or a list
        of request dicts for batch processing.

    Returns
    -------
    Dict | List[Dict] | None
        For single requests: response dict or None for notifications.
        For batch requests: list of response dicts.
        Empty payload returns an error response.
    """
    if not payload:
        error = JsonRpcError(
            code=ERROR_INVALID_REQUEST,
            message=ErrorCodeToName[ERROR_INVALID_REQUEST],
            data="Payload is empty",
        )

        response = _prepared_response(result=error, request_id=None)
        assert response, "Response cannot be None"

        return response.to_json_dict()

    if isinstance(payload, dict):
        response = await _dispatch_single(payload)
        return response.to_json_dict() if response else None

    results: List[Dict] = []
    awaitables: Dict[KeyIdxType, Awaitable] = {}

    for item in payload:
        try:
            request = JsonRpcRequest(**item)
            handler = _get_handler(request.method)

            if not handler:
                error = JsonRpcError(
                    code=ERROR_METHOD_NOT_FOUND,
                    message=ErrorCodeToName[ERROR_METHOD_NOT_FOUND],
                )

                response = _prepared_response(result=error, request_id=request.id)
                assert response

                results.append(response.to_json_dict())
                continue

            if isinstance(request.id, _NoIdSentinel):
                # Notifications: execute but never respond
                _ = asyncio.create_task(handler(request.params))
                continue

            awaitables[request.id] = asyncio.create_task(handler(request.params))
        except ValidationError as ex:
            error = JsonRpcError(
                code=ERROR_INVALID_REQUEST,
                message=ErrorCodeToName[ERROR_INVALID_REQUEST],
                data=ex.errors(),
            )

            response = _prepared_response(result=error, request_id=None)
            assert response

            results.append(response.to_json_dict())

    if awaitables:
        responses = await gather_awaitables(awaitables)
    else:
        responses = {}

    for request_id, response in responses.items():
        if isinstance(request_id, _NoIdSentinel):
            continue

        if isinstance(response, AioErrorItem):
            error = JsonRpcError(
                code=ERROR_INTERNAL_ERROR,
                message=ErrorCodeToName[ERROR_INTERNAL_ERROR],
                data=response.model_dump(by_alias=True),
            )

            response = _prepared_response(result=error, request_id=request_id)
        else:
            assert isinstance(response, (JsonRpcSuccess, JsonRpcError))
            response = _prepared_response(result=response, request_id=request_id)

        assert isinstance(response, JsonRpcResponse)
        results.append(response.to_json_dict())

    return results or None
