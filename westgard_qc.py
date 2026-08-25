#!/usr/bin/env python3
"""
Westgard QC Evaluator
======================

Evaluates clinical laboratory QC control results against the Westgard
multirule system (Westgard, Barry, Hunt & Groth, 1981), flagging runs
that violate the 1-3s, 2-2s, R-4s, 4-1s and 10x rules.

The 1981 Westgard multirule scheme combines several individual control
rules, applied both *within* a single analytical run (comparing
different control levels measured together) and *across* consecutive
runs (comparing successive results for the same control level):

  Rule    Scope                Meaning
  ------  -------------------  ---------------------------------------------
  1-2s    single point         one control exceeds mean +/- 2SD (warning
                                only -- triggers inspection of the other
                                rules, does not reject by itself)
  1-3s    single point         one control exceeds mean +/- 3SD (reject)
  2-2s    within-run / across  two controls exceed the same +2SD or -2SD
                                limit -- either two different levels in the
                                same run, or the same level in two
                                consecutive runs (reject, systematic error)
  R-4s    within-run           the range between the highest and lowest
                                control observation in the same run spans
                                >= 4SD (reject, random error)
  4-1s    across-run           four consecutive control observations for
                                the same level exceed the same +1SD or -1SD
                                limit (reject, systematic error)
  10x     across-run           ten consecutive control observations for the
                                same level fall on the same side of the
                                mean (reject, systematic error)

A run is REJECTed if any rejection-class rule fires for any control
level measured in that run, WARNING if only the 1-2s screening rule
fires, and PASS otherwise.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Data ingestion
# ---------------------------------------------------------------------------

@dataclass
class Observation:
    run: int
    level: str
    value: float


def read_observations(path: str) -> List[Observation]:
    """Read a long-format QC data CSV with columns: run, level, value."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: no header row found")
        colmap = {name.strip().lower(): name for name in reader.fieldnames}
        for required in ("run", "level", "value"):
            if required not in colmap:
                raise ValueError(
                    f"{path}: missing required column '{required}' "
                    f"(found columns: {reader.fieldnames})"
                )
        observations = []
        for row in reader:
            if not row.get(colmap["run"], "").strip():
                continue  # skip blank lines
            observations.append(
                Observation(
                    run=int(row[colmap["run"]]),
                    level=row[colmap["level"]].strip(),
                    value=float(row[colmap["value"]]),
                )
            )
    if not observations:
        raise ValueError(f"{path}: no data rows found")
    return observations


def read_established_stats(path: str) -> Dict[str, Tuple[float, float]]:
    """Read established mean/SD per control level from a CSV with columns:
    level, mean, sd."""
    stats: Dict[str, Tuple[float, float]] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: no header row found")
        colmap = {name.strip().lower(): name for name in reader.fieldnames}
        for required in ("level", "mean", "sd"):
            if required not in colmap:
                raise ValueError(f"{path}: missing required column '{required}'")
        for row in reader:
            level = row[colmap["level"]].strip()
            if not level:
                continue
            mean = float(row[colmap["mean"]])
            sd = float(row[colmap["sd"]])
            if sd <= 0:
                raise ValueError(f"{path}: SD for level '{level}' must be > 0")
            stats[level] = (mean, sd)
    return stats


def compute_established_stats(observations: List[Observation]) -> Dict[str, Tuple[float, float]]:
    """Compute the established mean and sample SD per level from a series
    of QC observations (e.g. a baseline/precision run), using numpy."""
    by_level: Dict[str, List[float]] = OrderedDict()
    for obs in observations:
        by_level.setdefault(obs.level, []).append(obs.value)

    stats: Dict[str, Tuple[float, float]] = {}
    for level, values in by_level.items():
        arr = np.array(values, dtype=float)
        if arr.size < 2:
            raise ValueError(
                f"Cannot compute an established SD for level '{level}' "
                f"from a single observation; supply --stats instead."
            )
        mean = float(np.mean(arr))
        sd = float(np.std(arr, ddof=1))  # sample SD, matches lab QC convention
        if sd == 0:
            raise ValueError(f"Computed SD for level '{level}' is 0 (all values identical)")
        stats[level] = (mean, sd)
    return stats


