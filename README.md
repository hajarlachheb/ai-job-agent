# AI Job Agent

Python + n8n job discovery, deduplication, AI matching, eligibility review, ATS-friendly resume PDFs, and tracking.

> **Development foundation — not an auto-apply bot yet.** Application submission is deliberately disabled until permitted, validated provider adapters are implemented.

## Features

- Greenhouse and Lever public job-listing discovery (board slugs configured in `config.json`).
- SQLite persistence, stable per-source identifiers, and event tracking.
- Heuristic ranking and optional OpenAI structured assessment grounded in a private, verified candidate profile.
- Conservative eligibility/sponsorship gate: unknown facts go to review, never automatic submission.
- ATS-friendly PDF resume output, with verified employment bullets copied from the profile.
- Local FastAPI endpoints, Docker Compose, n8n six-hour discovery schedule, and six policy tests.
- Review-only submission adapter boundary. Never bypass CAPTCHA or restricted websites.

## Quick start (local computer)

```bash
git clone https://github.com/hajarlachheb/ai-job-agent.git
cd ai-job-agent
cp .env.example .env
cp profile.example.json profile.json
# Edit .env, profile.json, config.json with your private, verified information
docker compose up --build -d
curl http://localhost:8000/health
curl -X POST http://localhost:8000/discover -H "x-agent-key: YOUR_SECRET"
curl http://localhost:8000/jobs -H "x-agent-key: YOUR_SECRET"
```

To assess an individual job after discovery:

```bash
curl -X POST http://localhost:8000/evaluate/JOB_ID -H "x-agent-key: YOUR_SECRET"
```

Resumes are saved to `./drafts/`. The agent requires an OpenAI API key and a verified `profile.json` before evaluation.

## API

| Route | Function |
| --- | --- |
| `GET /health` | Health check |
| `POST /discover` | Fetch and deduplicate configured listings |
| `GET /jobs` | Inspect jobs and statuses |
| `POST /evaluate/{job_id}` | Structured matching, conservative policy, PDF |
| `POST /prepare/{job_id}` | Draft-only Markdown preparation |
| `POST /jobs/{job_id}/decision` | Update review/approval/other states; cannot self-certify submission |
| `GET /stats` | Status counts |

Except for `/health`, endpoints require the `x-agent-key` header.

## n8n

Import `n8n-workflow.json`. It expects the API at `http://agent:8000` (same Docker network) and an `AGENT_API_KEY` variable in n8n. If n8n runs separately, set the HTTP node to a privately reachable local API URL. The workflow currently runs **discovery only**. Keep n8n and Docker running for scheduled operation.

## Tests

```bash
pip install -r requirements.txt pytest
pytest -q
```

## Security

`.env`, `profile.json`, databases, generated PDFs, and `drafts/` are excluded via `.gitignore`. Never commit applicant data, API credentials, or sensitive records. Limit access to the API; Compose binds only to 127.0.0.1.

## Roadmap

- Cross-source deduplication and robust posting freshness checks
- Batch LLM evaluations with rate and budget controls
- Provider-specific submission adapters with verified authorization, field mapping, idempotency, quotas, receipts, and review fallback
- Gmail response reconciliation, dashboard, and improved n8n orchestration
- LinkedIn/Indeed support only via permitted workflows

See [PHASE2.md](PHASE2.md) for details and limits.

## Scheduled AI evaluation (Phase 3 foundation)

The `POST /pipeline/run` endpoint performs discovery and evaluates at most **3 new high-scoring jobs per trigger**, with a persistent **12 LLM assessments per UTC day** cap. A failed evaluation moves into review and will not automatically retry. It does not submit any application.

After `git pull` and `docker compose up --build -d`, test it manually:

```powershell
$headers = @{ "x-agent-key" = "YOUR_SECRET" }
Invoke-RestMethod -Method Post -Uri http://localhost:8000/pipeline/run -Headers $headers
Invoke-RestMethod -Uri http://localhost:8000/stats -Headers $headers
```

**n8n networking:** The imported workflow points to `http://agent:8000`, which works **only when n8n runs on the same Docker network as the agent**. If n8n is in another Docker Compose project on Windows with Docker Desktop, change the HTTP node URL to `http://host.docker.internal:8000/pipeline/run`, and ensure the API is reachable from that container (the default API is loopback-bound, so you may need an explicit shared Docker network instead). If n8n runs directly on the host, use `http://localhost:8000/pipeline/run`. The n8n variable `AGENT_API_KEY` must be set in n8n's environment.

Open the n8n workflow, test a manual execution, inspect the result, and only then activate the schedule. Keep your computer, Docker Desktop and n8n running. The daily LLM assessment cap limits calls, **not monetary spending**, which depends on model and token usage. Set an API billing limit separately. This workflow does not import your CV automatically: populate `profile.json` with your verified experience first.
