# polystack-proveit-sandbox

Public, standalone MVP for **Vultr Agent Rush — Challenge 1: Blast Radius Zero**.

Prove-It control plane: the host plans/assesses; **user code runs only inside a throwaway Docker sandbox** with no network and no host secrets. Verdicts are evidence-gated — a failed sandbox is always **REFUSED**, even if an LLM would prefer nicer prose.

## Architecture

```
Browser UI  →  FastAPI host on Vultr Cloud Compute (secrets + LLM adapter)
                    │
                    │  LLM calls → Vultr Serverless Inference
                    │              (https://api.vultrinference.com/v1)
                    ▼
              docker run --rm --network none --read-only …  (on the same VM)
                    │
                    ▼
              Receipt: stdout/stderr/exit/hash + APPROVED|REFUSED
```

- **Host:** `app/main.py`, `app/llm.py`, `app/verifier.py`
- **Sandbox:** `app/sandbox.py` + image from `runner/Dockerfile`
- **UI:** `static/` — happy path + **Containment Moment** (malicious env/network attempt)

## How we use Vultr (judging signal)

Challenge 1 scores **visible Vultr usage** roughly as hard as the idea. This project treats Vultr as the **control plane**, not wallpaper:

| Surface | Role in Prove-It |
|--------|-------------------|
| **Vultr Cloud Compute (Shared CPU)** | Runs FastAPI + Docker. Public demo URL points here. |
| **Vultr Serverless Inference** | All agent/assessor LLM calls via OpenAI-compatible API (`OPENAI_BASE_URL=https://api.vultrinference.com/v1`). No GPU. |
| **Docker sandbox on that VM** | Throwaway `--network none` runs. Secrets never enter the container. |
| **Receipt** | `attempt_hash`, exit code, `contained`, verdict — proof of a real run, not chat. |

**Localhost (`127.0.0.1`) is for development only.** Submission video and LabLab demo URL should use the **public Vultr IP/hostname**.

### Cloud proof (what to show judges)

Stamp the run as cloud-side:

1. **Public demo URL** on the Vultr instance (firewall: 80/443 or 8080).
2. **Video**: browser address bar shows the Vultr host (not localhost) during Containment Moment + happy path.
3. **`GET /api/health`**: shows `OpenAICompatibleProvider` + Inference base URL when keys are set.
4. **Optional 5s cut**: Vultr console with the Compute instance running + Remaining Credit.
5. **Optional README badge**: region + instance plan (e.g. `vc2-1c-1gb`, `ewr`).

Optional extra (only if time): Vultr Community showcase post — **does not replace** LabLab submission.

### Degreed in the pitch (process color, not infra)

**Degreed is not Vultr proof** and is **not** a judging criterion for Agent Rush. Using it as “we ran in the cloud” is wrong.

Using it as **one sentence of process / business narrative** can help *Presentation* and *Business Value* **only if** it serves the product thesis:

> LXP/skills surfaces declare capability; Prove-It on Vultr verifies execution was contained — same honesty loop, runtime side.

Rules for the video/slides:

- **At most one line** (or one slide footnote). No Degreed walkthrough, screenshots of certificates, or “we use Degreed” as a tech-stack bullet next to Vultr.
- Prefer **Degreed-shaped / evidence loop** language over “we integrate Degreed” unless you have a live artefact for that claim.
- If the line does not make Containment Moment clearer, cut it — clarity beats enterprise name-drop.

### Out of band / skip

- Degreed profiles or learning certificates as “cloud proof”
- Degreed as a primary slide / majority of the presentation
- GPU instances (not available / not needed for C1)
- Hosting the control plane elsewhere and only “mentioning” Vultr

## Prerequisites

- Python 3.11+
- Docker Desktop / Docker Engine (CLI on `PATH`)

## Setup

```bash
cd polystack-proveit-sandbox
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# If you also use LifeGraph SWE tooling, clear inherited site-packages:
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

# macOS/Linux
# source .venv/bin/activate
# unset PYTHONPATH

pip install -r requirements.txt
copy .env.example .env   # or: cp .env.example .env
```

Leave `OPENAI_API_KEY` empty to use the **MockLLMProvider** (no credentials).

### Build the sandbox runner image

```bash
docker build -t polystack-proveit-runner:local ./runner
```

### Run the control plane

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:8080

## Local test script

1. **Happy path** — keep the default sort example → click **Run in Strongbox (Sandbox)** → expect **APPROVED**, `contained=true`, `exit_code=0`, stdout with `PROVED`.
2. **Containment Moment** — click **Simulate Malicious Attack (Exfil Envs/Network)** → expect **REFUSED**, `contained=true`, non-zero exit (`124` timeout kill and/or `ATTACK_BLOCKED` / exit `2`). Host secrets are not injected; image env like `GPG_KEY` may appear — that is container base, not host exfil.
3. **Health** — `GET /api/health` shows `MockLLMProvider` when key/base URL empty, or `OpenAICompatibleProvider` when Vultr Inference is configured. Empty sandbox `.env` **overrides** inherited host `OPENAI_*` so a personal OpenAI key cannot silently 401 the demo.

### Optional: Vultr / OpenAI-compatible LLM

In `.env`:

```env
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.vultrinference.com/v1
OPENAI_MODEL=your-model-id
```

Restart uvicorn. Sandbox failures still **REFUSED** without consulting the model for a “save”.

## Non-goals (v0)

Playwright browser sandbox, GPU, multi-tenant auth, Challenge 2 enterprise workflows, LifeGraph/Path2 internals.

## License

MIT (intended for public hackathon submission surface).
