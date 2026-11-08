"""Non-negotiable verdict contract — sandbox failure always REFUSED."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .llm import ClaimAssessment
from .sandbox import SandboxResult


@dataclass
class Verdict:
    status: str  # APPROVED | REFUSED
    reason: str
    contained: bool
    attempt_hash: str
    llm_provider: str
    llm_rationale: str

    def to_dict(self) -> dict:
        return asdict(self)


def decide_verdict(sandbox: SandboxResult, assessment: ClaimAssessment) -> Verdict:
    """
    APPROVED only if:
      contained=true AND exit_code=0 AND not timeout/OOM AND claim_supported.
    Any sandbox failure => REFUSED regardless of LLM prose.
    """
    if not sandbox.contained:
        return Verdict(
            status="REFUSED",
            reason=f"Sandbox orchestration failed ({sandbox.runner_error or 'not_contained'}).",
            contained=False,
            attempt_hash=sandbox.attempt_hash,
            llm_provider=assessment.provider,
            llm_rationale=assessment.rationale,
        )

    if sandbox.timed_out:
        return Verdict(
            status="REFUSED",
            reason="Sandbox timeout — container killed; no proof accepted.",
            contained=True,
            attempt_hash=sandbox.attempt_hash,
            llm_provider=assessment.provider,
            llm_rationale="Ignored: timeout forces REFUSED.",
        )

    if sandbox.oom_killed:
        return Verdict(
            status="REFUSED",
            reason="Sandbox OOM/kill (e.g. exit 137) — containment held; claim refused.",
            contained=True,
            attempt_hash=sandbox.attempt_hash,
            llm_provider=assessment.provider,
            llm_rationale="Ignored: OOM forces REFUSED.",
        )

    if sandbox.exit_code != 0:
        extra = ""
        if sandbox.network_blocked_signal:
            extra = " Network/exfil attempt appears blocked by --network none."
        return Verdict(
            status="REFUSED",
            reason=f"Sandbox exit_code={sandbox.exit_code}.{extra} Automatic REFUSED.",
            contained=True,
            attempt_hash=sandbox.attempt_hash,
            llm_provider=assessment.provider,
            llm_rationale="Ignored: non-zero exit forces REFUSED.",
        )

    if not assessment.claim_supported:
        return Verdict(
            status="REFUSED",
            reason="Sandbox succeeded but evidence is insufficient for the claim.",
            contained=True,
            attempt_hash=sandbox.attempt_hash,
            llm_provider=assessment.provider,
            llm_rationale=assessment.rationale,
        )

    return Verdict(
        status="APPROVED",
        reason="Sandbox contained run succeeded and evidence supports the claim.",
        contained=True,
        attempt_hash=sandbox.attempt_hash,
        llm_provider=assessment.provider,
        llm_rationale=assessment.rationale,
    )
