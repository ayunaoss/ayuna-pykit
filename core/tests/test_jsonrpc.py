"""
Tests for ayuna_core.jsonrpc module.

Tests the JSON-RPC 2.0 implementation:
- JsonRpcError model
- JsonRpcSuccess model
- JsonRpcRequest model
- JsonRpcResponse model
- @json_rpc_method decorator
- process_rpc dispatcher
- OpenRPC document generation
"""

import pytest
from pydantic import ValidationError

from ayuna_core.constants import NODATA, NOID
from ayuna_core.jsonrpc.dispatcher import (
    build_openrpc_document,
    build_param_model_from_fn,
    json_rpc_method,
    json_rpc_registry,
    process_rpc,
    python_type_to_json_type,
)
from ayuna_core.jsonrpc.models import (
    ERROR_INTERNAL_ERROR,
    ERROR_INVALID_PARAMS,
    ERROR_INVALID_REQUEST,
    ERROR_METHOD_NOT_FOUND,
    ERROR_PARSE_ERROR,
    ERROR_SERVER_ERROR,
    ErrorCodeToName,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcSuccess,
)


class TestJsonRpcError:
    """Tests for JsonRpcError model."""

    def test_create_error_basic(self):
        """Test creating a basic error."""
        error = JsonRpcError(code=ERROR_INVALID_REQUEST, message="Invalid request")

        assert error.code == ERROR_INVALID_REQUEST
        assert error.message == "Invalid request"
        assert error.data == NODATA

    def test_create_error_with_data(self):
        """Test creating an error with additional data."""
        error = JsonRpcError(
            code=ERROR_INTERNAL_ERROR,
            message="Internal error",
            data={"details": "Something went wrong"},
        )

        assert error.code == ERROR_INTERNAL_ERROR
        assert error.message == "Internal error"
        assert error.data == {"details": "Something went wrong"}

    def test_error_serialization_without_data(self):
        """Test error serialization omits data when NODATA."""
        error = JsonRpcError(code=ERROR_METHOD_NOT_FOUND, message="Method not found")
        serialized = error.model_dump()

        assert "data" not in serialized
        assert serialized["code"] == ERROR_METHOD_NOT_FOUND
        assert serialized["message"] == "Method not found"

    def test_error_serialization_with_data(self):
        """Test error serialization includes data when provided."""
        error = JsonRpcError(
            code=ERROR_INVALID_PARAMS, message="Invalid params", data="test data"
        )
        serialized = error.model_dump()

        assert serialized["data"] == "test data"

    def test_error_codes(self):
        """Test all standard error codes."""
        assert ERROR_PARSE_ERROR == -32700
        assert ERROR_INVALID_REQUEST == -32600
        assert ERROR_METHOD_NOT_FOUND == -32601
        assert ERROR_INVALID_PARAMS == -32602
        assert ERROR_INTERNAL_ERROR == -32603
        assert ERROR_SERVER_ERROR == -32000

    def test_error_code_names(self):
        """Test error code to name mapping."""
        assert ErrorCodeToName[ERROR_PARSE_ERROR] == "Parse error"
        assert ErrorCodeToName[ERROR_INVALID_REQUEST] == "Invalid request"
        assert ErrorCodeToName[ERROR_METHOD_NOT_FOUND] == "Method not found"
        assert ErrorCodeToName[ERROR_INVALID_PARAMS] == "Invalid params"
        assert ErrorCodeToName[ERROR_INTERNAL_ERROR] == "Internal error"
        assert ErrorCodeToName[ERROR_SERVER_ERROR] == "Server error"

    def test_server_error_range(self):
        """Test that server error codes in range -32099 to -32000 are valid."""
        error = JsonRpcError(code=-32050, message="Custom server error")
        assert error.code == -32050

    def test_invalid_error_code_raises(self):
        """Test that an out-of-range error code raises ValidationError."""
        with pytest.raises(ValidationError):
            JsonRpcError(code=-99, message="Bad code")


