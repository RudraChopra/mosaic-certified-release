"""Runtime semantics for persistent and bounded-query MOSAIC releases."""

from __future__ import annotations

from collections.abc import Hashable, MutableMapping, Sequence
from dataclasses import dataclass, field
from itertools import product

import numpy as np


MAX_PRODUCT_OUTPUTS = 1_000_000


def validate_release_channel(values: Sequence[Sequence[float]]) -> np.ndarray:
    channel = np.asarray(values, dtype=np.float64)
    if channel.ndim != 2 or min(channel.shape) < 2:
        raise ValueError("release channel must have at least two rows and columns")
    if not np.isfinite(channel).all() or np.any(channel < -1e-12):
        raise ValueError("release channel must be finite and nonnegative")
    if not np.allclose(channel.sum(axis=1), 1.0, atol=1e-10, rtol=0.0):
        raise ValueError("every release-channel row must sum to one")
    return np.clip(channel, 0.0, 1.0)


def independent_repetition_channel(
    release_channel: Sequence[Sequence[float]], query_count: int
) -> np.ndarray:
    """Return the product channel for fresh independent repeated releases.

    Output columns use lexicographic tuples from ``product(range(L), repeat=r)``.
    The construction is intended for threat-model audits at modest ``L**r``;
    persistent release is the default production semantics.
    """

    channel = validate_release_channel(release_channel)
    if not isinstance(query_count, int) or query_count < 1:
        raise ValueError("query_count must be a positive integer")
    output_count = channel.shape[1] ** query_count
    if output_count > MAX_PRODUCT_OUTPUTS:
        raise ValueError(
            f"product channel has {output_count:,} outputs; "
            f"cap is {MAX_PRODUCT_OUTPUTS:,}"
        )
    output_tuples = tuple(product(range(channel.shape[1]), repeat=query_count))
    result = np.asarray(
        [
            [
                float(np.prod(channel[fine_token, output_tuple]))
                for output_tuple in output_tuples
            ]
            for fine_token in range(channel.shape[0])
        ],
        dtype=np.float64,
    )
    result /= result.sum(axis=1, keepdims=True)
    return result


@dataclass
class PersistentReleaseMechanism:
    """Sample once per protected item and return the same token thereafter.

    ``state`` must be private mechanism state. A production caller can provide a
    durable transactional mapping; the default in-memory mapping is suitable
    for tests and single-process demonstrations. Reusing an item identifier for
    a different fine token is rejected because it would make persistence
    semantics ambiguous.
    """

    release_channel: Sequence[Sequence[float]]
    rng: np.random.Generator
    state: MutableMapping[Hashable, tuple[int, int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.release_channel = validate_release_channel(self.release_channel)
        if not isinstance(self.rng, np.random.Generator):
            raise TypeError("rng must be a numpy Generator")

    def release(self, item_identifier: Hashable, fine_token: int) -> int:
        if item_identifier is None:
            raise ValueError("item_identifier must be stable and non-null")
        if not isinstance(fine_token, (int, np.integer)):
            raise TypeError("fine_token must be an integer")
        token = int(fine_token)
        if not 0 <= token < self.release_channel.shape[0]:
            raise ValueError("fine_token is outside the channel alphabet")
        if item_identifier in self.state:
            stored_fine, stored_release = self.state[item_identifier]
            if stored_fine != token:
                raise ValueError(
                    "item_identifier was already bound to a different fine token"
                )
            return int(stored_release)
        released = int(
            self.rng.choice(
                self.release_channel.shape[1], p=self.release_channel[token]
            )
        )
        self.state[item_identifier] = (token, released)
        return released
