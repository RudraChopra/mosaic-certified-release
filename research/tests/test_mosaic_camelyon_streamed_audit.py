from __future__ import annotations

from audit_mosaic_camelyon_streamed_confirmation import normalize


def test_camelyon_audit_normalization_is_stable() -> None:
    value = {
        "z": [0.12345678901234],
        "a": {"b": 2, "a": 1},
    }
    assert normalize(value) == {
        "a": {"a": 1, "b": 2},
        "z": [0.123456789012],
    }
