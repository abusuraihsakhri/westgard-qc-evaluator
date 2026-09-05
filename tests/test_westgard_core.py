"""
Additional edge case tests for the Westgard multirule QC evaluator.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import csv
import os
import tempfile
from collections import OrderedDict

from westgard_qc import (
    Observation,
    RunResult,
    Violation,
    compute_established_stats,
    evaluate_series,
    organize_by_run,
    read_observations,
    read_established_stats,
    _validate_path,
)


STATS = {"Level1": (100.0, 5.0), "Level2": (200.0, 10.0)}


class TestPathValidation:
    """Tests for path traversal prevention."""

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            _validate_path("../etc/passwd")

    def test_rejects_deep_traversal(self):
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            _validate_path("subdir/../../../etc/passwd")

    def test_accepts_safe_relative_path(self):
        result = _validate_path("data.csv")
        assert result.endswith("data.csv")

    def test_accepts_safe_absolute_within_cwd(self):
        cwd = os.getcwd()
        safe_path = os.path.join(cwd, "data.csv")
        result = _validate_path(safe_path)
        assert result.endswith("data.csv")


class TestCSVReading:
    """Tests for CSV file reading with path validation."""

    def test_read_observations_valid_file(self, tmp_path):
        csv_file = tmp_path / "observations.csv"
        csv_file.write_text("run,level,value\n1,Level1,100.0\n2,Level1,105.0\n")
        obs = read_observations(str(csv_file))
        assert len(obs) == 2
        assert obs[0].run == 1
        assert obs[0].level == "Level1"
        assert obs[0].value == 100.0

    def test_read_observations_rejects_traversal(self):
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            read_observations("../secret.csv")

    def test_read_established_stats_valid_file(self, tmp_path):
        csv_file = tmp_path / "stats.csv"
        csv_file.write_text("level,mean,sd\nLevel1,100.0,5.0\n")
        stats = read_established_stats(str(csv_file))
        assert stats["Level1"] == (100.0, 5.0)

    def test_read_established_stats_rejects_nonpositive_sd(self, tmp_path):
        csv_file = tmp_path / "bad_stats.csv"
        csv_file.write_text("level,mean,sd\nLevel1,100.0,0.0\n")
        with pytest.raises(ValueError, match="must be > 0"):
            read_established_stats(str(csv_file))


class TestEdgeCases:
    """Edge case tests for the Westgard multirule algorithm."""

    def test_single_level_run_passes_within_1sd(self):
        """Single level run with value within 1SD should PASS."""
        obs = [Observation(1, "Level1", 100.5)]
        runs_ordered, run_data, _ = organize_by_run(obs)
        results = evaluate_series(runs_ordered, run_data, STATS)
        assert results[0].verdict == "PASS"

    def test_exact_2sd_boundary_warns(self):
        """Value at exactly 2SD should trigger warning (boundary test)."""
        obs = [Observation(1, "Level1", 110.0)]  # z = 2.0 exactly
        runs_ordered, run_data, _ = organize_by_run(obs)
        results = evaluate_series(runs_ordered, run_data, STATS)
        assert results[0].verdict == "WARNING"
        assert any(v.rule == "1-2s" for v in results[0].violations)

    def test_exact_3sd_boundary_rejects(self):
        """Value at exactly 3SD should trigger rejection (boundary test)."""
        obs = [Observation(1, "Level1", 115.0)]  # z = 3.0 exactly
        runs_ordered, run_data, _ = organize_by_run(obs)
        results = evaluate_series(runs_ordered, run_data, STATS)
        assert results[0].verdict == "REJECT"
        assert any(v.rule == "1-3s" for v in results[0].violations)

    def test_2_2s_within_run_positive(self):
        """Two levels both above +2SD in same run trigger within-run 2-2s."""
        obs = [
            Observation(1, "Level1", 112),  # z = 2.4
            Observation(1, "Level2", 222),  # z = 2.2
        ]
        runs_ordered, run_data, _ = organize_by_run(obs)
        results = evaluate_series(runs_ordered, run_data, STATS)
        assert results[0].verdict == "REJECT"
        v_22s = [v for v in results[0].violations if v.rule == "2-2s" and v.scope == "within-run"]
        assert len(v_22s) >= 1

    def test_2_2s_within_run_negative(self):
        """Two levels both below -2SD in same run trigger within-run 2-2s."""
        obs = [
            Observation(1, "Level1", 88),  # z = -2.4
            Observation(1, "Level2", 178),  # z = -2.2
        ]
        runs_ordered, run_data, _ = organize_by_run(obs)
        results = evaluate_series(runs_ordered, run_data, STATS)
        assert results[0].verdict == "REJECT"
        v_22s = [v for v in results[0].violations if v.rule == "2-2s" and v.scope == "within-run"]
        assert len(v_22s) >= 1

    def test_multiple_runs_preserve_order(self):
        """Runs should be evaluated in chronological order."""
        obs = [
            Observation(3, "Level1", 100),
            Observation(1, "Level1", 100),
            Observation(2, "Level1", 100),
        ]
        runs_ordered, run_data, _ = organize_by_run(obs)
        assert runs_ordered == [1, 2, 3]

    def test_compute_established_stats_requires_min_2_obs(self):
        """Computing SD requires at least 2 observations."""
        obs = [Observation(1, "Level1", 100.0)]
        with pytest.raises(ValueError, match="single observation"):
            compute_established_stats(obs)

    def test_empty_stats_on_unknown_level(self):
        """Unknown level in stats should raise an error."""
        obs = [Observation(1, "UnknownLevel", 100.0)]
        runs_ordered, run_data, _ = organize_by_run(obs)
        with pytest.raises(ValueError, match="No established mean/SD"):
            evaluate_series(runs_ordered, run_data, STATS)

    def test_warning_does_not_escalate_to_reject(self):
        """A run with only warning-class violations should be WARNING, not REJECT."""
        obs = [Observation(1, "Level1", 111)]  # z = 2.2, only 1-2s
        runs_ordered, run_data, _ = organize_by_run(obs)
        results = evaluate_series(runs_ordered, run_data, STATS)
        assert results[0].verdict == "WARNING"
        assert all(not v.is_rejection for v in results[0].violations)


class TestAuditSecurity:
    """Tests for audit trail security improvements."""

    def test_phi_guard_blocks_mrn(self):
        from agents.base import PHIGuard, SecurityException
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Patient MRN-12345678")

    def test_phi_guard_blocks_ssn(self):
        from agents.base import PHIGuard, SecurityException
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("SSN: 123-45-6789")

    def test_phi_guard_allows_clean_text(self):
        from agents.base import PHIGuard
        PHIGuard.assert_no_phi("Analytical result within normal limits")

    def test_audit_trail_integrity_after_multiple_entries(self):
        from agents.base import AuditLogger
        # Log several entries
        for i in range(5):
            AuditLogger.log("test", "tier", "EVENT", {"index": i})
        assert AuditLogger.verify_integrity() is True