def organize_by_run(
    observations: List[Observation],
) -> Tuple[List[int], "OrderedDict[int, Dict[str, float]]", List[str]]:
    """Group observations by run, preserving first-seen run and level order."""
    run_data: "OrderedDict[int, Dict[str, float]]" = OrderedDict()
    level_order: List[str] = []
    for obs in sorted(observations, key=lambda o: o.run):
        run_data.setdefault(obs.run, OrderedDict())[obs.level] = obs.value
        if obs.level not in level_order:
            level_order.append(obs.level)
    runs_ordered = list(run_data.keys())
    return runs_ordered, run_data, level_order


# ---------------------------------------------------------------------------
# Westgard multirule evaluation
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    rule: str            # "1-2s", "1-3s", "2-2s", "R-4s", "4-1s", "10x"
    scope: str            # "single-point", "within-run", "across-run"
    levels: List[str]
    is_rejection: bool
    message: str


@dataclass
class RunResult:
    run: int
    verdict: str          # "PASS", "WARNING", "REJECT"
    z_scores: Dict[str, float]
    violations: List[Violation] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


WARNING_LIMIT = 2.0
REJECT_LIMIT = 3.0
SYSTEMATIC_2S_LIMIT = 2.0
SYSTEMATIC_1S_LIMIT = 1.0
RANGE_4S_LIMIT = 4.0
RUN_LENGTH_4 = 4
RUN_LENGTH_10 = 10


