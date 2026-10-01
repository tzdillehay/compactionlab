const $ = (id) => document.getElementById(id);
const labels = {
  full_history: "Full history",
  recent_history: "Recent history",
  summary: "LLM summary",
  plain: "Plain records",
  structured: "State + evidence",
  compact: "Compact shared sources",
  compact_fixed: "Compact · same selected records",
};
let activeJob = null;
let qualificationJob = null;
function inference(thinking) {
  return {
    thinking,
    context_tokens: 8192,
    max_output_tokens: thinking ? 6144 : 2048,
  };
}
function busy(value) {
  $("start").disabled = value;
  $("qualification-start").disabled = value;
}
async function api(path, body) {
  const response = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : JSON.stringify(result.detail),
    );
  return result;
}
function cell(row, text, className = "") {
  const td = document.createElement("td");
  td.textContent = text;
  td.className = className;
  row.append(td);
  return td;
}
function options(select, rows, selected) {
  select.replaceChildren();
  for (const [value, text] of rows) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    select.append(option);
  }
  if (selected) select.value = selected;
}
function element(tag, text, className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
}
function accuracy(value) {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}
function seconds(value) {
  return value === null ? "—" : `${value.toFixed(2)}s`;
}
function counted(value, singular, plural = `${singular}s`) {
  return `${value} ${value === 1 ? singular : plural}`;
}
async function openStudyRun(run) {
  try {
    if (run.kind === "qualification") {
      $("qualification-panel").open = true;
      await loadQualifications(run.id);
      $("qualification-panel").scrollIntoView({ block: "start" });
    } else {
      await loadRuns(run.id);
      $("results").scrollIntoView({ block: "start" });
    }
  } catch (error) {
    $("overview-status").textContent = error.message;
  }
}
function runButton(run, label = "Inspect ↗") {
  const button = element("button", label, "secondary-button");
  button.type = "button";
  button.setAttribute("aria-label", `${label} ${run.id}`);
  button.addEventListener("click", () => openStudyRun(run));
  return button;
}
async function loadOverview() {
  $("refresh-overview").disabled = true;
  try {
    const result = await api("/api/overview");
    const summary = result.summary;
    $("overview-status").textContent = summary.latest_at
      ? `Latest saved · ${new Date(summary.latest_at).toLocaleString()} · All saved history`
      : "No saved studies yet. Run a comparison to begin.";
    $("overview-metrics").replaceChildren();
    const headline = [
      ["Study types", summary.studies, "Current protocols"],
      [
        "Saved evaluations",
        summary.saved_probes,
        "Includes development runs & errors",
      ],
      [
        "Completed runs",
        summary.completed_runs,
        counted(summary.runs, "total saved run"),
      ],
      [
        "Model variants",
        summary.models.length,
        summary.models.join(" · ") || "No models tested yet",
      ],
    ];
    for (const [label, value, caption] of headline) {
      const card = element("div", "", "metric-card");
      card.append(
        element("span", label, "metric-label"),
        element("strong", value.toLocaleString(), "metric-value"),
        element("span", caption, "metric-caption"),
      );
      $("overview-metrics").append(card);
    }
    $("study-cards").replaceChildren();
    for (const study of result.studies) {
      const card = element("article", "", "study-card");
      const heading = element("div", "", "study-heading");
      heading.append(
        element("h2", study.title),
        element("span", counted(study.runs.length, "saved run"), "study-badge"),
      );
      card.append(
        heading,
        element("p", study.description, "study-description"),
      );
      const stats = element("div", "", "study-stats");
      const m = study.metrics;
      for (const [label, value] of [
        ["Evaluations", m.saved.toLocaleString()],
        ["Strict passes", `${m.passed} / ${m.saved}`],
        ["Fact accuracy", accuracy(m.mean_fact_accuracy)],
        ["Median response", seconds(m.median_receiver_seconds)],
      ]) {
        const stat = element("div", "");
        stat.append(
          element("span", label, "stat-label"),
          element("strong", value, "stat-value"),
        );
        stats.append(stat);
      }
      card.append(stats);
      const latest = study.runs[0];
      if (latest.encoding) {
        const e = latest.encoding;
        const reduction = e.same_selection_token_reduction;
        card.append(
          element(
            "p",
            `Latest run · Compact vs verbose: ${counted(e.wins, "win")}, ${counted(e.losses, "loss", "losses")}, ${counted(e.ties, "tie")}.${reduction ? ` Same records use ${(reduction[0] * 100).toFixed(1)}–${(reduction[1] * 100).toFixed(1)}% fewer history tokens.` : ""}`,
            "study-insight",
          ),
        );
      }
      const footer = element("div", "", "study-footer");
      footer.append(
        element(
          "span",
          `${counted(m.errors, "error")} · ${m.graded} graded · ${counted(m.timed_responses, "timed response")}`,
        ),
        runButton(latest, "View latest ↗"),
      );
      card.append(footer);
      const detail = element("details", "", "study-runs");
      detail.append(
        element("summary", `Run history · ${study.protocols.join(" · ")}`),
      );
      for (const run of study.runs) {
        const row = element("div", "", "study-run");
        const text = element("div", "");
        const r = run.metrics;
        text.append(
          element("span", run.setup),
          element(
            "span",
            `${run.id} · ${run.status} · ${run.published ? "published trace" : "local trace"}`,
          ),
          element(
            "span",
            `${r.passed}/${r.saved} strict passes · ${accuracy(r.mean_fact_accuracy)} facts · ${seconds(r.median_receiver_seconds)} median · ${r.errors} errors`,
          ),
        );
        if (run.workflow_gates) {
          const gates = Object.values(run.workflow_gates);
          text.append(
            element(
              "span",
              `${gates.filter(Boolean).length}/${gates.length} workflow gates met`,
            ),
          );
        }
        row.append(text, runButton(run));
        detail.append(row);
      }
      card.append(detail);
      $("study-cards").append(card);
    }
    $("development-archive").hidden = !result.development.length;
    $("development-title").textContent =
      `Earlier protocol runs · ${result.development.length}`;
    $("development-runs").replaceChildren();
    for (const run of result.development) {
      const row = document.createElement("tr");
      cell(row, `${run.id} · ${run.setup}`);
      cell(row, run.protocol);
      cell(row, `${run.metrics.passed} / ${run.metrics.saved}`);
      cell(row, run.metrics.errors);
      cell(row, "").append(runButton(run));
      $("development-runs").append(row);
    }
    $("overview-note").textContent =
      "Coverage totals include repeated checkpoints and all conditions. Strict passes count saved errors as failures; fact accuracy averages graded responses; response time is the median of measured receiver calls. Compare methods within the same run and allowance.";
  } catch (error) {
    $("overview-status").textContent = `Overview unavailable: ${error.message}`;
  } finally {
    $("refresh-overview").disabled = false;
  }
}
$("refresh-overview").addEventListener("click", loadOverview);
try {
  $("qualification-panel").open =
    localStorage.getItem("compactionlab.qualification.open") === "true";
} catch {
  /* Disclosure still works when browser storage is unavailable. */
}
$("qualification-panel").addEventListener("toggle", () => {
  try {
    localStorage.setItem(
      "compactionlab.qualification.open",
      String($("qualification-panel").open),
    );
  } catch {
    /* Disclosure still works when browser storage is unavailable. */
  }
});
$("qualification-nav").addEventListener("click", () => {
  $("qualification-panel").open = true;
});
async function loadModels() {
  try {
    const result = await api("/api/models");
    const rows = result.models.map((m) => [m.name, m.name]);
    options($("writer"), rows, "qwen3:4b");
    options($("reader"), rows, "qwen3:8b");
    options($("qualification-model"), rows, "qwen3:8b");
    $("connection").textContent = `${rows.length} local models available`;
    $("start").disabled = !rows.length;
    $("qualification-start").disabled = !rows.length;
  } catch (error) {
    $("connection").textContent = "Start Ollama to use local inference";
    $("status").textContent = error.message;
    $("start").disabled = true;
    $("qualification-start").disabled = true;
  }
}
async function loadRuns(preferred) {
  const rows = await api("/api/runs");
  options(
    $("runs"),
    rows.map((r) => [
      r.id,
      `${r.config.writer_model || "Frozen 4B memory"} → ${r.config.reader_model} · ${r.id}`,
    ]),
    preferred || rows[0]?.id,
  );
  if (rows.length) await showRun($("runs").value);
}
async function showRun(id) {
  const result = await api(`/api/runs/${id}`);
  const replay = result.protocol === "representation-v1";
  const allowance = replay
    ? `${result.config.budgets.join(", ")} historical tokens`
    : result.config.token_budget
      ? `${result.config.token_budget.toLocaleString()} historical tokens`
      : `${result.config.byte_budget.toLocaleString()} historical bytes`;
  $("run-meta").textContent =
    `${result.status} · ${result.protocol} · ${allowance} · ${result.trials.length}${replay ? `/${result.planned_trials}` : ""} probes saved · ${result.config.writer_model || result.frozen_writer?.name} → ${result.config.reader_model}`;
  $("replay-results").hidden = !replay;
  $("replay-totals").replaceChildren();
  if (replay) {
    const passCount = (rows) =>
      `${rows.filter((t) => t.status === "graded" && t.grade.passed).length}/${result.config.seeds.length}${rows.length < result.config.seeds.length ? ` · ${rows.length} saved` : ""}`;
    for (const task of result.cases) {
      for (const budget of result.config.budgets) {
        const row = document.createElement("tr");
        cell(row, task.case.replaceAll("_", " "));
        cell(row, budget);
        for (const condition of [
          "structured",
          "compact",
          "compact_fixed",
          "recent_history",
        ]) {
          cell(
            row,
            passCount(
              result.trials.filter(
                (t) =>
                  t.case === task.case &&
                  t.token_budget === budget &&
                  t.condition === condition,
              ),
            ),
          );
        }
        cell(
          row,
          passCount(
            result.trials.filter(
              (t) => t.case === task.case && t.condition === "full_history",
            ),
          ),
        );
        $("replay-totals").append(row);
      }
    }
  }
  $("totals").replaceChildren();
  for (const [condition, total] of Object.entries(result.totals || {})) {
    const row = document.createElement("tr");
    cell(row, labels[condition]);
    cell(
      row,
      `${total.passed} / ${total.graded}`,
      total.passed === total.graded && total.graded ? "pass" : "fail",
    );
    cell(
      row,
      total.mean_fact_accuracy === null
        ? "—"
        : `${Math.round(total.mean_fact_accuracy * 100)}%`,
    );
    cell(row, total.errors);
    $("totals").append(row);
  }
  $("trials").replaceChildren();
  for (const trial of result.trials) {
    const detail = document.createElement("details");
    const summary = document.createElement("summary");
    const passed = trial.grade?.passed;
    summary.textContent = `${trial.case} · ${labels[trial.condition]} · ${trial.status === "graded" ? (passed ? "PASS" : "FAIL") : trial.status} · ${replay ? `${trial.token_budget ?? "full"} tokens · seed ${trial.seed} · ` : ""}${trial.context_bytes ?? 0} bytes`;
    summary.className = passed ? "pass" : "fail";
    detail.append(summary);
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(
      {
        context: trial.context,
        answer: trial.model?.parsed,
        grade: trial.grade,
        error: trial.error,
        tokens: trial.model?.prompt_tokens,
        historical_tokens: trial.historical_tokens,
        output_tokens: trial.model?.output_tokens,
        prompt_accounting_match: trial.model?.prompt_accounting_match,
        wall_seconds: trial.model?.wall_seconds,
        record_ids: trial.retrieval?.record_ids || trial.record_ids,
        fidelity_verified: trial.fidelity_verified,
      },
      null,
      2,
    );
    detail.append(pre);
    $("trials").append(detail);
  }
  const link = document.createElement("a");
  link.href = `/api/runs/${id}`;
  link.target = "_blank";
  link.textContent = "Inspect complete run JSON ↗";
  $("trials").append(link);
  await loadNamespaces(result.cases?.[0]?.namespace);
}
async function loadNamespaces(preferred) {
  const rows = await api("/api/namespaces");
  const selected = preferred || $("namespaces").value || rows[0]?.name;
  options(
    $("namespaces"),
    rows.map((n) => [n.name, `${n.name} · revision ${n.revision}`]),
    selected,
  );
  if (rows.length) await showNamespace($("namespaces").value);
}
async function showNamespace(name) {
  const state = await api(`/api/namespaces/${encodeURIComponent(name)}`);
  $("records").replaceChildren();
  for (const record of state.records) {
    const row = document.createElement("tr");
    cell(row, record.id, "record-id");
    cell(
      row,
      `${record.kind} / ${record.effective_state}`,
      record.effective_state === "superseded" ? "muted" : "pass",
    );
    cell(row, record.text);
    const scope = cell(
      row,
      `${record.applies_to || "Project"} · ${record.source_ids.join(", ")}`,
    );
    const detail = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Inspect sources & links";
    detail.append(summary);
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(
      {
        supersedes: record.supersedes,
        depends_on: record.depends_on,
        sources: state.events.filter((e) => record.source_ids.includes(e.id)),
      },
      null,
      2,
    );
    detail.append(pre);
    scope.append(detail);
    $("records").append(row);
  }
}
$("experiment").addEventListener("submit", async (event) => {
  event.preventDefault();
  busy(true);
  $("status").textContent = "Starting local comparison…";
  try {
    const cases =
      $("cases").value === "all"
        ? ["release_handoff", "conversation", "budgeting"]
        : [$("cases").value];
    const job = await api("/api/jobs", {
      writer_model: $("writer").value,
      reader_model: $("reader").value,
      cases,
      repetitions: Number($("repetitions").value),
      byte_budget: $("budget").value.startsWith("t")
        ? 6000
        : Number($("budget").value),
      token_budget: $("budget").value.startsWith("t")
        ? Number($("budget").value.slice(1))
        : null,
      writer_settings: inference($("writer-thinking").value === "true"),
      reader_settings: inference($("reader-thinking").value === "true"),
      seed: 42,
    });
    activeJob = job.job_id;
    poll();
  } catch (error) {
    $("status").textContent = error.message;
    busy(false);
  }
});
async function poll() {
  if (!activeJob) return;
  try {
    const job = await api(`/api/jobs/${activeJob}`);
    $("status").textContent =
      `${job.status} · ${job.trials || 0} probes saved. Model writing and loading can take a moment.`;
    if (job.status === "completed" || job.status === "failed") {
      activeJob = null;
      busy(false);
      $("status").textContent =
        job.error ||
        `Completed · ${job.trials || 0} probes saved. Select a trial to inspect its context and response.`;
      await loadRuns(job.run_id);
      await loadOverview();
    } else {
      if (job.run_id) await showRun(job.run_id);
      setTimeout(poll, 2000);
    }
  } catch (error) {
    activeJob = null;
    $("status").textContent = error.message;
    busy(false);
  }
}
$("runs").addEventListener("change", () => showRun($("runs").value));
$("namespaces").addEventListener("change", () =>
  showNamespace($("namespaces").value),
);

