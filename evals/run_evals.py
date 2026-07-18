"""Deterministic DeepEval evaluation harness for the two LLM Decision Services.

Run:
    uv run --with deepeval --with httpx python evals/run_evals.py
    uv run --with deepeval --with httpx python evals/run_evals.py --gate-only
    uv run --with deepeval --with httpx python evals/run_evals.py --dt-only
    uv run --with deepeval --with httpx python evals/run_evals.py \
        --dt-url http://localhost:8130 --wa-url http://localhost:8140

ADR-0013/0021: deterministic custom metrics only — no LLM judge, no Confident AI.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

# --- Telemetry opt-out must happen before any deepeval import ---
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
os.environ["DEEPEVAL_RESULTS_FOLDER"] = ""  # disable local result writes

import httpx  # noqa: E402  (after env setup)
from deepeval.metrics import BaseMetric  # noqa: E402
from deepeval.test_case import LLMTestCase  # noqa: E402

_CORPUS_DIR = Path(__file__).parent / "corpus"
_SCORECARD_PATH = Path(__file__).parent / "last-scorecard.md"


# ---------------------------------------------------------------------------
# Custom deterministic metrics (ADR-0013/0021 — no LLM judge)
# ---------------------------------------------------------------------------


class ExactMatchMetric(BaseMetric):
    """Gate service: actual decision string must equal the expected label."""

    def __init__(self) -> None:
        self.threshold = 1.0
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "ExactMatch"

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        actual = (test_case.actual_output or "").strip()
        expected = (test_case.expected_output or "").strip()
        self.success = actual == expected
        self.score = 1.0 if self.success else 0.0
        self.reason = "match" if self.success else f"got '{actual}', expected '{expected}'"
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)


class SetMatchMetric(BaseMetric):
    """Delivery-targets service: set(actual_targets) must equal set(expected_targets)."""

    def __init__(self) -> None:
        self.threshold = 1.0
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "SetMatch"

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        try:
            actual_set = set(json.loads(test_case.actual_output or "[]"))
        except (json.JSONDecodeError, TypeError):
            actual_set = set()
        try:
            expected_set = set(json.loads(test_case.expected_output or "[]"))
        except (json.JSONDecodeError, TypeError):
            expected_set = set()
        self.success = actual_set == expected_set
        self.score = 1.0 if self.success else 0.0
        if self.success:
            self.reason = f"match: {sorted(actual_set)}"
        else:
            extra = actual_set - expected_set
            missing = expected_set - actual_set
            parts = []
            if extra:
                parts.append(f"unexpected={sorted(extra)}")
            if missing:
                parts.append(f"missing={sorted(missing)}")
            self.reason = "; ".join(parts)
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)


# ---------------------------------------------------------------------------
# Service callers
# ---------------------------------------------------------------------------


def _fresh_ids() -> tuple[str, str]:
    return f"eval-exec-{uuid.uuid4().hex[:8]}", f"eval-evt-{uuid.uuid4().hex[:8]}"


def call_gate(client: httpx.Client, wa_url: str, scenario: dict[str, Any]) -> dict[str, Any]:
    """POST /pre-target-gate and return the parsed JSON body (or an error dict)."""
    execution_id, event_id = _fresh_ids()
    payload = {
        "execution_id": execution_id,
        "event_id": event_id,
        "event_type": scenario["event_type"],
        "event": scenario["event"],
        "context_bundle": scenario["context_bundle"],
    }
    try:
        resp = client.post(f"{wa_url}/pre-target-gate", json=payload, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        return {"_error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
    except Exception as exc:  # noqa: BLE001
        return {"_error": str(exc)}


def call_dt(client: httpx.Client, dt_url: str, scenario: dict[str, Any]) -> dict[str, Any]:
    """POST /select-delivery-targets and return the parsed JSON body (or an error dict)."""
    execution_id, event_id = _fresh_ids()
    payload = {
        "execution_id": execution_id,
        "event_id": event_id,
        "event_type": scenario["event_type"],
        "source_system": scenario["source_system"],
        "learner_context": scenario["learner_context"],
    }
    try:
        resp = client.post(f"{dt_url}/select-delivery-targets", json=payload, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        return {"_error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
    except Exception as exc:  # noqa: BLE001
        return {"_error": str(exc)}


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


_CHECK = "✓"
_CROSS = "✗"


def run_gate_evals(
    client: httpx.Client, wa_url: str, scenarios: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    results = []
    for scenario in scenarios:
        sid = scenario["corpus_scenario_id"]
        expected = scenario["expected_decision"]
        raw = call_gate(client, wa_url, scenario)

        if "_error" in raw:
            results.append(
                {
                    "scenario_id": sid,
                    "expected": expected,
                    "actual": "ERROR",
                    "confidence": None,
                    "passed": False,
                    "reason": raw["_error"],
                    "error": True,
                }
            )
            continue

        actual_decision = raw.get("decision") or ""
        confidence = raw.get("confidence")

        metric = ExactMatchMetric()
        tc = LLMTestCase(
            input=json.dumps({"event_type": scenario["event_type"]}),
            actual_output=actual_decision,
            expected_output=expected,
        )
        metric.measure(tc)

        results.append(
            {
                "scenario_id": sid,
                "expected": expected,
                "actual": actual_decision,
                "confidence": confidence,
                "passed": metric.is_successful(),
                "reason": metric.reason,
                "error": False,
            }
        )
    return results


def run_dt_evals(
    client: httpx.Client, dt_url: str, scenarios: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    results = []
    for scenario in scenarios:
        sid = scenario["corpus_scenario_id"]
        expected = scenario["expected_targets"]
        raw = call_dt(client, dt_url, scenario)

        if "_error" in raw:
            results.append(
                {
                    "scenario_id": sid,
                    "expected": expected,
                    "actual": "ERROR",
                    "passed": False,
                    "reason": raw["_error"],
                    "error": True,
                }
            )
            continue

        actual_targets = raw.get("selected_targets", [])

        metric = SetMatchMetric()
        tc = LLMTestCase(
            input=json.dumps({"event_type": scenario["event_type"]}),
            actual_output=json.dumps(actual_targets),
            expected_output=json.dumps(expected),
        )
        metric.measure(tc)

        results.append(
            {
                "scenario_id": sid,
                "expected": expected,
                "actual": actual_targets,
                "passed": metric.is_successful(),
                "reason": metric.reason,
                "error": False,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Scorecard rendering
# ---------------------------------------------------------------------------


def _gate_table(results: list[dict[str, Any]]) -> str:
    col_w = max(len(r["scenario_id"]) for r in results) + 2
    dec_w = max(max(len(r["expected"]), len(str(r["actual"]))) for r in results) + 2
    header = (
        f"{'scenario_id':<{col_w}} {'expected':<{dec_w}} {'actual':<{dec_w}} "
        f"{'ok':>4}  {'confidence':>10}"
    )
    sep = "-" * len(header)
    rows = [header, sep]
    for r in results:
        mark = _CHECK if r["passed"] else _CROSS
        conf = f"{r['confidence']:.2f}" if r["confidence"] is not None else "  n/a"
        rows.append(
            f"{r['scenario_id']:<{col_w}} {r['expected']:<{dec_w}} "
            f"{str(r['actual']):<{dec_w}} {mark:>4}  {conf:>10}"
        )
    return "\n".join(rows)


def _dt_table(results: list[dict[str, Any]]) -> str:
    col_w = max(len(r["scenario_id"]) for r in results) + 2
    tgt_w = max(
        max(
            len(json.dumps(r["expected"])),
            len(json.dumps(r["actual"]) if not r["error"] else "ERROR"),
        )
        for r in results
    ) + 2
    header = f"{'scenario_id':<{col_w}} {'expected':<{tgt_w}} {'actual':<{tgt_w}} {'ok':>4}"
    sep = "-" * len(header)
    rows = [header, sep]
    for r in results:
        mark = _CHECK if r["passed"] else _CROSS
        exp_str = json.dumps(r["expected"])
        act_str = json.dumps(r["actual"]) if not r["error"] else "ERROR"
        rows.append(f"{r['scenario_id']:<{col_w}} {exp_str:<{tgt_w}} {act_str:<{tgt_w}} {mark:>4}")
    return "\n".join(rows)


def render_scorecard(
    gate_results: list[dict[str, Any]] | None,
    dt_results: list[dict[str, Any]] | None,
) -> str:
    lines: list[str] = ["# Eval Scorecard", ""]

    if gate_results is not None:
        passed = sum(1 for r in gate_results if r["passed"])
        total = len(gate_results)
        pct = int(100 * passed / total) if total else 0
        lines += [
            "## Workflow Actions Gate",
            "",
            _gate_table(gate_results),
            "",
            f"**gate: {passed}/{total} = {pct}%**",
            "",
        ]

    if dt_results is not None:
        passed = sum(1 for r in dt_results if r["passed"])
        total = len(dt_results)
        pct = int(100 * passed / total) if total else 0
        lines += [
            "## Delivery Targets (provisional labels — routing use case open, #75)",
            "",
            _dt_table(dt_results),
            "",
            f"**delivery_targets: {passed}/{total} = {pct}% (provisional labels)**",
            "",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run deterministic DeepEval evals against the two LLM Decision Services."
    )
    parser.add_argument("--dt-url", default="http://localhost:8130", help="Delivery Targets URL")
    parser.add_argument("--wa-url", default="http://localhost:8140", help="Workflow Actions URL")
    parser.add_argument("--gate-only", action="store_true", help="Only run gate evals")
    parser.add_argument("--dt-only", action="store_true", help="Only run delivery-targets evals")
    args = parser.parse_args()

    run_gate = not args.dt_only
    run_dt = not args.gate_only

    gate_results: list[dict[str, Any]] | None = None
    dt_results: list[dict[str, Any]] | None = None

    with httpx.Client() as client:
        if run_gate:
            gate_corpus = json.loads(
                (_CORPUS_DIR / "workflow_actions_gate.json").read_text()
            )
            print(f"Running gate evals ({len(gate_corpus)} scenarios) against {args.wa_url} ...")
            gate_results = run_gate_evals(client, args.wa_url, gate_corpus)

        if run_dt:
            dt_corpus_raw = json.loads(
                (_CORPUS_DIR / "delivery_targets.json").read_text()
            )
            dt_corpus = dt_corpus_raw["scenarios"]
            print(
                f"Running delivery-targets evals ({len(dt_corpus)} scenarios) "
                f"against {args.dt_url} ..."
            )
            dt_results = run_dt_evals(client, args.dt_url, dt_corpus)

    scorecard = render_scorecard(gate_results, dt_results)
    print()
    print(scorecard)

    _SCORECARD_PATH.write_text(scorecard)
    print(f"\n(scorecard also written to {_SCORECARD_PATH})")

    # Exit non-zero if any scenario failed
    all_results: list[dict[str, Any]] = []
    if gate_results:
        all_results.extend(gate_results)
    if dt_results:
        all_results.extend(dt_results)

    if any(not r["passed"] for r in all_results):
        sys.exit(1)


if __name__ == "__main__":
    main()