def evaluate_series(
    runs_ordered: List[int],
    run_data: "OrderedDict[int, Dict[str, float]]",
    stats: Dict[str, Tuple[float, float]],
) -> List[RunResult]:
    """Evaluate every run in chronological order against the Westgard
    multirule set, maintaining per-level history for the across-run rules."""
    history: Dict[str, List[float]] = {}
    results: List[RunResult] = []

    for run_id in runs_ordered:
        levels_in_run = run_data[run_id]
        for level in levels_in_run:
            if level not in stats:
                raise ValueError(f"No established mean/SD available for level '{level}'")

        z_scores: Dict[str, float] = {}
        violations: List[Violation] = []

        # --- single-point rules: 1-2s (warning), 1-3s (reject) -----------
        for level, value in levels_in_run.items():
            mean, sd = stats[level]
            z = (value - mean) / sd
            z_scores[level] = z
            if abs(z) >= REJECT_LIMIT:
                violations.append(Violation(
                    rule="1-3s", scope="single-point", levels=[level], is_rejection=True,
                    message=f"{level}: value {value:g} is z={z:+.2f}SD from the mean (>= 3SD)",
                ))
            elif abs(z) >= WARNING_LIMIT:
                violations.append(Violation(
                    rule="1-2s", scope="single-point", levels=[level], is_rejection=False,
                    message=f"{level}: value {value:g} is z={z:+.2f}SD from the mean (>= 2SD, warning)",
                ))

        # --- within-run rules (require >= 2 levels measured together) ----
        levels_present = list(levels_in_run.keys())
        if len(levels_present) >= 2:
            zmax_level = max(levels_present, key=lambda l: z_scores[l])
            zmin_level = min(levels_present, key=lambda l: z_scores[l])
            zmax, zmin = z_scores[zmax_level], z_scores[zmin_level]
            if (zmax - zmin) >= RANGE_4S_LIMIT:
                violations.append(Violation(
                    rule="R-4s", scope="within-run", levels=[zmax_level, zmin_level], is_rejection=True,
                    message=(f"Range between {zmax_level} (z={zmax:+.2f}) and {zmin_level} "
                             f"(z={zmin:+.2f}) is {zmax - zmin:.2f}SD (>= 4SD)"),
                ))

            pos2 = [l for l in levels_present if z_scores[l] >= SYSTEMATIC_2S_LIMIT]
            neg2 = [l for l in levels_present if z_scores[l] <= -SYSTEMATIC_2S_LIMIT]
            if len(pos2) >= 2:
                violations.append(Violation(
                    rule="2-2s", scope="within-run", levels=pos2, is_rejection=True,
                    message=f"Levels {pos2} both exceed +2SD within the same run",
                ))
            if len(neg2) >= 2:
                violations.append(Violation(
                    rule="2-2s", scope="within-run", levels=neg2, is_rejection=True,
                    message=f"Levels {neg2} both exceed -2SD within the same run",
                ))

        # --- update per-level history, then across-run rules --------------
        for level in levels_present:
            history.setdefault(level, []).append(z_scores[level])

        for level in levels_present:
            h = history[level]

            if len(h) >= 2 and h[-1] >= SYSTEMATIC_2S_LIMIT and h[-2] >= SYSTEMATIC_2S_LIMIT:
                violations.append(Violation(
                    rule="2-2s", scope="across-run", levels=[level], is_rejection=True,
                    message=f"{level}: last 2 consecutive runs both exceed +2SD "
                            f"(z={h[-2]:+.2f}, {h[-1]:+.2f})",
                ))
            if len(h) >= 2 and h[-1] <= -SYSTEMATIC_2S_LIMIT and h[-2] <= -SYSTEMATIC_2S_LIMIT:
                violations.append(Violation(
                    rule="2-2s", scope="across-run", levels=[level], is_rejection=True,
                    message=f"{level}: last 2 consecutive runs both exceed -2SD "
                            f"(z={h[-2]:+.2f}, {h[-1]:+.2f})",
                ))

            if len(h) >= RUN_LENGTH_4:
                last4 = h[-RUN_LENGTH_4:]
                if all(v >= SYSTEMATIC_1S_LIMIT for v in last4):
                    violations.append(Violation(
                        rule="4-1s", scope="across-run", levels=[level], is_rejection=True,
                        message=f"{level}: last 4 consecutive runs all exceed +1SD "
                                f"({', '.join(f'{v:+.2f}' for v in last4)})",
                    ))
                if all(v <= -SYSTEMATIC_1S_LIMIT for v in last4):
                    violations.append(Violation(
                        rule="4-1s", scope="across-run", levels=[level], is_rejection=True,
                        message=f"{level}: last 4 consecutive runs all exceed -1SD "
                                f"({', '.join(f'{v:+.2f}' for v in last4)})",
                    ))

            if len(h) >= RUN_LENGTH_10:
                last10 = h[-RUN_LENGTH_10:]
                if all(v > 0 for v in last10):
                    violations.append(Violation(
                        rule="10x", scope="across-run", levels=[level], is_rejection=True,
                        message=f"{level}: last 10 consecutive runs all fall above the mean",
                    ))
                if all(v < 0 for v in last10):
                    violations.append(Violation(
                        rule="10x", scope="across-run", levels=[level], is_rejection=True,
                        message=f"{level}: last 10 consecutive runs all fall below the mean",
                    ))

        if any(v.is_rejection for v in violations):
            verdict = "REJECT"
        elif violations:
            verdict = "WARNING"
        else:
            verdict = "PASS"

        results.append(RunResult(run=run_id, verdict=verdict, z_scores=z_scores, violations=violations))

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def format_report(results: List[RunResult], stats: Dict[str, Tuple[float, float]]) -> str:
    lines = []
    lines.append("Established statistics:")
    for level, (mean, sd) in stats.items():
        lines.append(f"  {level}: mean={mean:g}  SD={sd:g}")
    lines.append("")
    lines.append(f"{'Run':<5} {'Verdict':<8} Details")
    lines.append("-" * 60)
    for r in results:
        if not r.violations:
            lines.append(f"{r.run:<5} {r.verdict:<8} all controls within limits")
        else:
            first = True
            for v in r.violations:
                prefix = f"{r.run:<5} {r.verdict:<8}" if first else f"{'':<5} {'':<8}"
                lines.append(f"{prefix} [{v.rule}/{v.scope}] {v.message}")
                first = False

    n_reject = sum(1 for r in results if r.verdict == "REJECT")
    n_warn = sum(1 for r in results if r.verdict == "WARNING")
    n_pass = sum(1 for r in results if r.verdict == "PASS")
    lines.append("-" * 60)
    lines.append(f"Summary: {n_pass} PASS, {n_warn} WARNING, {n_reject} REJECT (of {len(results)} runs)")
    return "\n".join(lines)