async function loadQualifications(preferred) {
  const rows = await api("/api/qualifications");
  $("qualification-summary-value").textContent =
    `${counted(rows.length, "saved run")} · Controls, workflow gates & outcomes`;
  options(
    $("qualification-runs"),
    rows.map((r) => [
      r.id,
      `${r.config.model} · ${r.config.settings.thinking ? "reasoning on" : "reasoning off"} · ${r.id}`,
    ]),
    preferred || rows[0]?.id,
  );
  if (rows.length) await showQualification($("qualification-runs").value);
}
async function showQualification(id) {
  const result = await api(`/api/qualifications/${id}`);
  $("qualification-meta").textContent =
    `${result.status} · ${result.protocol} · ${result.config.model} · reasoning ${result.config.settings.thinking ? "on" : "off"} · ${result.trials.length} probes · ${result.qualified ? "meets all workflow gates" : "qualification not established"}`;
  $("qualification-totals").replaceChildren();
  for (const [workflow, total] of Object.entries(result.totals || {})) {
    const row = document.createElement("tr");
    cell(row, workflow.replaceAll("_", " "));
    for (const condition of ["full_history", "minimal_source"]) {
      const group = total[condition];
      cell(
        row,
        `${group.passed} / ${group.planned}${group.errors ? ` · ${group.errors} errors` : ""}`,
      );
    }
    cell(
      row,
      total.qualified ? "Qualified" : "Not qualified",
      total.qualified ? "pass" : "fail",
    );
    $("qualification-totals").append(row);
  }
  $("qualification-trials").replaceChildren();
  const failed = result.trials.filter(
    (t) => t.status !== "graded" || !t.grade.passed,
  );
  for (const trial of failed) {
    const detail = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `${trial.case} · ${trial.condition} · ${trial.status === "graded" ? "FAIL" : trial.status}`;
    summary.className = "fail";
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(
      {
        context: trial.context,
        answer: trial.model?.parsed,
        grade: trial.grade,
        error: trial.error,
        historical_tokens: trial.historical_tokens,
        prompt_tokens: trial.model?.prompt_tokens,
        output_tokens: trial.model?.output_tokens,
        accounting_match: trial.model?.prompt_accounting_match,
      },
      null,
      2,
    );
    detail.append(summary, pre);
    $("qualification-trials").append(detail);
  }
  const link = document.createElement("a");
  link.href = `/api/qualifications/${id}`;
  link.target = "_blank";
  link.textContent = "Inspect all qualification outcomes and raw JSON ↗";
  $("qualification-trials").append(link);
}
$("qualification").addEventListener("submit", async (event) => {
  event.preventDefault();
  busy(true);
  $("qualification-status").textContent = "Starting qualification…";
  try {
    const job = await api("/api/qualification/jobs", {
      model: $("qualification-model").value,
      cases_per_workflow: Number($("qualification-count").value),
      calculator: $("qualification-calculator").value === "true",
      settings: inference($("qualification-thinking").value === "true"),
    });
    qualificationJob = job.job_id;
    pollQualification();
  } catch (error) {
    $("qualification-status").textContent = error.message;
    busy(false);
  }
});
async function pollQualification() {
  if (!qualificationJob) return;
  try {
    const job = await api(`/api/jobs/${qualificationJob}`);
    $("qualification-status").textContent =
      `${job.status} · ${job.trials || 0} probes saved. Reasoning-enabled trials can take longer.`;
    if (job.status === "completed" || job.status === "failed") {
      qualificationJob = null;
      busy(false);
      $("qualification-status").textContent =
        job.error || `Completed · ${job.trials} probes saved.`;
      await loadQualifications(job.run_id);
      await loadOverview();
    } else {
      if (job.run_id) await showQualification(job.run_id);
      setTimeout(pollQualification, 2000);
    }
  } catch (error) {
    qualificationJob = null;
    busy(false);
    $("qualification-status").textContent = error.message;
  }
}
$("qualification-runs").addEventListener("change", () =>
  showQualification($("qualification-runs").value),
);
Promise.all([
  loadModels(),
  loadRuns(),
  loadQualifications(),
  loadOverview(),
]).catch((error) => {
  $("status").textContent = error.message;
});
