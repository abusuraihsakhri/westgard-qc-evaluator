"""API regression tests for the dedicated Westgard endpoint."""
import pytest
from fastapi import HTTPException
from agents.api import QCEvaluationRequest, api_qc_evaluate


def test_qc_api_evaluates_westgard_rules():
    payload = QCEvaluationRequest(
        observations=[
            {"run": 1, "level": "A", "value": 112.0},
            {"run": 2, "level": "A", "value": 112.0},
        ],
        statistics=[{"level": "A", "mean": 100.0, "sd": 5.0}],
    )
    output = api_qc_evaluate(payload)
    assert output["summary"]["reject"] == 1
    assert output["results"][1]["verdict"] == "REJECT"
    assert any(v["rule"] == "2-2s" for v in output["results"][1]["violations"])


def test_qc_api_rejects_duplicate_measurements():
    payload = QCEvaluationRequest(
        observations=[
            {"run": 1, "level": "A", "value": 112.0},
            {"run": 1, "level": "A", "value": 111.0},
        ],
        statistics=[{"level": "A", "mean": 100.0, "sd": 5.0}],
    )
    with pytest.raises(HTTPException) as exc:
        api_qc_evaluate(payload)
    assert exc.value.status_code == 422


def test_qc_api_rejects_missing_statistics():
    payload = QCEvaluationRequest(
        observations=[{"run": 1, "level": "A", "value": 112.0}],
        statistics=[{"level": "B", "mean": 100.0, "sd": 5.0}],
    )
    with pytest.raises(HTTPException) as exc:
        api_qc_evaluate(payload)
    assert exc.value.status_code == 422