class TestJsonRpcSuccess:
    """Tests for JsonRpcSuccess model."""

    def test_create_success_basic(self):
        """Test creating a basic success result."""
        success = JsonRpcSuccess(data="result")

        assert success.data == "result"

    def test_create_success_none(self):
        """Test creating a success result with None."""
        success = JsonRpcSuccess()

        assert success.data is None

    def test_create_success_complex_data(self):
        """Test creating a success result with complex data."""
        data = {"key": "value", "list": [1, 2, 3]}
        success = JsonRpcSuccess(data=data)

        assert success.data == data

    def test_success_serialization(self):
        """Test success serialization."""
        success = JsonRpcSuccess(data=42)
        serialized = success.model_dump()

        assert serialized["data"] == 42


class TestJsonRpcRequest:
    """Tests for JsonRpcRequest model."""

    def test_create_request_basic(self):
        """Test creating a basic request."""
        request = JsonRpcRequest(method="test_method", id=1)

        assert request.jsonrpc == "2.0"
        assert request.method == "test_method"
        assert request.params is None
        assert request.id == 1

    def test_create_request_with_params_list(self):
        """Test creating a request with list params."""
        request = JsonRpcRequest(method="add", params=[1, 2], id=1)

        assert request.params == [1, 2]

    def test_create_request_with_params_dict(self):
        """Test creating a request with dict params."""
        request = JsonRpcRequest(method="add", params={"a": 1, "b": 2}, id=1)

        assert request.params == {"a": 1, "b": 2}

    def test_create_notification(self):
        """Test creating a notification (no id)."""
        request = JsonRpcRequest(method="notify")

        assert request.id == NOID

    def test_request_serialization_full(self):
        """Test full request serialization."""
        request = JsonRpcRequest(method="test", params={"key": "value"}, id="abc")
        serialized = request.model_dump()

        assert serialized["jsonrpc"] == "2.0"
        assert serialized["method"] == "test"
        assert serialized["params"] == {"key": "value"}
        assert serialized["id"] == "abc"

    def test_request_serialization_omits_params(self):
        """Test request serialization omits params when None."""
        request = JsonRpcRequest(method="test", id=1)
        serialized = request.model_dump()

        assert "params" not in serialized

    def test_request_serialization_omits_id_for_notification(self):
        """Test request serialization omits id for notifications."""
        request = JsonRpcRequest(method="test")
        serialized = request.model_dump()

        assert "id" not in serialized


class TestJsonRpcResponse:
    """Tests for JsonRpcResponse model."""

    def test_create_success_response(self):
        """Test creating a success response."""
        response = JsonRpcResponse(result="success", id=1)

        assert response.jsonrpc == "2.0"
        assert response.result == "success"
        assert response.error is None
        assert response.id == 1

    def test_create_error_response(self):
        """Test creating an error response."""
        error = JsonRpcError(code=ERROR_INTERNAL_ERROR, message="Error")
        response = JsonRpcResponse(error=error, id=1)

        assert response.result is None
        assert response.error == error
        assert response.id == 1

    def test_response_validation_both_set(self):
        """Test that having both result and error raises validation error."""
        error = JsonRpcError(code=ERROR_INTERNAL_ERROR, message="Error")

        with pytest.raises(ValidationError):
            JsonRpcResponse(result="success", error=error, id=1)

    def test_response_serialization_success(self):
        """Test success response serialization omits error."""
        response = JsonRpcResponse(result=42, id=1)
        serialized = response.model_dump()

        assert serialized["result"] == 42
        assert "error" not in serialized

    def test_response_serialization_error(self):
        """Test error response serialization omits result."""
        error = JsonRpcError(code=ERROR_INTERNAL_ERROR, message="Error")
        response = JsonRpcResponse(error=error, id=1)
        serialized = response.model_dump()

        assert "result" not in serialized
        assert serialized["error"]["code"] == ERROR_INTERNAL_ERROR

    def test_response_validation_none_result_with_error(self):
        """Test that result=None with error set also raises validation error."""
        error = JsonRpcError(code=ERROR_INTERNAL_ERROR, message="Error")

        with pytest.raises(ValidationError):
            JsonRpcResponse(result=None, error=error, id=1)

    def test_response_no_typmod_in_wire_format(self):
        """Test that to_json_dict does not include _typmod."""
        response = JsonRpcResponse(result=42, id=1)
        wire = response.to_json_dict()

        assert "_typmod" not in wire


