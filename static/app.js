const $ = (id) => document.getElementById(id);

async function refreshHealth() {
  try {
    const r = await fetch("/api/health");
    const j = await r.json();
    $("healthPill").textContent = `LLM: ${j.llm} · image ready`;
  } catch {
    $("healthPill").textContent = "API offline";
  }
}

function setBusy(busy) {
  $("btnProve").disabled = busy;
  $("btnAttack").disabled = busy;
  if (busy) {
    $("verdict").className = "verdict running";
    $("verdict").textContent = "Running in Strongbox…";
  }
}

function render(result) {
  const v = result.verdict;
  const s = result.sandbox;
  $("verdict").className = `verdict ${v.status}`;
  $("verdict").textContent = `${v.status} — ${v.reason}`;
  $("hash").textContent = s.attempt_hash || "—";
  $("duration").textContent = `${s.duration_ms} ms`;
  $("exit").textContent = String(s.exit_code);
  $("contained").textContent = String(s.contained);
  $("llm").textContent = `${result.assessment.provider}: ${result.assessment.rationale}`;
  $("stdout").textContent = s.stdout || "(empty)";
  $("stderr").textContent = s.stderr || "(empty)";
  $("reason").textContent = v.reason;
}

async function run(mode) {
  setBusy(true);
  try {
    const body = {
      mode,
      claim: $("claim").value,
      code: $("code").value,
    };
    const r = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || r.statusText);
    render(j);
  } catch (err) {
    $("verdict").className = "verdict REFUSED";
    $("verdict").textContent = `REFUSED — ${err.message || err}`;
  } finally {
    setBusy(false);
  }
}

$("btnProve").addEventListener("click", () => run("prove"));
$("btnAttack").addEventListener("click", () => run("attack"));
refreshHealth();
