"""Submission boundary: no arbitrary browser clicking or unsanctioned POSTs.
Adapters must be implemented per ATS with documented authorization and confirmation.
"""
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class SubmissionRequest:
    job_id: str
    application_url: str
    resume_path: str
    applicant_email: str
    answers: dict
    consent: bool

@dataclass(frozen=True)
class SubmissionReceipt:
    success: bool
    provider: str
    confirmation_id: str | None = None
    message: str = ''

class SubmissionAdapter(Protocol):
    def supports(self, url: str) -> bool: ...
    def validate(self, request: SubmissionRequest) -> list[str]: ...
    def submit(self, request: SubmissionRequest) -> SubmissionReceipt: ...

class ReviewOnlyAdapter:
    """Safe default for Greenhouse, Lever, LinkedIn, Indeed, and unknown forms."""
    def supports(self, url: str) -> bool: return False
    def validate(self, request: SubmissionRequest) -> list[str]:
        return ['No authorized submission integration configured']
    def submit(self, request: SubmissionRequest) -> SubmissionReceipt:
        return SubmissionReceipt(False,'review-only',message='Manual review required; nothing submitted')

# Future adapters must enforce: domain allowlist; website authorization;
# validated answers; no CAPTCHA bypass; per-day cap; idempotency key;
# atomic claim before submission; confirmation ID / receipt verification;
# redacted audit logging; error => review, never blind retry.
