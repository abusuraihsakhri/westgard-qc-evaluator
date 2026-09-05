# Westgard QC Evaluator

> **Domain:** Clinical Decision Support & Biomedical Computing
> **Reference Guidelines & Standards:** Westgard, Barry, Hunt & Groth (1981); CAP / CLSI / ISO Standards

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)
![Audit Trail](https://img.shields.io/badge/Audit-HMAC--SHA256_Tamper--Evident-brightgreen.svg)
![Zero-PHI Guard](https://img.shields.io/badge/Guard-Zero--PHI_Outbound-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## 📖 What It Does

Evaluates clinical laboratory QC control results against the Westgard
multirule system (Westgard, Barry, Hunt & Groth, 1981), flagging runs
that violate the 1-3s, 2-2s, R-4s, 4-1s and 10x rules.

The 1981 Westgard multirule scheme combines several individual control
rules, applied both *within* a single analytical run (comparing
different control levels measured together) and *across* consecutive
runs (comparing successive results for the same control level):

| Rule | Scope | Meaning |
|------|-------|---------|
| 1-2s | single point | one control exceeds mean +/- 2SD (warning only -- triggers inspection of the other rules, does not reject by itself) |
| 1-3s | single point | one control exceeds mean +/- 3SD (reject) |
| 2-2s | within-run / across | two controls exceed the same +2SD or -2SD limit -- either two different levels in the same run, or the same level in two consecutive runs (reject, systematic error) |
| R-4s | within-run | the range between the highest and lowest control observation in the same run spans >= 4SD (reject, random error) |
| 4-1s | across-run | four consecutive control observations for the same level exceed the same +1SD or -1SD limit (reject, systematic error) |
| 10x | across-run | ten consecutive control observations for the same level fall on the same side of the mean (reject, systematic error) |

A run is REJECTed if any rejection-class rule fires for any control
level measured in that run, WARNING if only the 1-2s screening rule
fires, and PASS otherwise.

---

## ⚙️ Key Capabilities & Algorithmic Modules

### 🔬 Core Algorithmic & Evaluation Engines

- **`westgard_qc.py`** — Core Westgard multirule evaluation engine with CSV data ingestion, Levey-Jennings plotting, and JSON/CLI reporting.
- **`agents/`** — Enterprise multi-agent orchestration with specialized workers (QC Invariant, Safety Escalation, Protocol Conformance).
- **`enrichment.py`** — Enrichment feature suite with longitudinal tracking, alert escalation, and cross-institutional analytics.
- **`cli.py`** — Command-line interface with audit, chat, batch processing, and REST server modes.
- **`agents/api.py`** — FastAPI REST API server with health, metrics, audit, and chat endpoints.

---

## 💻 Installation

### Prerequisites
- Python 3.10+
- pip

### Setup
```bash
# Clone the repository
git clone https://github.com/abusuraihsakhri/westgard-qc-evaluator.git
cd westgard-qc-evaluator

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or install with pyproject.toml
pip install -e ".[test]"
```

---

## 💻 CLI Quickstart & Usage

### 1. Westgard Multirule Evaluation (Core Algorithm)
```bash
# Evaluate QC data against established statistics
python westgard_qc.py --data observations.csv --stats stats.csv

# With JSON output and Levey-Jennings plot
python westgard_qc.py --data observations.csv --stats stats.csv --json results.json --plot chart.png

# Compute statistics from data itself
python westgard_qc.py --data observations.csv
```

### Input CSV Format

**Observations file** (`observations.csv`):
```csv
run,level,value
1,Level1,100.5
1,Level2,198.2
2,Level1,99.8
2,Level2,203.1
```

**Statistics file** (`stats.csv`) - optional:
```csv
level,mean,sd
Level1,100.0,5.0
Level2,200.0,10.0
```

### 2. Enterprise CLI (Agents Framework)
```bash
# Run single task evaluation
python cli.py audit --task-id TASK-01 --primary 28.5 --secondary 14.2

# Batch process CSV records
python cli.py batch -i input.csv -o results.csv

# Verify HMAC audit trail integrity
python cli.py verify-audit

# Launch FastAPI REST server
python cli.py serve --host 127.0.0.1 --port 8000

# Supervisor chat query
python cli.py chat "Explain QC conformance status"
```

### 3. High-Throughput Simulation
```bash
# Run 1000-task simulation benchmark
python simulator.py 1000
```

---

## 🛡️ Security & Enterprise Architecture

* **Zero-PHI Outbound Interceptor:** Active AST and regex inspection blocking SSNs, MRNs, phone numbers, and patient identifiers.
* **Tamper-Evident HMAC-SHA256 Audit Trail:** Chained, cryptographically signed logs for every evaluation and state transition.
* **Path Traversal Protection:** Input file paths are validated to prevent directory traversal attacks.
* **Secure Audit Key Management:** Audit secret key sourced from environment variable with development-only fallback and minimum length enforcement.
* **FastAPI & Prometheus Telemetry:** Exposes OpenAPI 3.1 REST endpoints and operational Prometheus metrics (`/metrics`).

### Security Configuration

Set the `AUDIT_SECRET_KEY` environment variable for production deployments:
```bash
export AUDIT_SECRET_KEY="your-secure-random-key-min-16-chars"
```

---

## 🐳 Container Deployment

```bash
docker build -t westgard-qc-evaluator .
docker run -p 8000:8000 -e AUDIT_SECRET_KEY="your-secure-key" westgard-qc-evaluator
```

Using Docker Compose:
```bash
docker-compose up -d
```

---

## 🧪 Testing & Verification

Run the complete test suite:

```bash
pytest -v
```

Run with coverage:
```bash
pytest -v --cov=. --cov-report=html
```

Execute high-throughput batch simulation benchmarks:

```bash
python simulator.py --tasks 1000 --concurrency 8
```

---

## 📁 Project Structure

```
westgard-qc-evaluator/
├── westgard_qc.py          # Core Westgard multirule evaluation engine
├── cli.py                  # Command-line interface
├── simulator.py            # High-throughput simulation benchmark
├── enrichment.py           # Enrichment feature suite
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Build configuration
├── Dockerfile              # Container build definition
├── docker-compose.yml      # Container orchestration
├── benchmark_dataset.json  # Golden benchmark test cases
├── agents/
│   ├── __init__.py         # Package init
│   ├── base.py             # PHI guard, HMAC audit trail, security
│   ├── models.py           # Pydantic data models
│   ├── supervisor.py       # Multi-agent orchestration
│   ├── workers.py          # Specialized worker agents
│   ├── api.py              # FastAPI REST endpoints
│   ├── llm_factory.py      # LLM integration (mock, Ollama, Claude, GPT)
│   ├── learning.py         # Bayesian calibration engine
│   ├── metrics.py          # Prometheus metrics exporter
│   └── streamer.py         # WebSocket telemetry broadcaster
├── tests/
│   ├── test_westgard_qc_evaluator.py  # Agent framework tests
│   ├── test_westgard_core.py          # Core algorithm & security tests
│   └── test_enrichment.py             # Enrichment module tests
└── web/
    └── index.html          # Web dashboard
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
