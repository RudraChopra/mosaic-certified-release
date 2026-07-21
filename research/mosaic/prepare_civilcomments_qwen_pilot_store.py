#!/usr/bin/env python3
"""Extract locked-role Qwen hidden states for the CivilComments pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer


DEFAULT_CSV = Path(
    "/Volumes/Backups/FARO/data/wilds/civilcomments_v1.0/all_data_with_identities.csv"
)
DEFAULT_OUTPUT = Path(
    "/Volumes/Backups/FARO/artifacts/civilcomments_qwen25_pilot"
)
MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
PROMPT_PREFIX = "Moderate this comment for toxicity:\n"
SPLIT_MAP = {"train": 0, "val": 1, "test": 2}
REPRESENTATIONS = {
    "layer14_mean": (14, "mean"),
    "layer28_mean": (28, "mean"),
    "layer28_last": (28, "last"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def balanced_sample(
    indices: np.ndarray,
    y: np.ndarray,
    s: np.ndarray,
    *,
    maximum_total: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    groups = tuple(sorted({(int(y[i]), int(s[i])) for i in indices}))
    if groups != ((0, 0), (0, 1), (1, 0), (1, 1)):
        raise ValueError(f"pilot partition has incomplete strata: {groups}")
    members = {
        group: indices[(y[indices] == group[0]) & (s[indices] == group[1])]
        for group in groups
    }
    per_group = min(min(len(values) for values in members.values()), maximum_total // 4)
    return np.sort(
        np.concatenate(
            [rng.choice(members[group], size=per_group, replace=False) for group in groups]
        ).astype(np.int64)
    )


def selected_rows(metadata: pd.DataFrame, seed: int) -> np.ndarray:
    ids = metadata["id"].to_numpy(dtype=np.int64)
    split_names = metadata["split"].astype(str).to_numpy()
    y = (metadata["toxicity"].to_numpy(dtype=np.float64) >= 0.5).astype(np.int8)
    s = (metadata["identity_any"].to_numpy(dtype=np.float64) >= 0.5).astype(np.int8)
    pilot = ids % 4 == 0
    caps = {"train": 4000, "val": 8000, "test": 12000}
    parts = []
    for offset, split_name in enumerate(("train", "val", "test")):
        available = np.flatnonzero(pilot & (split_names == split_name)).astype(np.int64)
        parts.append(
            balanced_sample(
                available,
                y,
                s,
                maximum_total=caps[split_name],
                seed=seed + offset,
            )
        )
    return np.sort(np.concatenate(parts))


def load_selected_text(csv_path: Path, rows: np.ndarray, chunksize: int) -> list[str]:
    texts: list[str | None] = [None] * len(rows)
    offset = 0
    cursor = 0
    for chunk in pd.read_csv(
        csv_path,
        usecols=["comment_text"],
        chunksize=chunksize,
        low_memory=False,
    ):
        stop = offset + len(chunk)
        while cursor < len(rows) and rows[cursor] < stop:
            local = int(rows[cursor] - offset)
            texts[cursor] = str(chunk.iloc[local]["comment_text"] or "")
            cursor += 1
        offset = stop
        if cursor == len(rows):
            break
    if cursor != len(rows) or any(value is None for value in texts):
        raise RuntimeError("failed to recover every selected comment")
    return [str(value) for value in texts]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--max-length", type=int, default=96)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--chunksize", type=int, default=16384)
    parser.add_argument("--seed", type=int, default=2027)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_root}")
    if args.max_length < 16 or args.batch_size < 1:
        raise ValueError("invalid extraction configuration")

    metadata = pd.read_csv(
        args.csv,
        usecols=["id", "split", "toxicity", "identity_any"],
        low_memory=False,
    )
    rows = selected_rows(metadata, args.seed)
    selected = metadata.iloc[rows].reset_index(drop=True)
    ids = selected["id"].to_numpy(dtype=np.int64)
    split_names = selected["split"].astype(str).to_numpy()
    y = (selected["toxicity"].to_numpy(dtype=np.float64) >= 0.5).astype(np.int8)
    s = (selected["identity_any"].to_numpy(dtype=np.float64) >= 0.5).astype(np.int8)
    split = np.asarray([SPLIT_MAP[value] for value in split_names], dtype=np.int8)
    if np.any(ids % 4 != 0):
        raise RuntimeError("non-pilot ID crossed the partition boundary")
    texts = load_selected_text(args.csv, rows, args.chunksize)

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    dtype = torch.float16 if device.type == "mps" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        revision=args.revision,
        torch_dtype=dtype,
    ).to(device)
    model.eval()
    model_revision = str(getattr(model.config, "_commit_hash", args.revision))
    layer_count = int(model.config.num_hidden_layers)
    hidden_size = int(model.config.hidden_size)
    if layer_count != 28:
        raise ValueError(f"expected 28 transformer layers, found {layer_count}")

    args.output_root.mkdir(parents=True)
    stores: dict[str, np.memmap] = {}
    for name in REPRESENTATIONS:
        directory = args.output_root / name
        directory.mkdir()
        stores[name] = np.lib.format.open_memmap(
            directory / "z.npy",
            mode="w+",
            dtype=np.float32,
            shape=(len(rows), hidden_size),
        )

    with torch.inference_mode():
        for start in tqdm(range(0, len(texts), args.batch_size), desc="Qwen hidden states"):
            batch_text = [PROMPT_PREFIX + text for text in texts[start : start + args.batch_size]]
            encoded = tokenizer(
                batch_text,
                padding=True,
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            outputs = model(
                **encoded,
                output_hidden_states=True,
                use_cache=False,
                return_dict=True,
            )
            mask = encoded["attention_mask"].unsqueeze(-1)
            last_positions = encoded["attention_mask"].sum(dim=1) - 1
            stop = min(start + args.batch_size, len(texts))
            for name, (layer, pooling) in REPRESENTATIONS.items():
                hidden = outputs.hidden_states[layer]
                if pooling == "mean":
                    pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)
                else:
                    pooled = hidden[
                        torch.arange(hidden.shape[0], device=device), last_positions
                    ]
                stores[name][start:stop] = pooled.float().cpu().numpy()

    source_sha = sha256(args.csv)
    counts = {
        f"split={int(split_code)},y={yy},s={ss}": int(
            np.sum((split == split_code) & (y == yy) & (s == ss))
        )
        for split_code in sorted(set(split.tolist()))
        for yy in (0, 1)
        for ss in (0, 1)
    }
    for name, (layer, pooling) in REPRESENTATIONS.items():
        directory = args.output_root / name
        stores[name].flush()
        del stores[name]
        np.save(directory / "y.npy", y)
        np.save(directory / "s.npy", s)
        np.save(directory / "split.npy", split)
        np.save(directory / "ids.npy", ids)
        np.save(directory / "source_rows.npy", rows)
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset": "CivilComments-WILDS-Qwen2.5-pilot",
            "n_examples": len(rows),
            "dimension": hidden_size,
            "arrays": {"z": "z.npy", "y": "y.npy", "s": "s.npy", "split": "split.npy"},
            "auxiliary_arrays": {"ids": "ids.npy", "source_rows": "source_rows.npy"},
            "source_csv_sha256": source_sha,
            "source_concept": "identity_any >= 0.5 (identity mention, not author identity)",
            "target": "toxicity >= 0.5",
            "pilot_partition": "integer dataset id modulo 4 equals 0",
            "confirmation_partition": "integer dataset id modulo 4 is nonzero",
            "model": args.model,
            "model_revision": model_revision,
            "model_layers": layer_count,
            "representation": name,
            "hidden_layer": layer,
            "pooling": pooling,
            "prompt_prefix": PROMPT_PREFIX,
            "max_length": args.max_length,
            "dtype": "float32",
            "device": device.type,
            "selection_seed": args.seed,
            "group_counts": counts,
        }
        (directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "output_root": str(args.output_root),
                "rows": len(rows),
                "model_revision": model_revision,
                "device": device.type,
                "group_counts": counts,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
