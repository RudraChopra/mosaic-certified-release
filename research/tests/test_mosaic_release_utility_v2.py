from __future__ import annotations

from mosaic_release_utility_common_v2 import selected_jobs


def test_v2_reuses_the_v1_selection_interface() -> None:
    assert callable(selected_jobs)
