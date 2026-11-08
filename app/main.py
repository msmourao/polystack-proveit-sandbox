"""Prove-It Control Plane — FastAPI host (secrets stay here; code runs in sandbox)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .llm import get_llm_provider
from .sandbox import run_python_in_sandbox
from .verifier import decide_verdict

ROOT = Path(__file__).resolve().parents[1]
# Sandbox .env wins over inherited host/workspace keys (e.g. a personal OPENAI_API_KEY
# that would otherwise force OpenAICompatibleProvider → 401 on api.openai.com).
load_dotenv(ROOT / ".env", override=True)

app = FastAPI(
    title="PolyStack Prove-It Sandbox",
    description="Blast Radius Zero MVP — local-first containment control plane.",
    version="0.1.0",
)

static_dir = ROOT / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class RunRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=80_000)
    claim: str = Field(..., min_length=1, max_length=4_000)
    mode: str = Field(default="prove", description="prove | attack")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "sandbox_image": os.getenv("SANDBOX_IMAGE", "polystack-proveit-runner:local"),
        "llm": type(get_llm_provider()).__name__,
    }


@app.post("/api/run")
def run(req: RunRequest) -> dict:
    code = req.code
    if req.mode == "attack":
        # Fixed containment-moment payload (UI may also send its own).
        code = _MALICIOUS_DEMO

    sandbox = run_python_in_sandbox(code)
    llm = get_llm_provider()
    assessment = llm.assess_claim(
        code=code,
        claim=req.claim,
        stdout=sandbox.stdout,
        stderr=sandbox.stderr,
        exit_code=sandbox.exit_code,
    )
    verdict = decide_verdict(sandbox, assessment)

    return {
        "claim": req.claim,
        "mode": req.mode,
        "sandbox": sandbox.to_dict(),
        "assessment": {
            "claim_supported": assessment.claim_supported,
            "rationale": assessment.rationale,
            "provider": assessment.provider,
        },
        "verdict": verdict.to_dict(),
    }


_MALICIOUS_DEMO = r'''
# Containment Moment — tries to read secrets + open the network.
import os, sys, urllib.request

print("ATTACK: listing env keys", flush=True)
print(sorted(os.environ.keys()), flush=True)
secretish = {k: v for k, v in os.environ.items() if any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}
print("ATTACK: secret-like envs", secretish, flush=True)

print("ATTACK: fetching https://example.com", flush=True)
try:
    with urllib.request.urlopen("https://example.com", timeout=3) as r:
        print("LEAK_OK", r.status, flush=True)
        sys.exit(0)
except Exception as e:
    print("ATTACK_BLOCKED", type(e).__name__, e, flush=True)
    sys.exit(2)
'''