def results_to_jsonable(results: List[RunResult]) -> list:
    out = []
    for r in results:
        d = {
            "run": r.run,
            "verdict": r.verdict,
            "z_scores": r.z_scores,
            "violations": [
                {
                    "rule": v.rule,
                    "scope": v.scope,
                    "levels": v.levels,
                    "is_rejection": v.is_rejection,
                    "message": v.message,
                }
                for v in r.violations
            ],
        }
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Levey-Jennings plot
# ---------------------------------------------------------------------------

def generate_levey_jennings_plot(
    runs_ordered: List[int],
    run_data: "OrderedDict[int, Dict[str, float]]",
    stats: Dict[str, Tuple[float, float]],
    results: List[RunResult],
    level_order: List[str],
    out_path: str,
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    result_by_run = {r.run: r for r in results}
    n_levels = len(level_order)
    fig, axes = plt.subplots(n_levels, 1, figsize=(10, 3.2 * n_levels), squeeze=False)

    for idx, level in enumerate(level_order):
        ax = axes[idx][0]
        mean, sd = stats[level]

        xs = [run for run in runs_ordered if level in run_data[run]]
        ys = [run_data[run][level] for run in xs]

        for n_sd, style in ((1, ":"), (2, "--"), (3, "-")):
            ax.axhline(mean + n_sd * sd, color="gray", linestyle=style, linewidth=0.8)
            ax.axhline(mean - n_sd * sd, color="gray", linestyle=style, linewidth=0.8)
        ax.axhline(mean, color="black", linestyle="-", linewidth=1.0)

        ax.plot(xs, ys, color="steelblue", linewidth=1.0, zorder=1)

        for run, y in zip(xs, ys):
            result = result_by_run[run]
            level_violations = [v for v in result.violations if level in v.levels]
            reject = any(v.is_rejection for v in level_violations)
            warn = any(not v.is_rejection for v in level_violations)
            if reject:
                color, marker, size = "red", "x", 70
            elif warn:
                color, marker, size = "orange", "^", 50
            else:
                color, marker, size = "steelblue", "o", 30
            ax.scatter([run], [y], color=color, marker=marker, s=size, zorder=2)
            if level_violations:
                rules = "/".join(sorted({v.rule for v in level_violations}))
                ax.annotate(rules, (run, y), textcoords="offset points", xytext=(4, 4), fontsize=7)

        ax.set_title(f"Levey-Jennings: {level} (mean={mean:g}, SD={sd:g})")
        ax.set_xlabel("Run")
        ax.set_ylabel("Control value")
        ax.set_xticks(runs_ordered)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="westgard_qc.py",
        description="Evaluate QC control results against the Westgard multirule system.",
    )
    parser.add_argument(
        "--data", required=True,
        help="CSV of QC observations with columns: run, level, value",
    )
    parser.add_argument(
        "--stats",
        help="CSV of established mean/SD per level with columns: level, mean, sd. "
             "If omitted, mean/SD are computed from --data itself.",
    )
    parser.add_argument(
        "--plot",
        help="Path to save a Levey-Jennings plot (PNG) with rule violations annotated.",
    )
    parser.add_argument(
        "--json",
        help="Path to save the full per-run results as JSON.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        observations = read_observations(args.data)
        runs_ordered, run_data, level_order = organize_by_run(observations)

        if args.stats:
            stats = read_established_stats(args.stats)
        else:
            print("No --stats file given; computing established mean/SD from --data.\n", file=sys.stderr)
            stats = compute_established_stats(observations)

        results = evaluate_series(runs_ordered, run_data, stats)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(format_report(results, stats))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results_to_jsonable(results), f, indent=2)
        print(f"\nJSON results written to {args.json}")

    if args.plot:
        generate_levey_jennings_plot(runs_ordered, run_data, stats, results, level_order, args.plot)
        print(f"Levey-Jennings plot written to {args.plot}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
