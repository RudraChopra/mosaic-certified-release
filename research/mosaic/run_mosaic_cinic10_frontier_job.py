#!/usr/bin/env python3
"""Run one MOSAIC frontier job on the frozen CINIC-10 origin store."""

from __future__ import annotations

import os
from pathlib import Path

import run_mosaic_bridge_frontier as frontier


STORE = Path(
    os.environ.get(
        "MOSAIC_CINIC10_STORE",
        "/Users/rudrachopra/Documents/Science Fair/data/"
        "cinic10_natural_origin_numpy_store",
    )
)
DATASET = "CINIC10-Natural-Origin"


def main() -> None:
    frontier.DATASETS[DATASET] = {
        "path": str(STORE),
        "target_mode": "binary",
    }
    frontier.main()


if __name__ == "__main__":
    main()
