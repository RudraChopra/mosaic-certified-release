from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
MOSAIC = ROOT / "research/mosaic"
if str(MOSAIC) not in sys.path:
    sys.path.insert(0, str(MOSAIC))

from prepare_camelyon_streamed_confirmation_store import selected_rows


def test_streamed_selection_is_balanced_deterministic_and_disjoint() -> None:
    rows = []
    image_id = 0
    for split in ("train", "validation"):
        for label in (0, 1):
            for source, center in ((0, 0), (1, 3)):
                for offset in range(12):
                    rows.append(
                        {
                            "id": f"camelyon17_{image_id:06d}",
                            "split": split,
                            "y": label,
                            "center": center,
                            "patient": offset,
                            "node": 0,
                            "x_coord": offset,
                            "y_coord": offset,
                            "image_id": np.uint32(image_id),
                            "source": np.int8(source),
                        }
                    )
                    image_id += 1
    frame = pd.DataFrame(rows)
    first = selected_rows(
        frame,
        train_per_stratum=7,
        validation_per_stratum=5,
        seed=20270727,
    )
    second = selected_rows(
        frame,
        train_per_stratum=7,
        validation_per_stratum=5,
        seed=20270727,
    )
    assert first["image_id"].tolist() == second["image_id"].tolist()
    assert first["image_id"].is_unique
    counts = first.groupby(["split", "y", "source"]).size().to_dict()
    assert set(counts.values()) == {5, 7}
    assert len(first) == 48
