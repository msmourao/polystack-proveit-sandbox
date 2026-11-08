"""Throwaway Docker sandbox — host orchestrates; container never sees secrets."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "polystack-proveit-runner:local")
SANDBOX_TIMEOUT_SEC = float(os.getenv("SANDBOX_TIMEOUT_SEC", "5"))
SANDBOX_MEMORY = os.getenv("SANDBOX_MEMORY", "128m")
SANDBOX_CPUS = os.getenv("SANDBOX_CPUS", "0.5")


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    contained: bool
    timed_out: bool
    oom_killed: bool
    network_blocked_signal: bool
    attempt_hash: str
    runner_error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _looks_like_network_attempt(stderr: str, stdout: str) -> bool:
    blob = f"{stderr}\n{stdout}".lower()
    needles = (
        "network is unreachable",
        "name or service not known",
        "nodename nor servname",
        "failed to establish a new connection",
        "connection refused",
        "temporary failure in name resolution",
        "errno 101",
        "errno -2",
        "errno -3",
        "gaierror",
        "urlopen error",
    )
    return any(n in blob for n in needles)


def run_python_in_sandbox(code: str) -> SandboxResult:
    """Run user Python inside a disposable, locked-down container."""
    attempt_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]

    if not _docker_available():
        return SandboxResult(
            stdout="",
            stderr="docker CLI not found on host PATH",
            exit_code=127,
            duration_ms=0,
            contained=False,
            timed_out=False,
            oom_killed=False,
            network_blocked_signal=False,
            attempt_hash=attempt_hash,
            runner_error="docker_missing",
        )

    with tempfile.TemporaryDirectory(prefix="proveit-") as tmp:
        work = Path(tmp)
        script = work / "user_code.py"
        script.write_text(code, encoding="utf-8")

        # Bind-mount only the script file as read-only into /work/user_code.py
        # Workdir is /work; /tmp is writable tmpfs for read-only rootfs.
        cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            SANDBOX_MEMORY,
            "--memory-swap",
            SANDBOX_MEMORY,
            "--cpus",
            SANDBOX_CPUS,
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--user",
            "10001:10001",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--pids-limit",
            "64",
            "-v",
            f"{script.resolve()}:/work/user_code.py:ro",
            "-w",
            "/work",
            # Do NOT forward host env / secrets into the container.
            "-e",
            "HOME=/tmp",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            SANDBOX_IMAGE,
            "python",
            "/work/user_code.py",
        ]

        t0 = time.perf_counter()
        timed_out = False
        oom_killed = False
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=SANDBOX_TIMEOUT_SEC + 1.5,
                encoding="utf-8",
                errors="replace",
            )
            exit_code = int(proc.returncode)
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            # Docker often uses 137 for SIGKILL (OOM / kill)
            if exit_code in (137, 139):
                oom_killed = "oom" in stderr.lower() or exit_code == 137
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = ((exc.stderr or "") if isinstance(exc.stderr, str) else "") + (
                f"\n[host] sandbox timeout after {SANDBOX_TIMEOUT_SEC}s — container killed"
            )
            # Best-effort: docker run --rm should clean up; also try prune dangling.
            subprocess.run(
                ["docker", "ps", "-q", "--filter", f"ancestor={SANDBOX_IMAGE}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            return SandboxResult(
                stdout="",
                stderr="docker CLI not found",
                exit_code=127,
                duration_ms=0,
                contained=False,
                timed_out=False,
                oom_killed=False,
                network_blocked_signal=False,
                attempt_hash=attempt_hash,
                runner_error="docker_missing",
            )
        except Exception as exc:  # noqa: BLE001 — surface host orchestration failures
            return SandboxResult(
                stdout="",
                stderr=str(exc),
                exit_code=1,
                contained=False,
                timed_out=False,
                oom_killed=False,
                network_blocked_signal=False,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                attempt_hash=attempt_hash,
                runner_error="docker_orchestrate_failed",
            )

        duration_ms = int((time.perf_counter() - t0) * 1000)
        network_signal = _looks_like_network_attempt(stderr, stdout)

        return SandboxResult(
            stdout=stdout[-50_000:],
            stderr=stderr[-50_000:],
            exit_code=exit_code,
            duration_ms=duration_ms,
            contained=True,
            timed_out=timed_out,
            oom_killed=oom_killed,
            network_blocked_signal=network_signal,
            attempt_hash=attempt_hash,
            runner_error=None,
        )
