# Phase 2 — local implementation

## Installation

1. Copy `profile.example.json` to `profile.json` and verify every employer, date, skill, and achievement. Never include unverified claims.
2. Copy `.env.example` to `.env`; set `AGENT_API_KEY` and `OPENAI_API_KEY`.
3. Run `docker compose up --build -d`. Check `http://localhost:8000/health`.
4. Edit `config.json` with actual Greenhouse and Lever board slugs.
5. Call `POST /discover`, `GET /jobs` and `POST /evaluate/{job_id}` with the `x-agent-key` header.

Generated PDFs are stored in `./drafts`, excluded from Git.

## Constraints

- LLM evaluation is implemented but has not been tested live with the user's API key.
- Ambiguous work authorization or sponsorship routes to review.
- A result marked approved is **not** a submitted application.
- Experience bullets are preserved from the verified profile; the model writes only the summary and selects verified skills.
- Automatic submission, LinkedIn/Indeed integration, and Gmail synchronization are **not implemented**.
- Public Greenhouse and Lever job listings do not grant permission to post applications.
- n8n's included workflow triggers discovery only, every six hours. n8n and the Docker API must be reachable on the same network.
- Keep port 8000 bound to loopback; use strong secrets and never commit real applicant data.

## Future submission adapters

Adapters must use supported, permitted integration methods; validate all application fields; explicitly record candidate consent; implement idempotency and a daily cap; capture confirmation receipts; stop at CAPTCHA or unusual declarations; and route errors to human review.
