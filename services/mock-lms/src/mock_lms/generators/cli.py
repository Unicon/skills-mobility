"""CLI: generate a dataset and capture it as the mock's fixture input.

    uv run mock-lms-generate                       # regenerate committed fixtures (seed 42)
    uv run mock-lms-generate --learners 5 --courses 2 --out-dir generated-fixtures

The default out-dir is the packaged ``fixtures/`` (the committed, canonical
snapshot). Point ``--out-dir`` at the gitignored ``generated-fixtures/`` to
experiment with larger sets without touching the committed demo data; run the
service against them with ``MOCK_LMS_FIXTURES_DIR=...``.
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
    parser = argparse.ArgumentParser(description="Generate + capture Mock LMS fixtures.")
    parser.add_argument("--seed", type=int, default=42, help="deterministic seed (default: 42)")
    parser.add_argument("--learners", type=int, default=1, help="learners to generate (default: 1)")
    parser.add_argument("--courses", type=int, default=1, help="courses to generate (default: 1)")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_DEFAULT_OUT,
        help="where to write catalog.json + scenarios.json (default: committed fixtures/)",
    )
    args = parser.parse_args()

    result = generate(seed=args.seed, learners=args.learners, courses=args.courses)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    _write_json(args.out_dir / "catalog.json", result.catalog.model_dump(mode="json"))
    _write_json(
        args.out_dir / "scenarios.json",
        [s.model_dump(mode="json") for s in result.scenarios],
    )

    catalog = result.catalog
    print(
        f"Wrote {args.out_dir}/catalog.json "
        f"({len(catalog.courses)} course(s), {len(catalog.students)} learner(s), "
        f"{len(catalog.submissions)} submission(s)) "
        f"and scenarios.json ({len(result.scenarios)} scenario(s)) "
        f"[seed={args.seed}]"
    )


if __name__ == "__main__":
    main()
