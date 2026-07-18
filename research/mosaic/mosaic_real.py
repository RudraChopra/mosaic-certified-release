"""Real-feature utilities for MOSAIC's finite-token evaluation protocol."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from scipy.optimize import linprog
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from mosaic_channel import normalized_attacker_advantage
from mosaic_envelope import weissman_l1_radius
from mosaic_invariant import (
    adaptive_pre_release_attacker_certificate,
    pre_release_utility_certificate,
)


SPLIT_TRAIN = 0
SPLIT_VALIDATION = 1
SPLIT_EXTERNAL = 2
BIOS_CLINICAL_PROFESSIONS = frozenset({3, 6, 7, 13, 19, 22, 25})


@dataclass(frozen=True)
class FrozenStore:
    path: Path
    manifest: dict[str, object]
    features: np.ndarray
    target: np.ndarray
    source: np.ndarray
    split: np.ndarray


@dataclass(frozen=True)
class ScoreTokenizer:
    scaler: StandardScaler
    classifier: LogisticRegression
    thresholds: tuple[float, ...]

    @property
    def token_count(self) -> int:
        return len(self.thresholds) + 1

    def scores(self, features: np.ndarray) -> np.ndarray:
        transformed = self.scaler.transform(np.asarray(features, dtype=np.float64))
        probabilities = self.classifier.predict_proba(transformed)
        class_one = int(np.flatnonzero(self.classifier.classes_ == 1)[0])
        return np.asarray(probabilities[:, class_one], dtype=np.float64)

    def encode(self, features: np.ndarray) -> np.ndarray:
        return np.digitize(self.scores(features), self.thresholds).astype(np.int16)


@dataclass(frozen=True)
class TokenTable:
    probabilities: np.ndarray
    counts: np.ndarray
    l1_radii: np.ndarray
    labels: tuple[int, ...]
    sources: tuple[int, ...]
    token_count: int
    familywise_delta: float


@dataclass(frozen=True)
class ExternalTokenRisk:
    privacy_advantage_by_label: tuple[float | None, ...]
    worst_privacy_advantage: float | None
    conditional_error_by_label_source: tuple[tuple[float | None, ...], ...]
    worst_conditional_error: float | None
    missing_strata: tuple[tuple[int, int], ...]
    estimable: bool


@dataclass(frozen=True)
class DeterministicChannelSolution:
    release_channel: np.ndarray
    decoder: tuple[int, ...]
    certified_worst_conditional_error: float
    certified_privacy_advantages: tuple[float, ...]
    evaluated_channel_decoder_pairs: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_frozen_store(path: Path, *, target_mode: str = "native_binary") -> FrozenStore:
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    arrays = manifest["arrays"]
    features = np.load(path / arrays.get("z", "z.npy"), mmap_mode="r")
    native_target = np.load(path / arrays.get("y", "y.npy"), mmap_mode="r")
    source = np.load(path / arrays.get("s", "s.npy"), mmap_mode="r")
    split = np.load(path / arrays.get("split", "split.npy"), mmap_mode="r")
    expected = int(manifest["n_examples"])
    if not all(len(values) == expected for values in (features, native_target, source, split)):
        raise ValueError("store arrays do not match the manifest")
    if target_mode == "native_binary":
        target = np.asarray(native_target, dtype=np.int16)
        if set(np.unique(target)) != {0, 1}:
            raise ValueError("native_binary requires exactly labels 0 and 1")
    elif target_mode == "bios_clinical_binary":
        target = np.isin(native_target, tuple(BIOS_CLINICAL_PROFESSIONS)).astype(np.int16)
    else:
        raise ValueError(f"unknown target mode: {target_mode}")
    binary_source = np.asarray(source, dtype=np.int16)
    if set(np.unique(binary_source)) != {0, 1}:
        raise ValueError("the exact real-data protocol currently requires two sources")
    return FrozenStore(
        path=path,
        manifest=manifest,
        features=features,
        target=target,
        source=binary_source,
        split=split,
    )


def balanced_stratum_sample(
    indices: Iterable[int],
    target: np.ndarray,
    source: np.ndarray,
    *,
    maximum_total: int,
    seed: int,
) -> np.ndarray:
    """Sample the same count from each represented source-label stratum."""

    selected = np.asarray(tuple(indices), dtype=np.int64)
    if selected.ndim != 1 or selected.size == 0:
        raise ValueError("indices must be a nonempty one-dimensional collection")
    groups = tuple(
        sorted({(int(target[index]), int(source[index])) for index in selected})
    )
    if len(groups) < 2:
        raise ValueError("at least two represented strata are required")
    grouped = {
        group: selected[
            (target[selected] == group[0]) & (source[selected] == group[1])
        ]
        for group in groups
    }
    per_group = min(
        min(len(values) for values in grouped.values()),
        max(1, int(maximum_total) // len(groups)),
    )
    rng = np.random.default_rng(seed)
    sampled = [
        rng.choice(values, size=per_group, replace=False).astype(np.int64)
        if len(values) > per_group
        else np.asarray(values, dtype=np.int64)
        for values in grouped.values()
    ]
    return np.sort(np.concatenate(sampled))


def random_cap_sample(
    indices: Iterable[int], *, maximum_total: int, seed: int
) -> np.ndarray:
    """Use every available training row up to a deterministic random cap."""

    selected = np.asarray(tuple(indices), dtype=np.int64)
    if selected.ndim != 1 or selected.size == 0:
        raise ValueError("indices must be a nonempty one-dimensional collection")
    if maximum_total <= 0:
        raise ValueError("maximum_total must be positive")
    if len(selected) <= maximum_total:
        return np.sort(selected)
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(selected, size=maximum_total, replace=False).astype(np.int64))


def fit_score_tokenizer(
    features: np.ndarray,
    target: np.ndarray,
    *,
    token_count: int,
    seed: int,
) -> ScoreTokenizer:
    if token_count < 2:
        raise ValueError("token_count must be at least two")
    values = np.asarray(features, dtype=np.float64)
    labels = np.asarray(target, dtype=np.int16)
    if values.ndim != 2 or labels.shape != (len(values),):
        raise ValueError("features and targets have incompatible shapes")
    if set(np.unique(labels)) != {0, 1}:
        raise ValueError("score tokenizer requires binary targets")
    scaler = StandardScaler().fit(values)
    standardized = scaler.transform(values)
    classifier = LogisticRegression(
        C=1.0,
        class_weight="balanced",
        max_iter=2000,
        solver="lbfgs",
        random_state=int(seed),
    ).fit(standardized, labels)
    class_one = int(np.flatnonzero(classifier.classes_ == 1)[0])
    scores = classifier.predict_proba(standardized)[:, class_one]
    quantiles = np.linspace(0.0, 1.0, token_count + 1)[1:-1]
    thresholds = np.quantile(scores, quantiles)
    if np.any(np.diff(thresholds) <= 1e-12):
        thresholds = np.linspace(0.0, 1.0, token_count + 1)[1:-1]
    return ScoreTokenizer(
        scaler=scaler,
        classifier=classifier,
        thresholds=tuple(float(value) for value in thresholds),
    )


def build_token_table(
    tokens: Sequence[int],
    target: Sequence[int],
    source: Sequence[int],
    *,
    token_count: int,
    familywise_delta: float,
    labels: Sequence[int] = (0, 1),
    sources: Sequence[int] = (0, 1),
) -> TokenTable:
    token_array = np.asarray(tokens, dtype=np.int64)
    target_array = np.asarray(target, dtype=np.int64)
    source_array = np.asarray(source, dtype=np.int64)
    if not (
        token_array.shape == target_array.shape == source_array.shape
        and token_array.ndim == 1
    ):
        raise ValueError("tokens, target, and source must have matching vectors")
    if np.any(token_array < 0) or np.any(token_array >= token_count):
        raise ValueError("token is outside the registered alphabet")
    if not 0.0 < familywise_delta < 1.0:
        raise ValueError("familywise_delta must lie in (0, 1)")
    label_values = tuple(int(value) for value in labels)
    source_values = tuple(int(value) for value in sources)
    counts = np.zeros((len(label_values), len(source_values), token_count), dtype=np.int64)
    probabilities = np.zeros_like(counts, dtype=np.float64)
    radii = np.zeros(counts.shape[:2], dtype=np.float64)
    stratum_delta = familywise_delta / (len(label_values) * len(source_values))
    for label_index, label in enumerate(label_values):
        for source_index, current_source in enumerate(source_values):
            mask = (target_array == label) & (source_array == current_source)
            counts[label_index, source_index] = np.bincount(
                token_array[mask], minlength=token_count
            )
            n = int(counts[label_index, source_index].sum())
            if n == 0:
                probabilities[label_index, source_index] = 1.0 / token_count
                radii[label_index, source_index] = 2.0
            else:
                probabilities[label_index, source_index] = counts[label_index, source_index] / n
                radii[label_index, source_index] = weissman_l1_radius(
                    n, token_count, stratum_delta
                )
    return TokenTable(
        probabilities=probabilities,
        counts=counts,
        l1_radii=radii,
        labels=label_values,
        sources=source_values,
        token_count=int(token_count),
        familywise_delta=float(familywise_delta),
    )


def ordered_smoothing_library(token_count: int, *, smoothing: float) -> tuple[np.ndarray, ...]:
    if token_count < 2 or not 0.0 <= smoothing <= 1.0:
        raise ValueError("invalid ordered smoothing configuration")
    identity = np.eye(token_count, dtype=np.float64)
    channel = (1.0 - smoothing) * identity
    for token in range(token_count):
        neighbors = [value for value in (token - 1, token + 1) if 0 <= value < token_count]
        for neighbor in neighbors:
            channel[token, neighbor] += smoothing / len(neighbors)
    return identity, channel


def optimize_deterministic_invariant_channel(
    table: TokenTable,
    *,
    common_channels_by_label: Sequence[Sequence[Sequence[Sequence[float]]]],
    contaminations: Sequence[float],
    privacy_advantage_thresholds: Sequence[float],
    released_token_count: int,
) -> DeterministicChannelSolution | None:
    """Exhaust every deterministic release and decoder for small real tables."""

    label_count, source_count, fine_count = table.probabilities.shape
    eta = tuple(float(value) for value in contaminations)
    thresholds = tuple(float(value) for value in privacy_advantage_thresholds)
    if len(eta) != label_count or len(thresholds) != label_count:
        raise ValueError("contaminations and thresholds need one value per label")
    if len(common_channels_by_label) != label_count or released_token_count < 2:
        raise ValueError("invalid deterministic optimization configuration")
    best: DeterministicChannelSolution | None = None
    evaluated = 0
    for mapping in product(range(released_token_count), repeat=fine_count):
        channel = np.zeros((fine_count, released_token_count), dtype=np.float64)
        channel[np.arange(fine_count), np.asarray(mapping, dtype=np.int64)] = 1.0
        privacy = tuple(
            adaptive_pre_release_attacker_certificate(
                table.probabilities[label],
                channel,
                l1_radii=table.l1_radii[label],
                common_fine_token_channels=common_channels_by_label[label],
                contamination=eta[label],
            )
            for label in range(label_count)
        )
        privacy_advantages = tuple(value.normalized_advantage for value in privacy)
        if any(
            privacy_advantages[label] > thresholds[label] + 1e-10
            for label in range(label_count)
        ):
            evaluated += label_count**released_token_count
            continue
        for decoder in product(range(label_count), repeat=released_token_count):
            evaluated += 1
            certificates = tuple(
                pre_release_utility_certificate(
                    table.probabilities[label, source],
                    channel,
                    decoder,
                    true_label=label,
                    l1_radius=float(table.l1_radii[label, source]),
                    common_fine_token_channels=common_channels_by_label[label],
                    contamination=eta[label],
                )
                for label in range(label_count)
                for source in range(source_count)
            )
            error = max(value.error_probability for value in certificates)
            candidate = DeterministicChannelSolution(
                release_channel=channel,
                decoder=tuple(int(value) for value in decoder),
                certified_worst_conditional_error=float(error),
                certified_privacy_advantages=privacy_advantages,
                evaluated_channel_decoder_pairs=evaluated,
            )
            if best is None or (
                candidate.certified_worst_conditional_error
                < best.certified_worst_conditional_error - 1e-12
            ):
                best = candidate
    if best is None:
        return None
    return DeterministicChannelSolution(
        release_channel=best.release_channel,
        decoder=best.decoder,
        certified_worst_conditional_error=best.certified_worst_conditional_error,
        certified_privacy_advantages=best.certified_privacy_advantages,
        evaluated_channel_decoder_pairs=evaluated,
    )


def evaluate_external_channel(
    tokens: Sequence[int],
    target: Sequence[int],
    source: Sequence[int],
    channel: Sequence[Sequence[float]],
    decoder: Sequence[int],
    *,
    labels: Sequence[int] = (0, 1),
    sources: Sequence[int] = (0, 1),
) -> ExternalTokenRisk:
    release = np.asarray(channel, dtype=np.float64)
    decoder_array = np.asarray(decoder, dtype=np.int64)
    if release.ndim != 2 or decoder_array.shape != (release.shape[1],):
        raise ValueError("channel and decoder have incompatible shapes")
    table = build_token_table(
        tokens,
        target,
        source,
        token_count=release.shape[0],
        familywise_delta=0.5,
        labels=labels,
        sources=sources,
    )
    missing = []
    privacy = []
    errors = []
    for label_index, label in enumerate(table.labels):
        label_missing = [
            table.counts[label_index, source_index].sum() == 0
            for source_index in range(len(table.sources))
        ]
        for source_index, is_missing in enumerate(label_missing):
            if is_missing:
                missing.append((label, table.sources[source_index]))
        if any(label_missing):
            privacy.append(None)
        else:
            released = table.probabilities[label_index] @ release
            balanced_accuracy = float(np.max(released, axis=0).sum() / len(table.sources))
            privacy.append(
                normalized_attacker_advantage(balanced_accuracy, len(table.sources))
            )
        label_errors = []
        loss = (decoder_array != label).astype(np.float64)
        for source_index in range(len(table.sources)):
            if label_missing[source_index]:
                label_errors.append(None)
            else:
                label_errors.append(
                    float(table.probabilities[label_index, source_index] @ release @ loss)
                )
        errors.append(tuple(label_errors))
    estimable = not missing
    return ExternalTokenRisk(
        privacy_advantage_by_label=tuple(privacy),
        worst_privacy_advantage=(max(float(value) for value in privacy) if estimable else None),
        conditional_error_by_label_source=tuple(errors),
        worst_conditional_error=(
            max(float(value) for row in errors for value in row) if estimable else None
        ),
        missing_strata=tuple(missing),
        estimable=estimable,
    )


def minimum_contamination_fraction(
    reference_source_laws: Sequence[Sequence[float]],
    external_source_laws: Sequence[Sequence[float]],
    common_transform_extremes: Sequence[Sequence[Sequence[float]]],
) -> float:
    """Return the exact plug-in minimum eta for the structured shift class.

    This is an empirical model-fit diagnostic, not a confidence statement.
    With alpha_j = t w_j, maximizing retained mass is a linear program.
    """

    reference = np.asarray(reference_source_laws, dtype=np.float64)
    external = np.asarray(external_source_laws, dtype=np.float64)
    transforms = tuple(np.asarray(value, dtype=np.float64) for value in common_transform_extremes)
    if reference.shape != external.shape or reference.ndim != 2:
        raise ValueError("reference and external laws must share shape (sources, tokens)")
    if not transforms or any(
        transform.shape != (reference.shape[1], reference.shape[1])
        for transform in transforms
    ):
        raise ValueError("common transforms have incompatible shapes")
    retained_components = np.stack([reference @ transform for transform in transforms])
    constraints = []
    limits = []
    for source_index in range(reference.shape[0]):
        for token in range(reference.shape[1]):
            constraints.append(retained_components[:, source_index, token])
            limits.append(external[source_index, token])
    constraints.append(np.ones(len(transforms), dtype=np.float64))
    limits.append(1.0)
    result = linprog(
        -np.ones(len(transforms), dtype=np.float64),
        A_ub=np.asarray(constraints),
        b_ub=np.asarray(limits),
        bounds=[(0.0, 1.0)] * len(transforms),
        method="highs",
    )
    if not result.success or result.fun is None:
        raise RuntimeError(f"shift-membership LP failed: {result.message}")
    return float(np.clip(1.0 + float(result.fun), 0.0, 1.0))


def token_table_from_subset(
    tokenizer: ScoreTokenizer,
    store: FrozenStore,
    indices: np.ndarray,
    *,
    familywise_delta: float,
) -> tuple[np.ndarray, TokenTable]:
    tokens = tokenizer.encode(store.features[indices])
    return tokens, build_token_table(
        tokens,
        store.target[indices],
        store.source[indices],
        token_count=tokenizer.token_count,
        familywise_delta=familywise_delta,
    )
