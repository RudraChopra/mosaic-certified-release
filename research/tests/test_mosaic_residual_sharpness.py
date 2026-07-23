from __future__ import annotations

import math

import numpy as np

from run_mosaic_residual_sharpness import exact_bounds


def test_residual_floor_equals_eta_times_binary_capacity():
    probabilities = np.asarray(
        [
            [[0.5, 0.5], [0.5, 0.5]],
            [[0.5, 0.5], [0.5, 0.5]],
        ]
    )
    bridge = {
        "labels": [
            {"transform": np.eye(2).tolist(), "contamination": 0.2},
            {"transform": np.eye(2).tolist(), "contamination": 0.2},
        ]
    }
    channel = np.eye(2)
    full = exact_bounds(
        probabilities=probabilities,
        radii=np.zeros((2, 2)),
        bridge=bridge,
        channel=channel,
        decoder=(0, 1),
        zero_residual=False,
    )
    common = exact_bounds(
        probabilities=probabilities,
        radii=np.zeros((2, 2)),
        bridge=bridge,
        channel=channel,
        decoder=(0, 1),
        zero_residual=True,
    )
    assert math.isclose(full["source_advantage_upper"], 0.2, abs_tol=1e-12)
    assert math.isclose(common["source_advantage_upper"], 0.0, abs_tol=1e-12)


def test_residual_utility_term_survives_zero_radius():
    probabilities = np.asarray(
        [
            [[1.0, 0.0], [1.0, 0.0]],
            [[0.0, 1.0], [0.0, 1.0]],
        ]
    )
    bridge = {
        "labels": [
            {"transform": np.eye(2).tolist(), "contamination": 0.25},
            {"transform": np.eye(2).tolist(), "contamination": 0.25},
        ]
    }
    result = exact_bounds(
        probabilities=probabilities,
        radii=np.zeros((2, 2)),
        bridge=bridge,
        channel=np.eye(2),
        decoder=(0, 1),
        zero_residual=False,
    )
    assert math.isclose(
        result["worst_conditional_error_upper"], 0.25, abs_tol=1e-12
    )
