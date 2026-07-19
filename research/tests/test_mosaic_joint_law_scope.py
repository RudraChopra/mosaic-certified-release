from __future__ import annotations

import numpy as np

from mosaic_channel import (
    adaptive_channel_attacker_confidence_bound,
    population_balanced_attacker_accuracy,
)


def test_within_label_chance_does_not_imply_unconditional_source_privacy() -> None:
    # C equals Y and is identical across sources after conditioning on Y.
    within_label = np.asarray([[1.0, 0.0], [1.0, 0.0]])
    assert population_balanced_attacker_accuracy(within_label) == 0.5

    # Natural label prevalence differs sharply by source.  The joint X=(Y,C)
    # law therefore exposes source through a channel that reveals C=Y.
    joint = np.asarray(
        [
            [0.9, 0.0, 0.0, 0.1],
            [0.1, 0.0, 0.0, 0.9],
        ]
    )
    lifted = np.asarray(
        [
            [1.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, 1.0],
        ]
    )
    accuracy = population_balanced_attacker_accuracy(joint, lifted)
    assert np.isclose(accuracy, 0.9)

    certificate = adaptive_channel_attacker_confidence_bound(
        joint,
        lifted,
        l1_radii=(0.0, 0.0),
    )
    assert np.isclose(certificate.balanced_accuracy, accuracy)


def test_joint_lift_reduces_to_the_registered_channel() -> None:
    channel = np.asarray([[0.8, 0.2], [0.3, 0.7]])
    lifted = np.vstack((channel, channel))
    assert lifted.shape == (4, 2)
    np.testing.assert_allclose(lifted.sum(axis=1), 1.0)
