"""
test_opdata.py - Tests for ayuna_core.opdata module.
"""

from ayuna_core.opdata import (
    OpFailure,
    OpResult,
    OpSuccess,
    ensure_result_from_dict,
    ensure_result_from_json,
)


class TestOpSuccess:
    """Tests for OpSuccess model."""

    def test_create_success(self):
        """Should create OpSuccess with default values."""
        result = OpSuccess()
        assert result.typid == "success"
        assert result.code == 0
        assert result.result is None

    def test_create_success_with_result(self):
        """Should create OpSuccess with result data."""
        result = OpSuccess(code=200, result={"data": "value"})
        assert result.code == 200
        assert result.result == {"data": "value"}

    def test_serialization(self):
        """Should serialize to dict with type info."""
        result = OpSuccess(result="test")
        data = result.to_json_dict()
        assert data["typid"] == "success"
        assert data["result"] == "test"


class TestOpFailure:
    """Tests for OpFailure model."""

    def test_create_failure(self):
        """Should create OpFailure with default values."""
        result = OpFailure()
        assert result.typid == "failure"
        assert result.code == -1
        assert result.error is None

    def test_create_failure_with_error(self):
        """Should create OpFailure with error data."""
        result = OpFailure(code=500, error="Something went wrong")
        assert result.code == 500
        assert result.error == "Something went wrong"

    def test_serialization(self):
        """Should serialize to dict with type info."""
        result = OpFailure(error="error message")
        data = result.to_json_dict()
        assert data["typid"] == "failure"
        assert data["error"] == "error message"


class TestEnsureResultFromJson:
    """Tests for ensure_result_from_json function."""

    def test_parse_success_json(self):
        """Should parse OpSuccess from JSON."""
        success = OpSuccess(code=0, result="ok")
        json_str = success.to_json_str()

        result = ensure_result_from_json(json_str)

        assert isinstance(result, OpSuccess)
        assert result.result == "ok"

    def test_parse_failure_json(self):
        """Should parse OpFailure from JSON."""
        failure = OpFailure(code=500, error="error")
        json_str = failure.to_json_str()

        result = ensure_result_from_json(json_str)

        assert isinstance(result, OpFailure)
        assert result.error == "error"

    def test_parse_plain_success_json(self):
        """Should parse plain success dict as OpSuccess."""
        import orjson

        json_str = orjson.dumps({"typid": "success", "code": 0, "result": "data"})

        result = ensure_result_from_json(json_str)

        assert isinstance(result, OpSuccess)
        assert result.result == "data"

    def test_parse_plain_failure_json(self):
        """Should parse plain failure dict as OpFailure."""
        import orjson

        json_str = orjson.dumps({"typid": "failure", "code": -1, "error": "err"})

        result = ensure_result_from_json(json_str)

        assert isinstance(result, OpFailure)

    def test_parse_invalid_json_returns_failure(self):
        """Should return OpFailure for invalid JSON."""
        result = ensure_result_from_json(b"not valid json")

        assert isinstance(result, OpFailure)
        assert result.code == 400


class TestEnsureResultFromDict:
    """Tests for ensure_result_from_dict function."""

    def test_parse_success_dict(self):
        """Should parse OpSuccess from dict."""
        success = OpSuccess(code=0, result="ok")
        data = success.to_json_dict()

        result = ensure_result_from_dict(data)

        assert isinstance(result, OpSuccess)
        assert result.result == "ok"

    def test_parse_failure_dict(self):
        """Should parse OpFailure from dict."""
        failure = OpFailure(code=500, error="error")
        data = failure.to_json_dict()

        result = ensure_result_from_dict(data)

        assert isinstance(result, OpFailure)

    def test_parse_plain_success_dict(self):
        """Should parse plain dict as OpSuccess."""
        data = {"typid": "success", "code": 200, "result": {"key": "value"}}

        result = ensure_result_from_dict(data)

        assert isinstance(result, OpSuccess)
        assert result.code == 200

    def test_parse_plain_failure_dict(self):
        """Should parse plain dict as OpFailure."""
        data = {"typid": "failure", "code": 404, "error": "Not found"}

        result = ensure_result_from_dict(data)

        assert isinstance(result, OpFailure)
        assert result.code == 404


class TestOpResultUnion:
    """Tests for OpResult discriminated union type."""

    def test_discriminator_success(self):
        """Should discriminate OpSuccess by typid."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(OpResult)

        result = adapter.validate_python({"typid": "success", "result": "data"})
        assert isinstance(result, OpSuccess)

    def test_discriminator_failure(self):
        """Should discriminate OpFailure by typid."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(OpResult)

        result = adapter.validate_python({"typid": "failure", "error": "err"})
        assert isinstance(result, OpFailure)
