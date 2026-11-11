"""Compare extraction results with the ground truth in ``samples/*.truth.json``.

    python scripts/evaluate.py                    # run the configured backend on every sample
    python scripts/evaluate.py --out eval.json    # also save the raw results

A field counts as correct when the typed value matches the truth (strings are
compared case-insensitively with spaces and trailing punctuation ignored;
numbers within 0.005). "Sourced" counts correct values that also carry a source
box whose text matches the value.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from document_extractor.config import Settings
from document_extractor.grounding import _key, variants
from document_extractor.pipeline import run_extract
from document_extractor.schema import load_schema

ROOT = Path(__file__).resolve().parent.parent


def same(pred, truth, ftype: str) -> bool:
    if pred is None or truth is None:
        return pred is truth
    if ftype == "number":
        return abs(float(pred) - float(truth)) < 0.005
    if ftype == "integer":
        return int(pred) == int(truth)
    clean = lambda s: re.sub(r"\s+", " ", str(s)).strip(" .,;:").lower()  # noqa: E731
    return clean(pred) == clean(truth)


def source_matches(fv, ftype: str) -> bool:
    """True when the source box text spells the value (or contains it)."""
    if fv.source is None:
        return False
    got = _key(fv.source.text.split())
    return any(_key(v.split()) and _key(v.split()) in got for v in variants(fv.raw, fv.value, ftype))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default=str(ROOT / "samples"))
    ap.add_argument("--out")
    args = ap.parse_args()
    settings = Settings.from_env()
    settings.validate()
    rows, raw = [], []
    tot_ok = tot_n = tot_src = 0
    for truth_file in sorted(Path(args.samples).glob("*.truth.json")):
        truth = json.loads(truth_file.read_text())
        pdf = truth_file.with_name(truth["file"])
        schema = load_schema(truth["schema"])
        t0 = time.time()
        try:
            result = run_extract(pdf, truth["schema"], settings)
        except Exception as exc:  # report and keep going
            rows.append((pdf.name, 0, len(schema.fields), 0, 0.0, f"error: {exc}"))
            tot_n += len(schema.fields)
            continue
        dt = time.time() - t0
        raw.append(result.to_json_dict())
        ok = src = 0
        misses = []
        for spec in schema.fields:
            fv = result.fields[spec.name]
            if same(fv.value, truth["fields"][spec.name], spec.type):
                ok += 1
                if source_matches(fv, spec.type):
                    src += 1
            else:
                misses.append(f"{spec.name}={fv.value!r} (want {truth['fields'][spec.name]!r})")
        rows.append((pdf.name, ok, len(schema.fields), src, dt, "; ".join(misses)))
        tot_ok, tot_n, tot_src = tot_ok + ok, tot_n + len(schema.fields), tot_src + src
        print(f"{pdf.name}: {ok}/{len(schema.fields)} correct, {src} sourced, {dt:.1f}s", file=sys.stderr)

    print(f"\nBackend: {settings.backend}, model: {settings.model_name}\n")
    print("| Sample | Correct | Sourced | Time (s) | Misses |")
    print("|---|---|---|---|---|")
    for name, ok, n, src, dt, miss in rows:
        print(f"| {name} | {ok}/{n} | {src}/{ok} | {dt:.1f} | {miss or '-'} |")
    print(f"| **All** | **{tot_ok}/{tot_n} ({100 * tot_ok / max(tot_n, 1):.0f}%)** | {tot_src}/{tot_ok} | | |")
    if args.out:
        Path(args.out).write_text(json.dumps(raw, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
