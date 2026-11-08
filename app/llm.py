"""Pluggable LLM adapter — Mock by default; OpenAI-compatible for Vultr Inference."""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ClaimAssessment:
    """Advisory only — never overrides sandbox failure into APPROVED."""

    claim_supported: bool
    rationale: str
    provider: str


class LLMProvider(ABC):
    @abstractmethod
    def assess_claim(
        self,
        *,
        code: str,
        claim: str,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> ClaimAssessment:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """Deterministic local assessor — no network, no keys."""

    def assess_claim(
        self,
        *,
        code: str,
        claim: str,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> ClaimAssessment:
        if exit_code != 0:
            return ClaimAssessment(
                claim_supported=False,
                rationale="Sandbox exit_code != 0 — claim cannot be supported.",
                provider="mock",
            )

        claim_l = (claim or "").lower()
        out_l = (stdout or "").lower()

        # Happy-path demo: look for explicit PROVED / PASS markers from user tests.
        if re.search(r"\b(proved|pass(ed)?|ok|assert.?ok)\b", out_l):
            return ClaimAssessment(
                claim_supported=True,
                rationale="Stdout contains an explicit proof/pass marker.",
                provider="mock",
            )

        # Soft heuristic: claim keywords appear in stdout (weak — still requires exit 0).
        tokens = [t for t in re.findall(r"[a-z0-9_]{3,}", claim_l) if t not in {"the", "and", "that"}]
        hits = sum(1 for t in tokens if t in out_l)
        if tokens and hits >= max(1, len(tokens) // 2):
            return ClaimAssessment(
                claim_supported=True,
                rationale=f"Stdout overlaps claim keywords ({hits}/{len(tokens)}).",
                provider="mock",
            )

        return ClaimAssessment(
            claim_supported=False,
            rationale="No sufficient evidence in stdout to support the claim (mock assessor).",
            provider="mock",
        )


class OpenAICompatibleProvider(LLMProvider):
    """Vultr Serverless Inference / any OpenAI-compatible chat completions API."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def assess_claim(
        self,
        *,
        code: str,
        claim: str,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> ClaimAssessment:
        import httpx

        if exit_code != 0:
            # Hard rule mirrored here — do not ask the model to "save" a failed run.
            return ClaimAssessment(
                claim_supported=False,
                rationale="Sandbox exit_code != 0 — automatic refuse (LLM not consulted).",
                provider="openai-compatible",
            )

        system = (
            "You are an evidence auditor for a Prove-It sandbox. "
            "Answer ONLY whether the sandbox stdout/stderr supports the user's claim. "
            "If evidence is missing or ambiguous, say UNSUPPORTED. "
            "Reply with exactly two lines:\n"
            "VERDICT: SUPPORTED|UNSUPPORTED\n"
            "WHY: <one short sentence>"
        )
        user = (
            f"CLAIM:\n{claim}\n\n"
            f"CODE:\n{code[:4000]}\n\n"
            f"EXIT_CODE: {exit_code}\n"
            f"STDOUT:\n{stdout[:4000]}\n"
            f"STDERR:\n{stderr[:2000]}\n"
        )
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
            text = data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            return ClaimAssessment(
                claim_supported=False,
                rationale=f"LLM assessor failed ({exc}); refusing for insufficient evidence.",
                provider="openai-compatible",
            )

        supported = bool(re.search(r"VERDICT:\s*SUPPORTED", text, re.I))
        why_m = re.search(r"WHY:\s*(.+)", text, re.I)
        why = why_m.group(1).strip() if why_m else text.strip()[:240]
        return ClaimAssessment(
            claim_supported=supported,
            rationale=why,
            provider="openai-compatible",
        )


def get_llm_provider() -> LLMProvider:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()
    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    # Empty key OR empty base_url → Mock. Never silently default to api.openai.com.
    if not api_key or not base_url:
        return MockLLMProvider()
    return OpenAICompatibleProvider(api_key=api_key, base_url=base_url, model=model)