class TestPythonTypeToJsonType:
    """Tests for python_type_to_json_type conversion."""

    def test_int_to_integer(self):
        """Test int converts to integer."""
        assert python_type_to_json_type(int) == "integer"

    def test_float_to_number(self):
        """Test float converts to number."""
        assert python_type_to_json_type(float) == "number"

    def test_str_to_string(self):
        """Test str converts to string."""
        assert python_type_to_json_type(str) == "string"

    def test_bool_to_boolean(self):
        """Test bool converts to boolean."""
        assert python_type_to_json_type(bool) == "boolean"

    def test_list_to_array(self):
        """Test list converts to array."""
        assert python_type_to_json_type(list) == "array"

    def test_dict_to_object(self):
        """Test dict converts to object."""
        assert python_type_to_json_type(dict) == "object"


class TestBuildParamModelFromFn:
    """Tests for build_param_model_from_fn function."""

    def test_no_params(self):
        """Test function with no parameters returns None."""

        # This is a bit of an edge case - if there are no parameters, we return None instead of a model.
        def no_params():
            pass

        model = build_param_model_from_fn(no_params)
        assert model is None

    def test_with_params(self):
        """Test function with parameters creates model."""

        # This is the common case - we should get a Pydantic model with fields corresponding to the function parameters.
        def with_params(a: int, b: str):
            pass

        model = build_param_model_from_fn(with_params)
        assert model is not None

        # Validate the model works
        instance = model(a=1, b="test")
        data = instance.model_dump()
        assert data["a"] == 1
        assert data["b"] == "test"

    def test_with_defaults(self):
        """Test function with default parameters."""

        # This tests that parameters with default values are correctly represented in the model, and that the defaults are applied when creating an instance without those fields.
        def with_defaults(a: int, b: str = "default"):
            pass

        model = build_param_model_from_fn(with_defaults)
        assert model is not None

        instance = model(a=1)
        data = instance.model_dump()
        assert data["a"] == 1
        assert data["b"] == "default"


