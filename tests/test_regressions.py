"""Regression tests for input validation and rule semantics."""
import math
from collections import OrderedDict

import pytest

from agents.base import AuditTrail
from cli import parse_boolean
from westgard_qc import Observation, evaluate_series, organize_by_run, read_established_stats, read_observations


STATS = {"A": (100.0, 5.0), "B": (200.0, 10.0)}


def check(obs):
    runs, data, _ = organize_by_run(obs)
    return evaluate_series(runs, data, STATS)


def test_duplicate_run_level_is_rejected():
    with pytest.raises(ValueError, match="Duplicate observation"):
        organize_by_run([Observation(1, "A", 101), Observation(1, "A", 102)])


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_observation_is_rejected(bad, tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("run,level,value\n1,A," + str(bad) + "\n")
    with pytest.raises(ValueError, match="finite"):
        read_observations(str(path))


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "-2", "0"])
def test_invalid_sd_is_rejected(bad, tmp_path):
    path = tmp_path / "stats.csv"
    path.write_text("level,mean,sd\nA,100," + bad + "\n")
    with pytest.raises(ValueError, match="SD"):
        read_established_stats(str(path))


def test_duplicate_stat_levels_rejected(tmp_path):
    path = tmp_path / "stats.csv"
    path.write_text("level,mean,sd\nA,100,5\nA,100,6\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_established_stats(str(path))


def test_missing_level_breaks_consecutive_2_2s():
    obs = [Observation(1, "A", 112), Observation(2, "B", 200), Observation(3, "A", 112)]
    result = check(obs)
    assert result[-1].verdict == "WARNING"
    assert not any(v.rule == "2-2s" for v in result[-1].violations)


def test_missing_level_breaks_consecutive_4_1s():
    obs = [Observation(i, "A", 107) for i in (1, 2, 3, 5)]
    obs.append(Observation(4, "B", 200))
    result = check(obs)
    assert result[-1].verdict == "PASS"
    assert not any(v.rule == "4-1s" for v in result[-1].violations)


def test_r4s_requires_both_opposite_2sd_excursions():
    # A at +3.2 SD and B at -1.1 SD: span > 4 SD,
    # but B is not below -2 SD, so R-4s does not apply.
    result = check([Observation(1, "A", 116), Observation(1, "B", 189)])
    assert all(v.rule != "R-4s" for v in result[0].violations)
    assert result[0].verdict == "REJECT"  # 1-3s still applies.


def test_audit_detects_mutated_signed_entry():
    trail = AuditTrail(secret_key="long-enough-test-key")
    trail.log("tester", "unit", "EVENT", {"status": "ok"})
    copy = trail.get_trail()
    copy[0]["actor"] = "external-change"
    assert trail.verify_integrity() is True
    trail.logs[0]["actor"] = "tampered"
    assert trail.verify_integrity() is False


@pytest.mark.parametrize(("raw", "expected"), [
    ("true", True), ("false", False), ("0", False), ("1", True), ("yes", True), ("no", False), ("", False)
])
def test_csv_booleans(raw, expected):
    assert parse_boolean(raw) is expected


def test_invalid_csv_boolean():
    with pytest.raises(ValueError, match="Invalid boolean"):
        parse_boolean("not-sure")
