import numpy as np

from analyze_mosaic_symmetric_scope_stress import direct_target_region_status


def test_direct_target_region_status_handles_all_source_label_rows():
    target = np.asarray([[[0.7, 0.3], [0.2, 0.8]], [[0.4, 0.6], [0.6, 0.4]]])
    empirical = np.asarray([[[0.65, 0.35], [0.2, 0.8]], [[0.45, 0.55], [0.6, 0.4]]])
    radii = np.full((2, 2), 0.1)
    inside, excess = direct_target_region_status(target, empirical, radii)
    assert inside
    assert np.isclose(excess, 0.0)


def test_direct_target_region_status_detects_one_row_violation():
    target = np.asarray([[[0.8, 0.2], [0.2, 0.8]], [[0.4, 0.6], [0.6, 0.4]]])
    empirical = np.asarray([[[0.65, 0.35], [0.2, 0.8]], [[0.45, 0.55], [0.6, 0.4]]])
    radii = np.full((2, 2), 0.1)
    inside, excess = direct_target_region_status(target, empirical, radii)
    assert not inside
    assert np.isclose(excess, 0.2)
