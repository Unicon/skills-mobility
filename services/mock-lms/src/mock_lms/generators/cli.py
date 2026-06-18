"""CLI: assemble the catalog and capture it as the mock's fixture input.

    uv run mock-lms-generate                       # regenerate committed fixture (seed 42)
    uv run mock-lms-generate --csv-dir path/ --out-dir generated-fixtures

Reads the roster CSVs (``course_sections.csv``, ``users.csv``, ``enrollments.csv``)
from ``--csv-dir`` (default: the gitignored ``services/mock-lms/seed-data/``) and
writes ``catalog.json``. The default ``--out-dir`` is the packaged ``fixtures/``
(the committed, canonical snapshot). Point ``--out-dir`` at the gitignored
``generated-fixtures/`` to experiment without touching the committed demo data;
run the service against them with ``MOCK_LMS_FIXTURES_DIR=...``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mock_lms.generators.catalog import generate

_DEFAULT_OUT = Path(__file__).resolve().parents[1] / "fixtures"


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble + capture the Mock LMS fixture.")
    parser.add_argument("--seed", type=int, default=42, help="deterministic seed (default: 42)")
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=None,
        help="roster CSV dir (default: services/mock-lms/seed-data/)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_DEFAULT_OUT,
        help="where to write catalog.json (default: committed fixtures/)",
    )
    args = parser.parse_args()

    result = generate(seed=args.seed, csv_dir=args.csv_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_dir / "catalog.json", result.catalog.model_dump(mode="json"))

    catalog = result.catalog
    print(
        f"Wrote {args.out_dir}/catalog.json "
        f"({len(catalog.courses)} course(s), {len(catalog.users)} learner(s), "
        f"{len(catalog.assignments)} assignment(s), {len(catalog.badges)} badge(s), "
        f"{len(catalog.actions)} action(s)) [seed={args.seed}]"
    )


if __name__ == "__main__":
    main()