class TestJsonRpcMethodDecorator:
    """Tests for @json_rpc_method decorator."""

    def setup_method(self):
        """Clear registry before each test."""
        json_rpc_registry.clear()

    def test_register_sync_method(self):
        """Test registering a synchronous method."""

        @json_rpc_method(name="test.sync")
        def sync_method(a: int, b: int) -> int:
            return a + b

        assert "test.sync" in json_rpc_registry

    def test_register_async_method(self):
        """Test registering an async method."""

        @json_rpc_method(name="test.async")
        async def async_method(x: str) -> str:
            return x.upper()

        assert "test.async" in json_rpc_registry

    def test_register_with_default_name(self):
        """Test registering uses function name by default."""

        @json_rpc_method()
        # If no name is provided to the decorator, it should use the function's __name__ as the method name in the registry.
        def my_function():
            pass

        assert "my_function" in json_rpc_registry

    @pytest.mark.asyncio
    async def test_handler_with_list_params(self):
        """Test handler processes list params correctly."""

        @json_rpc_method(name="add")
        def add(a: int, b: int) -> int:
            return a + b

        handler = json_rpc_registry["add"]
        result = await handler([1, 2])

        assert isinstance(result, JsonRpcSuccess)
        assert result.data == 3

    @pytest.mark.asyncio
    async def test_handler_with_dict_params(self):
        """Test handler processes dict params correctly."""

        @json_rpc_method(name="multiply")
        def multiply(x: int, y: int) -> int:
            return x * y

        handler = json_rpc_registry["multiply"]
        result = await handler({"x": 3, "y": 4})

        assert isinstance(result, JsonRpcSuccess)
        assert result.data == 12

    @pytest.mark.asyncio
    async def test_handler_validation_error(self):
        """Test handler returns error on validation failure."""

        @json_rpc_method(name="typed")
        def typed(a: int) -> int:
            return a

        handler = json_rpc_registry["typed"]
        result = await handler({"a": "not_an_int"})

        assert isinstance(result, JsonRpcError)
        assert result.code == ERROR_INVALID_PARAMS

    @pytest.mark.asyncio
    async def test_handler_exception(self):
        """Test handler returns error on exception."""

        @json_rpc_method(name="failing")
        def failing():
            raise ValueError("Test error")

        handler = json_rpc_registry["failing"]
        result = await handler(None)

        assert isinstance(result, JsonRpcError)
        assert result.code == ERROR_INTERNAL_ERROR

    def test_rpc_reserved_prefix_raises(self):
        """Test that registering a method with 'rpc.' prefix raises ValueError."""
        with pytest.raises(ValueError, match="reserved"):

            @json_rpc_method(name="rpc.custom")
            # Methods starting with 'rpc.' are reserved for system methods, so this should raise an error.
            def custom_method():
                pass


class TestProcessRpc:
    """Tests for process_rpc dispatcher function."""

    def setup_method(self):
        """Set up test methods in registry."""
        json_rpc_registry.clear()

        @json_rpc_method(name="test.add")
        def add(a: int, b: int) -> int:
            return a + b

        @json_rpc_method(name="test.echo")
        def echo(message: str) -> str:
            return message

        @json_rpc_method(name="test.error")
        def error_method():
            raise ValueError("Intentional error")

    @pytest.mark.asyncio
    async def test_single_request_success(self):
        """Test processing a single successful request."""
        payload = {
            "jsonrpc": "2.0",
            "method": "test.add",
            "params": [1, 2],
            "id": 1,
        }

        response = await process_rpc(payload)

        assert isinstance(response, dict)
        assert response["jsonrpc"] == "2.0"
        assert response["result"] == 3
        assert response["id"] == 1

    @pytest.mark.asyncio
    async def test_single_request_method_not_found(self):
        """Test processing a request with non-existent method."""
        payload = {
            "jsonrpc": "2.0",
            "method": "nonexistent",
            "params": [],
            "id": 1,
        }

        response = await process_rpc(payload)

        assert isinstance(response, dict)
        assert response["error"]["code"] == ERROR_METHOD_NOT_FOUND
        assert response["id"] == 1

    @pytest.mark.asyncio
    async def test_single_request_invalid_params(self):
        """Test processing a request with invalid parameters."""
        payload = {
            "jsonrpc": "2.0",
            "method": "test.add",
            "params": {"a": "not_int", "b": 2},
            "id": 1,
        }

        response = await process_rpc(payload)

        assert isinstance(response, dict)
        assert response["error"]["code"] == ERROR_INVALID_PARAMS

    @pytest.mark.asyncio
    async def test_notification_returns_none(self):
        """Test that notifications (no id) return None."""
        payload = {
            "jsonrpc": "2.0",
            "method": "test.echo",
            "params": {"message": "hello"},
        }

        response = await process_rpc(payload)

        assert response is None

    @pytest.mark.asyncio
    async def test_empty_payload_error(self):
        """Test processing empty payload returns error."""
        response = await process_rpc({})

        assert isinstance(response, dict)
        assert response["error"]["code"] == ERROR_INVALID_REQUEST

    @pytest.mark.asyncio
    async def test_batch_request_success(self):
        """Test processing a batch of requests."""
        payload = [
            {"jsonrpc": "2.0", "method": "test.add", "params": [1, 2], "id": 1},
            {
                "jsonrpc": "2.0",
                "method": "test.echo",
                "params": {"message": "hi"},
                "id": 2,
            },
        ]

        responses = await process_rpc(payload)

        assert isinstance(responses, list)
        assert len(responses) == 2
        # Find responses by id
        resp_map = {r["id"]: r for r in responses}
        assert resp_map[1]["result"] == 3
        assert resp_map[2]["result"] == "hi"

    @pytest.mark.asyncio
    async def test_batch_with_errors(self):
        """Test batch with some failed requests."""
        payload = [
            {"jsonrpc": "2.0", "method": "test.add", "params": [1, 2], "id": 1},
            {"jsonrpc": "2.0", "method": "nonexistent", "id": 2},
        ]

        responses = await process_rpc(payload)

        assert isinstance(responses, list)
        assert len(responses) == 2
        resp_map = {r["id"]: r for r in responses}
        assert resp_map[1]["result"] == 3
        assert resp_map[2]["error"]["code"] == ERROR_METHOD_NOT_FOUND

    @pytest.mark.asyncio
    async def test_batch_with_invalid_request(self):
        """Test batch with invalid request in the batch."""
        payload = [
            {"jsonrpc": "2.0", "method": "test.add", "params": [1, 2], "id": 1},
            {"invalid": "request"},  # Invalid request
        ]

        responses = await process_rpc(payload)

        # Should have responses including error for invalid request
        assert isinstance(responses, list)
        assert len(responses) >= 1

    @pytest.mark.asyncio
    async def test_rpc_discover(self):
        """Test that rpc.discover returns an OpenRPC document."""
        payload = {"jsonrpc": "2.0", "method": "rpc.discover", "id": 1}

        response = await process_rpc(payload)

        assert isinstance(response, dict)
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["openrpc"] == "1.2.6"
        assert "methods" in response["result"]

    @pytest.mark.asyncio
    async def test_batch_all_notifications_returns_none(self):
        """Test that a batch of only notifications returns None."""
        payload = [
            {"jsonrpc": "2.0", "method": "test.echo", "params": {"message": "a"}},
            {"jsonrpc": "2.0", "method": "test.echo", "params": {"message": "b"}},
        ]

        response = await process_rpc(payload)

        assert response is None


