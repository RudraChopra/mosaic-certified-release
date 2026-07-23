#!/usr/bin/env python3
"""Build frozen features for the natural CIFAR/ImageNet origin shift in CINIC-10."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp

import numpy as np
import torch
import torchvision.transforms.functional as tvf
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision.models import ResNet18_Weights, resnet18


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = Path(
    "/Users/rudrachopra/Documents/Science Fair/data/CINIC-10"
)
DEFAULT_OUTPUT = Path(
    "/Users/rudrachopra/Documents/Science Fair/data/"
    "cinic10_natural_origin_numpy_store"
)
CLASS_TO_TARGET = {
    "automobile": 0,
    "truck": 0,
    "cat": 1,
    "dog": 1,
}
SPLIT_CODES = {"train": 0, "valid": 1, "test": 2}


@dataclass(frozen=True)
class Record:
    path: Path
    target: int
    source: int
    split: int
    class_name: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_origin(path: Path) -> int:
    """Return zero for CIFAR-10 origin and one for ImageNet origin."""

    return 0 if path.name.startswith("cifar10-") else 1


def select_records(
    root: Path,
    *,
    per_class_source_split: int,
    seed: int,
) -> list[Record]:
    rng = np.random.default_rng(seed)
    records: list[Record] = []
    for split_name, split_code in SPLIT_CODES.items():
        for class_name, target in CLASS_TO_TARGET.items():
            paths = sorted((root / split_name / class_name).glob("*.png"))
            if not paths:
                raise FileNotFoundError(
                    f"no images found in {root / split_name / class_name}"
                )
            for source in (0, 1):
                candidates = [
                    path for path in paths if image_origin(path) == source
                ]
                if len(candidates) < per_class_source_split:
                    raise ValueError(
                        f"{split_name}/{class_name}/source={source} has "
                        f"{len(candidates)} images"
                    )
                order = rng.permutation(len(candidates))[
                    :per_class_source_split
                ]
                records.extend(
                    Record(
                        path=candidates[int(index)],
                        target=target,
                        source=source,
                        split=split_code,
                        class_name=class_name,
                    )
                    for index in order
                )
    records.sort(
        key=lambda row: (
            row.split,
            row.target,
            row.source,
            row.class_name,
            row.path.name,
        )
    )
    return records


class ImageRecords(Dataset[tuple[torch.Tensor, int]]):
    def __init__(self, records: list[Record]) -> None:
        self.records = records

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        image = np.asarray(
            Image.open(self.records[index].path).convert("RGB")
        )
        tensor = (
            torch.from_numpy(image.copy()).permute(2, 0, 1).float() / 255.0
        )
        return tensor, index


def preprocess(batch: torch.Tensor) -> torch.Tensor:
    batch = tvf.resize(batch, [256], antialias=True)
    batch = tvf.center_crop(batch, [224, 224])
    mean = torch.as_tensor(
        [0.485, 0.456, 0.406], device=batch.device
    ).view(1, 3, 1, 1)
    std = torch.as_tensor(
        [0.229, 0.224, 0.225], device=batch.device
    ).view(1, 3, 1, 1)
    return (batch - mean) / std


def extract_features(
    records: list[Record],
    *,
    batch_size: int,
    device: torch.device,
) -> np.ndarray:
    model = resnet18(weights=ResNet18_Weights.DEFAULT)
    model.fc = torch.nn.Identity()
    model.eval().to(device)
    loader = DataLoader(
        ImageRecords(records),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )
    features = np.empty((len(records), 512), dtype=np.float32)
    with torch.inference_mode():
        for batch, indices in loader:
            values = model(preprocess(batch.to(device))).cpu().numpy()
            features[indices.numpy()] = values.astype(
                np.float32, copy=False
            )
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--per-class-source-split", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20270723)
    parser.add_argument("--batch-size", type=int, default=192)
    parser.add_argument("--source-archive", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        if not args.force:
            raise FileExistsError(f"output exists: {args.output}")
        shutil.rmtree(args.output)
    records = select_records(
        args.data,
        per_class_source_split=args.per_class_source_split,
        seed=args.seed,
    )
    device = torch.device(
        "mps" if torch.backends.mps.is_available() else "cpu"
    )
    features = extract_features(
        records, batch_size=args.batch_size, device=device
    )
    arrays = {
        "z": features,
        "y": np.asarray([row.target for row in records], dtype=np.int16),
        "s": np.asarray([row.source for row in records], dtype=np.int16),
        "split": np.asarray([row.split for row in records], dtype=np.int16),
    }
    temporary = Path(
        mkdtemp(prefix="cinic10_natural_", dir=args.output.parent)
    )
    array_hashes = {}
    for name, values in arrays.items():
        path = temporary / f"{name}.npy"
        np.save(path, values)
        array_hashes[name] = sha256(path)
    counts: dict[str, int] = {}
    for row in records:
        key = f"split={row.split},target={row.target},source={row.source}"
        counts[key] = counts.get(key, 0) + 1
    archive_receipt = None
    if args.source_archive is not None:
        archive_receipt = {
            "path": str(args.source_archive),
            "sha256": sha256(args.source_archive),
            "bytes": args.source_archive.stat().st_size,
        }
    manifest = {
        "name": "MOSAIC CINIC-10 natural origin-shift feature store",
        "format": "trace_embedding_store_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_examples": len(records),
        "feature_count": 512,
        "arrays": {name: f"{name}.npy" for name in arrays},
        "array_sha256": array_hashes,
        "split_codes": SPLIT_CODES,
        "stratum_counts": counts,
        "task": "automobile-or-truck versus cat-or-dog",
        "source": "CIFAR-10 versus ImageNet image origin",
        "class_to_target": CLASS_TO_TARGET,
        "selection": {
            "per_class_source_split": args.per_class_source_split,
            "seed": args.seed,
        },
        "encoder": (
            "torchvision ResNet18_Weights.DEFAULT, penultimate "
            "512-dimensional activation"
        ),
        "device": str(device),
        "source_archive": archive_receipt,
        "builder_sha256": sha256(Path(__file__)),
        "claim_boundary": (
            "CINIC-10 contains naturally collected CIFAR-10 and ImageNet "
            "images with file-level origin provenance. The frozen encoder "
            "uses ImageNet pretrained weights; this study evaluates release "
            "certification, not out-of-sample ImageNet recognition."
        ),
    }
    (temporary / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "examples": len(records),
                "device": str(device),
                "manifest_sha256": sha256(
                    args.output / "manifest.json"
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

