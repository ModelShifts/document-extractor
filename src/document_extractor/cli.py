"""Command-line interface.

    document-extractor extract FILE --schema schemas/invoice.yaml
    document-extractor ask FILE "When does the notice period start?"
    document-extractor batch DIR --schema invoice --out results.csv
    document-extractor serve
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from . import __version__
from .config import Settings
from .pdf import NoTextLayerError


def _settings() -> Settings:
    settings = Settings.from_env()
    settings.validate()
    return settings


def cmd_extract(args: argparse.Namespace) -> int:
    from .pipeline import run_extract

    settings = _settings()
    result = run_extract(args.file, args.schema, settings)
    text = json.dumps(result.to_json_dict(), indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from .pipeline import run_ask

    answer = run_ask(args.file, args.question, _settings())
    if args.json:
        print(json.dumps(answer.model_dump(), indent=2, ensure_ascii=False))
        return 0
    print(answer.answer)
    for c in answer.citations:
        snippet = " ".join(c.text.split())
        print(f"  [{c.n}] page {c.page}, box {[round(v, 1) for v in c.bbox]}: {snippet[:160]}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    from .pipeline import run_extract
    from .schema import load_schema

    settings = _settings()
    files = sorted(Path(args.dir).glob(args.glob))
    if not files:
        print(f"no PDF files in {args.dir}", file=sys.stderr)
        return 1
    field_names = load_schema(args.schema).field_names
    results, rows = [], []
    for f in files:
        t0 = time.time()
        try:
            r = run_extract(f, args.schema, settings)
        except NoTextLayerError as exc:
            print(f"skip {f.name}: {exc}", file=sys.stderr)
            rows.append({"file": f.name, "error": str(exc)})
            continue
        print(f"{f.name}: done in {time.time() - t0:.1f}s", file=sys.stderr)
        results.append(r.to_json_dict())
        row = {"file": f.name, "error": ""}
        for name in field_names:
            fv = r.fields[name]
            row[name] = "" if fv.value is None else fv.value
            row[f"{name}_page"] = fv.source.page if fv.source else ""
        rows.append(row)
    out = Path(args.out)
    if out.suffix.lower() == ".csv":
        cols = ["file"] + [c for n in field_names for c in (n, f"{n}_page")] + ["error"]
        with out.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    else:
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out} ({len(results)} of {len(files)} files extracted)", file=sys.stderr)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .webapp import launch

    launch(host=args.host, port=args.port, share=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="document-extractor", description="Turn PDF invoices and contracts into "
                                "structured fields, each linked to its source.")
    p.add_argument("--version", action="version", version=f"document-extractor {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("extract", help="extract schema fields from one PDF as JSON")
    e.add_argument("file")
    e.add_argument("--schema", required=True, help="schema YAML path, or 'invoice' / 'contract'")
    e.add_argument("--out", help="write JSON here instead of stdout")
    e.set_defaults(func=cmd_extract)

    a = sub.add_parser("ask", help="ask a question about one PDF; the answer cites passages")
    a.add_argument("file")
    a.add_argument("question")
    a.add_argument("--json", action="store_true", help="print the full answer as JSON")
    a.set_defaults(func=cmd_ask)

    b = sub.add_parser("batch", help="extract every PDF in a folder to one CSV or JSON file")
    b.add_argument("dir")
    b.add_argument("--schema", required=True)
    b.add_argument("--out", required=True, help="results.csv or results.json")
    b.add_argument("--glob", default="*.pdf", help="which files to read, e.g. 'invoice-*.pdf' (default: *.pdf)")
    b.set_defaults(func=cmd_batch)

    s = sub.add_parser("serve", help="start the local web demo (Gradio)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=7860)
    s.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (NoTextLayerError, ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
