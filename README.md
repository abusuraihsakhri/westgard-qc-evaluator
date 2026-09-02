# Westgard Qc Evaluator

> **Domain:** Clinical Decision Support & Biomedical Computing  
> **Reference Guidelines & Standards:** `Standard Clinical Formulations & ISO/IEC Quality Frameworks`

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

---

## ⚙️ Key Capabilities & Algorithmic Modules

### 🔬 Core Algorithmic & Evaluation Engines

- **`Observation`** — dedicated module for observation evaluation and state verification.
- **`Violation`** — dedicated module for violation evaluation and state verification.
- **`RunResult`** — dedicated module for run result evaluation and state verification.

---

## 💻 CLI Quickstart & Usage

### 1. Guided Interactive Mode
```bash
python cli.py
```

### 2. Direct Parameterized Evaluation
```bash
python cli.py --task-id <value> --target <value> --primary <value> --secondary <value>
```

### Parameter Reference
- `--task-id`: Specifies input measurement or parameter value.
- `--target`: Specifies input measurement or parameter value.
- `--primary`: Specifies input measurement or parameter value.
- `--secondary`: Specifies input measurement or parameter value.
- `--critical`: Specifies input measurement or parameter value.
- `--status`: Specifies input measurement or parameter value.
- `--input`: Specifies input measurement or parameter value.
- `--output`: Specifies input measurement or parameter value.

### Input Data Schema

| Field | Description | Requirement |
|:------|:------------|:------------|
| `suite_name` | Parameter / observation metric | Required |
| `system_slug` | Parameter / observation metric | Required |
| `standard_reference` | Parameter / observation metric | Required |
| `test_cases` | Parameter / observation metric | Required |

---

## 🛡️ Security & Enterprise Architecture

* **Zero-PHI Outbound Interceptor:** Active AST and regex inspection blocking SSNs, MRNs, phone numbers, and patient identifiers.
* **Tamper-Evident HMAC-SHA256 Audit Trail:** Chained, cryptographically signed logs for every evaluation and state transition.
* **Air-Gapped LLM Reasoning Adapter:** Agnostic integration for local Ollama instances (`llama3`, `mistral`), Claude 3.5 Sonnet, GPT-4o, and deterministic test mocks.
* **Active Learning Bayesian Calibration:** Dynamic tracker updating worker reliability weights and monitoring Brier calibration drift.
* **FastAPI & Prometheus Telemetry:** Exposes OpenAPI 3.1 REST endpoints and operational Prometheus metrics (`/metrics`).

---

## 🧪 Testing & Verification

Run the automated test suite:

```bash
pytest -v
```

Execute high-throughput batch simulation benchmarks:

```bash
python simulator.py --tasks 1000 --concurrency 8
```

---

## 🐳 Container Deployment

```bash
docker build -t westgard-qc-evaluator .
docker run -p 8000:8000 westgard-qc-evaluator
```
