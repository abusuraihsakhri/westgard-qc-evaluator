"""
FastAPI REST API Server for Westgard Qc Evaluator.
"""
from typing import Dict, Any, List
from westgard_qc import Observation, organize_by_run, evaluate_series, results_to_jsonable
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .base import AuditLogger, PHIGuard
from .models import SystemTaskPayload, ConsensusDossier
from .supervisor import SystemSupervisor

supervisor = SystemSupervisor(model_provider="mock")

app = FastAPI(
    title="Westgard Qc Evaluator API",
    description="Enterprise Distributed Component Platform (Clinical & Biomedical AI)",
    version="3.0.0-ENTERPRISE",
)


class QCObservation(BaseModel):
    run: int
    level: str
    value: float


class QCStatistics(BaseModel):
    level: str
    mean: float
    sd: float


class QCEvaluationRequest(BaseModel):
    observations: List[QCObservation]
    statistics: List[QCStatistics]


@app.post("/api/qc/evaluate")
def api_qc_evaluate(payload: QCEvaluationRequest):
    """Evaluate Westgard QC data using the same Python engine as the CLI."""
    if not payload.observations or len(payload.observations) > 10000:
        raise HTTPException(status_code=422, detail="Provide 1 to 10,000 observations")
    if not payload.statistics or len(payload.statistics) > 1000:
        raise HTTPException(status_code=422, detail="Provide 1 to 1,000 statistics rows")
    stats = {}
    try:
        for row in payload.statistics:
            if row.level in stats:
                raise ValueError(f"Duplicate statistics for level '{row.level}'")
            stats[row.level] = (row.mean, row.sd)
        observations = [Observation(run=x.run, level=x.level, value=x.value)
                        for x in payload.observations]
        runs, run_data, _ = organize_by_run(observations)
        results = evaluate_series(runs, run_data, stats)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "results": results_to_jsonable(results),
        "summary": {
            "total": len(results),
            "pass": sum(x.verdict == "PASS" for x in results),
            "warning": sum(x.verdict == "WARNING" for x in results),
            "reject": sum(x.verdict == "REJECT" for x in results),
        },
    }


class ChatRequest(BaseModel):
    query: str


@app.get("/health")
def health():
    return {"status": "HEALTHY", "service": "westgard-qc-evaluator", "domain": "Clinical & Biomedical AI", "standard": "CAP / CLSI / ISO Standards", "version": "3.0.0-ENTERPRISE"}


@app.get("/metrics")
def metrics():
    return {
        "dossiers_processed_total": len(supervisor.dossier_registry),
        "audit_blocks_total": len(AuditLogger.get_trail()),
        "system_status": "NOMINAL_OPTIMAL"
    }


@app.post("/api/audit")
def api_audit(payload: SystemTaskPayload):
    dossier = supervisor.process_task(payload)
    return dossier.to_dict()


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    try:
        ans = supervisor.query_supervisory_chat(req.query)
        return {"response": ans}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/audit/logs")
def api_audit_logs():
    return {"audit_trail": AuditLogger.get_trail(), "verified": AuditLogger.verify_integrity()}
