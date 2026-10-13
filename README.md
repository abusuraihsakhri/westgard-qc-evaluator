# Westgard QC Evaluator

Evaluate laboratory quality-control measurements against the Westgard 1-2s, 1-3s, 2-2s, R-4s, 4-1s and 10x rules.

## Browser application

The standalone evaluator is in [web/](web/). It accepts observations and established statistics as CSV, evaluates each run, displays a Levey–Jennings-style standardized plot, and exports CSV or JSON reports. It works without a backend, external APIs or file uploads. Sample data are available from **Load example**.

GitHub Pages deployment is configured by [.github/workflows/pages.yml](.github/workflows/pages.yml); the public URL should only be advertised once deployment is verified.

### CSV input

Observations:

```csv
run,level,value
1,Level1,100
1,Level2,201
2,Level1,112
2,Level2,200
```

Established control statistics:

```csv
level,mean,sd
Level1,100,5
Level2,200,10
```

Provide **independently established**, finite means and positive SDs for every control level. Duplicate run/level observations, duplicate statistics levels, missing values and non-finite measurements are rejected.

## Rules implemented

| Rule | Outcome | Scope |
| --- | --- | --- |
| 1-2s | Warning | One observation at or beyond ±2 SD (below 3 SD) |
| 1-3s | Reject | One observation at or beyond ±3 SD |
| 2-2s | Reject | Two levels beyond the same ±2 SD side in one run, or one level in two consecutive runs |
| R-4s | Reject | Two levels in one run, one ≥+2 SD and one ≤−2 SD, spanning at least 4 SD |
| 4-1s | Reject | Four consecutive observations of one level at or beyond the same ±1 SD side |
| 10x | Reject | Ten consecutive observations of one level strictly on the same side of the mean |

Runs are processed in ascending numeric run order. A missing level breaks its across-run consecutive sequence; the evaluator does not bridge such gaps. This implementation evaluates 4-1s and 10x independently per level and does **not** implement all possible cross-level sequential variants of multirule QC.

The application is a screening and educational aid. It does not authorize patient-result release, establish laboratory-specific control limits, or replace validated SOPs.

## Python CLI

Requires Python 3.10 or later:

```sh
python -m pip install -e '.[test]'
python westgard_qc.py --data examples/qc_data.csv --stats examples/qc_stats.csv
python westgard_qc.py --data examples/qc_data.csv --stats examples/qc_stats.csv --json results.json --plot chart.png
python -m pytest -v
node --test web/test-qc.cjs
```

Run locally as a static website:

```sh
python -m http.server 8001 --directory web
```

Then open `http://localhost:8001/` in a browser. The browser evaluator uses JavaScript for speed and compatibility; it does not execute Python through Pyodide.

**Caution:** If `--stats` is omitted, the CLI computes sample mean/SD from the evaluated observations. That mode is suitable for exploratory demonstration, **not** independent QC assessment.

## Python REST service

```sh
python cli.py serve --host 127.0.0.1 --port 8000
```

The dedicated `POST /api/qc/evaluate` endpoint applies the same Westgard Python evaluator as the CLI:

```json
{
  "observations": [{"run": 1, "level": "Level1", "value": 112.0}],
  "statistics": [{"level": "Level1", "mean": 100, "sd": 5}]
}
```

The pre-existing `/api/audit`, `/api/chat` and agent-based `cli.py audit` commands are retained for compatibility, but use independent, generic heuristic rules; **their results must not be interpreted as Westgard QC evaluation**. Mock provider responses are not actual LLM integration.

### Containers and security

```sh
export AUDIT_SECRET_KEY='replace-with-a-unique-strong-secret'
docker compose up --build
```

In production (`APP_ENV=production`), the server fails to start without `AUDIT_SECRET_KEY`. The audit trail computes HMAC-SHA256 signatures over event metadata; it is **in-memory**, not a persistent compliance-grade ledger. The optional identifier regex guard is not a complete PHI de-identification method. Do not expose the unauthenticated agent API on a public network or process clinical identifiers without appropriate institutional controls.

The static web app does not send data to any server, use external fonts or analytics, or persist data in browser storage. Generated downloads remain local to the browser.

## Project layout

- `westgard_qc.py` — multirule evaluator, CSV parser and optional Levey–Jennings PNG.
- `web/` — static browser evaluator, rendering and standalone Node tests.
- `agents/api.py` — FastAPI service with dedicated QC endpoint plus legacy agent endpoints.
- `cli.py`, `agents/`, `enrichment.py`, `simulator.py` — legacy agent and simulation interfaces.
- `tests/`, `test_westgard_qc.py` — Python tests.
- `.github/workflows/` — Python/browser CI and GitHub Pages deployment.

## License

[MIT](LICENSE).
