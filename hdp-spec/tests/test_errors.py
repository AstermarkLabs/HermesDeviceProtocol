import pytest
from hdp_proto.errors import ErrorCode, err, ok


def test_ok_shape():
    result = ok({"devices": []})
    assert result == {"ok": True, "data": {"devices": []}}


def test_err_shape_uses_canonical_hint_by_default():
    result = err(ErrorCode.NO_MATCHING_DEVICE, "no candidates")
    assert result["ok"] is False
    error = result["error"]
    assert error["code"] == "no_matching_device"
    assert error["message"] == "no candidates"
    assert error["hint"]  # non-empty
    assert "device_status_get" in error["hint"]


def test_err_accepts_an_exception_as_detail():
    exc = RuntimeError("boom")
    result = err(ErrorCode.BRIDGE_UNAVAILABLE, exc)
    assert result["error"]["message"] == "boom"


def test_err_hint_override():
    result = err(ErrorCode.NOT_IMPLEMENTED, "x", hint="custom hint")
    assert result["error"]["hint"] == "custom hint"


def test_err_carries_structured_context_without_overwriting_core_fields():
    result = err(
        ErrorCode.VERSION_INCOMPATIBLE,
        "no overlap",
        extras={"node_supports": [99], "plugin_supports": [1, 2]},
    )

    assert result["error"] == {
        "code": "version_incompatible",
        "message": "no overlap",
        "hint": "No mutually supported capability version. Call device_status_get to see the "
        "device's advertised versions.",
        "node_supports": [99],
        "plugin_supports": [1, 2],
    }

    with pytest.raises(ValueError, match="reserved error field"):
        err(ErrorCode.DEVICE_OFFLINE, "x", extras={"code": "wrong"})


def test_error_codes_are_unique_string_values():
    values = [c.value for c in ErrorCode]
    assert len(values) == len(set(values))
