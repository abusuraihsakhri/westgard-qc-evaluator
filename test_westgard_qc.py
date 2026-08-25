"""Tests for the Westgard multirule QC evaluator.

Run with: python test_westgard_qc.py
"""

from collections import OrderedDict

from westgard_qc import (
    Observation,
    compute_established_stats,
    evaluate_series,
    organize_by_run,
)

STATS = {"Level1": (100.0, 5.0), "Level2": (200.0, 10.0)}


def run_ids_with_rule(results, rule):
    return {r.run for r in results if any(v.rule == rule for v in r.violations)}


def verdict_of(results, run_id):
    for r in results:
        if r.run == run_id:
            return r.verdict
    raise KeyError(run_id)


def test_clean_series_passes():
    """Values that stay within 1SD of the mean should PASS every run."""
    obs = [
        Observation(1, "Level1", 101), Observation(1, "Level2", 198),
        Observation(2, "Level1", 99), Observation(2, "Level2", 203),
        Observation(3, "Level1", 102), Observation(3, "Level2", 197),
    ]
    runs_ordered, run_data, _ = organize_by_run(obs)
    results = evaluate_series(runs_ordered, run_data, STATS)
    assert all(r.verdict == "PASS" for r in results), results
    assert all(not r.violations for r in results)


def test_1_3s_rejects_single_outlier():
    """A control result beyond 3SD must REJECT that run via the 1-3s rule."""
    obs = [
        Observation(1, "Level1", 101),
        Observation(2, "Level1", 116),  # z = (116-100)/5 = 3.2
    ]
    runs_ordered, run_data, _ = organize_by_run(obs)
    results = evaluate_series(runs_ordered, run_data, STATS)
    assert verdict_of(results, 1) == "PASS"
    assert verdict_of(results, 2) == "REJECT"
    assert 2 in run_ids_with_rule(results, "1-3s")


def test_1_2s_warns_without_other_rule():
    """A lone result beyond 2SD (but under 3SD) should WARN, not REJECT,
    when no other rule is also triggered."""
    obs = [
        Observation(1, "Level1", 100),
        Observation(2, "Level1", 111),  # z = 2.2
    ]
    runs_ordered, run_data, _ = organize_by_run(obs)
    results = evaluate_series(runs_ordered, run_data, STATS)
    assert verdict_of(results, 2) == "WARNING"
    assert 2 in run_ids_with_rule(results, "1-2s")
    assert 2 not in run_ids_with_rule(results, "1-3s")


def test_2_2s_across_run_rejects_two_consecutive_same_side():
    """Two consecutive runs of the same level both beyond +2SD trigger the
    across-run 2-2s rejection rule on the second run."""
    obs = [
        Observation(1, "Level2", 222),  # z = 2.2
        Observation(2, "Level2", 223),  # z = 2.3, same side -> 2-2s
    ]
    runs_ordered, run_data, _ = organize_by_run(obs)
    results = evaluate_series(runs_ordered, run_data, STATS)
    assert verdict_of(results, 1) == "WARNING"   # 1-2s only
    assert verdict_of(results, 2) == "REJECT"
    v = [v for v in results[1].violations if v.rule == "2-2s"]
    assert len(v) == 1 and v[0].scope == "across-run"


def test_r_4s_within_run_rejects_wide_spread():
    """Two different levels in the same run, one above +2SD and one below
    -2SD (total spread >= 4SD), trigger the within-run R-4s rule."""
    obs = [
        Observation(1, "Level1", 112),  # z = 2.4
        Observation(1, "Level2", 178),  # z = -2.2, spread = 4.6
    ]
    runs_ordered, run_data, _ = organize_by_run(obs)
    results = evaluate_series(runs_ordered, run_data, STATS)
    assert verdict_of(results, 1) == "REJECT"
    rules = {v.rule for v in results[0].violations}
    assert "R-4s" in rules
    r4s = [v for v in results[0].violations if v.rule == "R-4s"][0]
    assert r4s.scope == "within-run"
    assert set(r4s.levels) == {"Level1", "Level2"}


def test_4_1s_across_run_rejects_four_consecutive_same_side():
    """Four consecutive runs of the same level all beyond +1SD trigger the
    across-run 4-1s rejection rule on the fourth run."""
    obs = [
        Observation(1, "Level1", 106),  # z = 1.2
        Observation(2, "Level1", 107),  # z = 1.4
        Observation(3, "Level1", 105.5),  # z = 1.1
        Observation(4, "Level1", 106.5),  # z = 1.3
    ]
    runs_ordered, run_data, _ = organize_by_run(obs)
    results = evaluate_series(runs_ordered, run_data, STATS)
    assert verdict_of(results, 3) == "PASS"
    assert verdict_of(results, 4) == "REJECT"
    assert 4 in run_ids_with_rule(results, "4-1s")


def test_10x_across_run_rejects_ten_consecutive_same_side():
    """Ten consecutive runs of the same level all above (or all below) the
    mean trigger the across-run 10x rejection rule on the tenth run."""
    obs = []
    # small, alternating-magnitude but always-positive offsets so no other
    # rule (1-2s/1-3s/4-1s) fires before the 10th point
    offsets = [0.3, 0.4, 0.2, 0.5, 0.3, 0.4, 0.2, 0.3, 0.5, 0.4]
    for i, off in enumerate(offsets, start=1):
        obs.append(Observation(i, "Level1", 100 + off * 5))
    runs_ordered, run_data, _ = organize_by_run(obs)
    results = evaluate_series(runs_ordered, run_data, STATS)
    for run in range(1, 10):
        assert verdict_of(results, run) == "PASS", (run, results[run - 1].violations)
    assert verdict_of(results, 10) == "REJECT"
    assert 10 in run_ids_with_rule(results, "10x")


def test_compute_established_stats_matches_numpy_sample_sd():
    """The established mean/SD computed from raw data must match a manual
    sample-SD (ddof=1) computation."""
    obs = [
        Observation(1, "Level1", 98),
        Observation(2, "Level1", 100),
        Observation(3, "Level1", 102),
        Observation(4, "Level1", 100),
    ]
    stats = compute_established_stats(obs)
    mean, sd = stats["Level1"]
    values = [98, 100, 102, 100]
    expected_mean = sum(values) / len(values)
    variance = sum((v - expected_mean) ** 2 for v in values) / (len(values) - 1)
    expected_sd = variance ** 0.5
    assert abs(mean - expected_mean) < 1e-9
    assert abs(sd - expected_sd) < 1e-9


def test_multilevel_run_only_flags_offending_level():
    """In a multi-level run, a violation on one level must not falsely mark
    an in-control level as violating."""
    obs = [
        Observation(1, "Level1", 101),
        Observation(1, "Level2", 199),
        Observation(2, "Level1", 116),  # 1-3s reject
        Observation(2, "Level2", 200),  # in control
    ]
    runs_ordered, run_data, _ = organize_by_run(obs)
    results = evaluate_series(runs_ordered, run_data, STATS)
    run2 = results[1]
    assert run2.verdict == "REJECT"
    levels_flagged = {lvl for v in run2.violations for lvl in v.levels}
    assert "Level1" in levels_flagged
    assert "Level2" not in levels_flagged


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL: {test.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passed")
    if failures:
        raise SystemExit(1)
