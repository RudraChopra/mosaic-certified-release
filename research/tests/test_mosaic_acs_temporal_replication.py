from __future__ import annotations

import json

from run_mosaic_acs_temporal_replication import (
    FAMILYWISE_DELTA,
    TABLE_DELTA,
    WITNESSES,
    expected_protocol,
)


def test_temporal_replication_family_is_exactly_the_three_discovery_rows() -> None:
    expected = {
        ("FL", "public_coverage", 1401, "TaCo::components_removed=1"),
        ("FL", "public_coverage", 1402, "R-LACE::rank=4"),
        ("IL", "public_coverage", 1402, "Identity::unedited"),
    }
    observed = {
        (
            row["target_state"],
            row["task"],
            row["seed"],
            row["candidate"],
        )
        for row in WITNESSES
    }
    assert observed == expected
    assert TABLE_DELTA == FAMILYWISE_DELTA / 3


def test_temporal_replication_protocol_is_json_stable() -> None:
    protocol = expected_protocol()
    assert protocol["confirmation_year"] == "2022"
    assert protocol["hypotheses"] == 3
    assert protocol["maximum_confirmation_rows_per_interface"] == 128_000
    assert len(json.dumps(protocol, sort_keys=True)) > 500
