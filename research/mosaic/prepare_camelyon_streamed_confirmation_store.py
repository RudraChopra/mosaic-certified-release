#!/usr/bin/env python3
"""Build a locked Camelyon17 feature store from pinned remote Parquet shards."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA = Path(
    "/Users/rudrachopra/Documents/Science Fair/research/artifacts/"
    "camelyon17_wilds_metadata 2.csv"
)
DEFAULT_OUTPUT = ROOT / "research/data/camelyon17_streamed_confirmation"
DEFAULT_PREREG = (
    ROOT
    / "research/mosaic/"
    "prereg_mosaic_camelyon_streamed_confirmation_v1.json"
)
SOURCE_ZERO_CENTERS = frozenset({0})
SOURCE_ONE_CENTERS = frozenset({3, 4})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_array(values: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(values).tobytes()
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def load_metadata(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(
        path,
        usecols=[
            "id",
            "split",
            "y",
            "center",
            "patient",
            "node",
            "x_coord",
            "y_coord",
        ],
        low_memory=False,
    )
    frame["image_id"] = (
        frame["id"].str.rsplit("_", n=1).str[-1].astype(np.uint32)
    )
    frame["source"] = np.where(
        frame["center"].isin(SOURCE_ZERO_CENTERS),
        0,
        np.where(frame["center"].isin(SOURCE_ONE_CENTERS), 1, -1),
    ).astype(np.int8)
    return frame


def selected_rows(
    frame: pd.DataFrame,
    *,
    train_per_stratum: int,
    validation_per_stratum: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    chosen: list[np.ndarray] = []
    for split_name, cap in (
        ("train", train_per_stratum),
        ("validation", validation_per_stratum),
    ):
        for label in (0, 1):
            for source in (0, 1):
                rows = frame.index[
                    (frame["split"] == split_name)
                    & (frame["y"] == label)
                    & (frame["source"] == source)
                ].to_numpy(dtype=np.int64)
                if len(rows) < cap:
                    raise RuntimeError(
                        f"{split_name},y={label},s={source} has "
                        f"{len(rows)} rows; {cap} required"
                    )
                chosen.append(
                    rng.choice(rows, size=cap, replace=False)
                )
    selected = frame.loc[np.sort(np.concatenate(chosen))].copy()
    if selected["image_id"].duplicated().any():
        raise RuntimeError("selected Camelyon image IDs are not unique")
    return selected.reset_index(drop=True)


def validate_lock(
    path: Path,
    metadata_path: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if sidecar.read_text(encoding="utf-8").split()[0] != sha256(path):
        raise ValueError("Camelyon streamed lock sidecar mismatch")
    prereg = load_json(path)
    if prereg.get("status") != "locked_before_streamed_model_and_outcomes":
        raise RuntimeError("Camelyon streamed preregistration is not locked")
    if metadata_path.stat().st_size != prereg["metadata"]["bytes"]:
        raise RuntimeError("Camelyon metadata size differs from the lock")
    if sha256(metadata_path) != prereg["metadata"]["sha256"]:
        raise RuntimeError("Camelyon metadata hash differs from the lock")
    for relative, expected in prereg["code_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"locked source mismatch: {relative}")
    for local in (path, sidecar):
        relative = local.relative_to(ROOT)
        committed = subprocess.run(
            ["git", "show", f"HEAD:{relative.as_posix()}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if committed != local.read_bytes():
            raise RuntimeError(f"{relative} is not the committed lock")

    frame = load_metadata(metadata_path)
    design = prereg["streamed_store"]
    selected = selected_rows(
        frame,
        train_per_stratum=int(design["train_rows_per_stratum"]),
        validation_per_stratum=int(
            design["validation_rows_per_stratum"]
        ),
        seed=int(design["selection_seed"]),
    )
    ids = selected["image_id"].to_numpy(dtype=np.uint32)
    if sha256_array(ids) != design["selected_image_ids_sha256"]:
        raise RuntimeError("Camelyon selected image IDs differ from the lock")
    return prereg, selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--batch-size", type=int, default=128)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prereg, selected = validate_lock(args.prereg, args.metadata)
    manifest_path = args.output / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"completed store already exists: {args.output}")

    import duckdb
    import torch
    from PIL import Image
    from torchvision.models import ResNet18_Weights, resnet18

    device = torch.device(
        "mps" if torch.backends.mps.is_available() else "cpu"
    )
    weights = ResNet18_Weights.DEFAULT
    model = resnet18(weights=weights)
    model.fc = torch.nn.Identity()
    model.to(device)
    model.eval()
    transform = weights.transforms()

    args.output.mkdir(parents=True, exist_ok=True)
    ids = selected["image_id"].to_numpy(dtype=np.uint32)
    target = selected["y"].to_numpy(dtype=np.int8)
    centers = selected["center"].to_numpy(dtype=np.int8)
    source = selected["source"].to_numpy(dtype=np.int8)
    split = np.where(
        selected["split"].to_numpy() == "train", 0, 1
    ).astype(np.int8)
    positions = {int(identifier): index for index, identifier in enumerate(ids)}
    features = np.lib.format.open_memmap(
        args.output / "z.npy",
        mode="w+",
        dtype=np.float32,
        shape=(len(selected), 512),
    )
    completed = np.zeros(len(selected), dtype=bool)

    repository = prereg["remote_dataset"]
    revision = repository["revision"]
    base = (
        "https://huggingface.co/datasets/"
        f"{repository['repository']}/resolve/{revision}/"
    )
    connection = duckdb.connect()
    connection.execute("INSTALL httpfs")
    connection.execute("LOAD httpfs")
    connection.execute("CREATE TEMP TABLE wanted(image_id UINTEGER)")
    connection.executemany(
        "INSERT INTO wanted VALUES (?)",
        [(int(identifier),) for identifier in ids],
    )

    images: list[torch.Tensor] = []
    output_positions: list[int] = []

    def flush() -> None:
        if not images:
            return
        batch = torch.stack(images).to(device)
        with torch.inference_mode():
            encoded = model(batch).float().cpu().numpy()
        features[np.asarray(output_positions, dtype=np.int64)] = encoded
        completed[np.asarray(output_positions, dtype=np.int64)] = True
        images.clear()
        output_positions.clear()

    fields = (
        "p.image.bytes, p.label, p.center, p.image_id, p.patient, "
        "p.node, p.x_coord, p.y_coord"
    )
    for relative in repository["parquet_files"]:
        url = base + relative
        cursor = connection.execute(
            f"SELECT {fields} FROM read_parquet(?) p "
            "SEMI JOIN wanted w USING (image_id)",
            [url],
        )
        while rows := cursor.fetchmany(args.batch_size):
            for (
                image_bytes,
                label,
                center,
                image_id,
                patient,
                node,
                x_coord,
                y_coord,
            ) in rows:
                position = positions[int(image_id)]
                expected = selected.iloc[position]
                observed = (
                    int(label),
                    int(center),
                    int(patient),
                    int(node),
                    int(x_coord),
                    int(y_coord),
                )
                locked = (
                    int(expected["y"]),
                    int(expected["center"]),
                    int(expected["patient"]),
                    int(expected["node"]),
                    int(expected["x_coord"]),
                    int(expected["y_coord"]),
                )
                if observed != locked:
                    raise RuntimeError(
                        f"remote metadata mismatch for image {image_id}: "
                        f"{observed} != {locked}"
                    )
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                images.append(transform(image))
                output_positions.append(position)
                if len(images) >= args.batch_size:
                    flush()
            features.flush()
    flush()
    features.flush()
    del features
    if not np.all(completed):
        missing = ids[~completed][:10].tolist()
        raise RuntimeError(f"remote mirror omitted selected IDs: {missing}")

    np.save(args.output / "y.npy", target)
    np.save(args.output / "s.npy", source)
    np.save(args.output / "split.npy", split)
    np.save(args.output / "g.npy", centers)
    np.save(args.output / "ids.npy", ids)
    model_path = Path(torch.hub.get_dir()) / "checkpoints" / Path(
        weights.url
    ).name
    manifest = {
        "name": "MOSAIC streamed Camelyon17 ResNet18 confirmation store",
        "n_examples": len(selected),
        "dimension": 512,
        "arrays": {
            "z": "z.npy",
            "y": "y.npy",
            "s": "s.npy",
            "split": "split.npy",
            "g": "g.npy",
        },
        "ids": "ids.npy",
        "preregistration_sha256": sha256(args.prereg),
        "metadata_sha256": prereg["metadata"]["sha256"],
        "selected_image_ids_sha256": sha256_array(ids),
        "remote_dataset": repository,
        "model": "torchvision ResNet18 ImageNet-1K V1 penultimate",
        "model_weights_url": weights.url,
        "model_weights_sha256": sha256(model_path),
        "preprocessing": str(transform),
        "device": device.type,
        "split_counts": {
            "train": int(np.sum(split == 0)),
            "validation": int(np.sum(split == 1)),
        },
        "source_label_counts": {
            f"split={role},y={label},s={group}": int(
                np.sum(
                    (split == role)
                    & (target == label)
                    & (source == group)
                )
            )
            for role in (0, 1)
            for label in (0, 1)
            for group in (0, 1)
        },
        "claim_boundary": prereg["claim_boundary"],
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), **manifest}, indent=2))


if __name__ == "__main__":
    main()
