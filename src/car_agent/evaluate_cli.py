"""Command-line runner for the Phase 3 scenario evaluation set."""

from __future__ import annotations

import argparse

from .evaluation import run_phase3_evaluation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate deterministic Phase 3 sales behavior")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail unless at least 18 scenarios pass with zero budget violations",
    )
    args = parser.parse_args(argv)

    report = run_phase3_evaluation()
    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} {result.scenario_id}: {result.final_stage}")
        for failure in result.failures:
            print(f"  - {failure}")
    print(
        f"Phase 3: {report.passed_count}/{report.total_count} passed; "
        f"budget violations: {report.budget_violation_count}"
    )
    if args.strict and (report.passed_count < 18 or report.budget_violation_count):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