class TestBuildOpenRpcDocument:
    """Tests for OpenRPC document generation."""

    def setup_method(self):
        """Set up test methods in registry."""
        json_rpc_registry.clear()

        @json_rpc_method(name="math.add")
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        @json_rpc_method(name="string.upper")
        def upper(text: str) -> str:
            """Convert to uppercase."""
            return text.upper()

    def test_document_structure(self):
        """Test OpenRPC document has correct structure."""
        doc = build_openrpc_document(title="Test API", version="1.0.0")

        assert doc["openrpc"] == "1.2.6"
        assert doc["info"]["title"] == "Test API"
        assert doc["info"]["version"] == "1.0.0"
        assert "methods" in doc

    def test_document_methods(self):
        """Test OpenRPC document includes registered methods."""
        doc = build_openrpc_document()

        method_names = [m["name"] for m in doc["methods"]]
        assert "math.add" in method_names
        assert "string.upper" in method_names

    def test_method_params(self):
        """Test OpenRPC document includes method parameters."""
        doc = build_openrpc_document()

        add_method = next(m for m in doc["methods"] if m["name"] == "math.add")
        param_names = [p["name"] for p in add_method["params"]]

        assert "a" in param_names
        assert "b" in param_names

    def test_method_result(self):
        """Test OpenRPC document includes method result."""
        doc = build_openrpc_document()

        add_method = next(m for m in doc["methods"] if m["name"] == "math.add")

        assert add_method["result"]["name"] == "result"
        assert add_method["result"]["schema"]["type"] == "integer"
