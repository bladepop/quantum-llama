# Execution Plan (Work‑Breakdown Structure)

*Version 0.3 – April 30 2025*

> Each task is **atomically runnable by an LLM‑powered agent** (ChatGPT, Cursor, etc.). Complex items are decomposed into fine‑grained subtasks with explicit inputs, outputs, and dependencies.

---

## Legend

| ID | ⬆ Depends on | 👤 Owner | 🏁 Output | 📝 Agent Prompt |
| -- | ------------ | -------- | --------- | -------------- |

All agent prompts now follow a unified template:

```text
You are an autonomous coding agent working in the <repo_root> directory.
Goal: <one‑sentence objective>.
Deliverable(s): <explicit file path(s) or artifact>.
Constraints:
  • adhere to existing project conventions (black, ruff, conventional commits).
  • add/modify ONLY the files listed in Deliverables.
  • include docstrings and type hints.
Return **ONLY** the file diff(s) inside triple‑backtick fences.
```

The **📝 Agent Prompt** column shows the *goal & deliverables* portion; the wrapper above is implicit for every task.

---

## Phase 0 – Project Bootstrap

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 0.1 | Create mono‑repo scaffold | – | Git repo with initial commit | "Initialise a public Git repository named `llm‑ops‑assistant`. Add an MIT `LICENSE`, a standard Python `.gitignore`, and push an empty commit on `main`." |
| 0.2 | DevContainer + pre‑commit | 0.1 | `.devcontainer`, `pre‑commit.yaml` | "Add a DevContainer (Python 3.11, Poetry). Configure pre‑commit with Black, Ruff and Commitizen hooks enabled on `git commit`." |
| 0.3 | CI skeleton | 0.1 | `.github/workflows/ci.yml` | "Create a GitHub Actions workflow that caches Poetry deps, runs `pytest --cov`, and uploads the coverage artifact." |

---

## Phase 1 – Repo Crawler

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 1.1 | `TargetRepo` dataclass | 0.3 | `models/target_repo.py` | "Define a Pydantic dataclass `TargetRepo` with fields `url:str`, `default_branch:str='main'`, `language:Literal['python','typescript','java','go']`." |
| 1.2 | Concurrent clone util | 1.1 | `crawler/clone.py` | "Implement `async clone_repos(repos: list[TargetRepo], dest_dir: Path)` using `anyio` + `tenacity` (3 retries)." |
| 1.3 | Python AST builder | 1.2 | `crawler/ast_py.py` | "Parse Python files with `libcst` and emit a JSON‑serialisable AST dictionary." |
| 1.4 | TypeScript AST builder | 1.2 | `crawler/ast_ts.ts` | "Use `ts‑morph` to parse TS sources and emit a compact JSON AST written to stdout." |
| 1.5 | Baseline metrics collector | 1.2 | `crawler/baseline.py` | "Run `pytest --cov --junitxml=results.xml`; return JSON → `{tests_passed, coverage_percent}`." |
| 1.6 | Snapshot persistence | 1.3‑1.5 | `data/crawl.db` | "Create SQLite schema (runs, files, coverage) and bulk‑insert baseline metrics using `aiosqlite`." |

---

## Phase 2 – LLM Analysis & Plan Builder

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 2.1 | `PlanItem` model | 0.3 | `models/plan_item.py` | "Create a Pydantic model `PlanItem` with fields `id`, `file_path`, `action:Literal[...]`, `reason`, `confidence:float 0‑1`." |
| 2.2 | Prompt templates | 2.1 | `prompts/*.j2` | "Draft Jinja2 templates for tasks: *refactor*, *upgrade_runtime*, *add_tests* with {{file_path}}, {{reason}} slots." |
| 2.3 | Function‑calling schema | 2.1 | `llm/schema.py` | "Map `PlanItem` to an OpenAI JSON function schema for structured output." |
| 2.4 | Planner engine | 1.6 & 2.2‑2.3 | `planner/engine.py` | "Implement `plan_repo(repo_snapshot)` that iterates ASTs, renders prompts, calls `openai.chat_completions`, returns `List[PlanItem]`." |
| 2.5 | Confidence heuristic | 2.4 | `planner/scoring.py` | "Combine `choice.logprobs`, static‑lint score, baseline tests into a 0‑1 confidence value." |

---

## Phase 3 – Change Engine

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 3.1 | Git ops helper | 0.3 | `engine/git_ops.py` | "Wrap `pygit2` to create branch `run‑{id}` from HEAD and interface with GitHub API to open PRs." |
| 3.2 | LLM patch generator | 2.4 | `engine/patch.py` | "Prompt: *'Produce a unified diff that implements {{plan_item.reason}} on {{plan_item.file_path}} (no context lines outside change).*'" |
| 3.3 | Apply & commit | 3.2 | updated working tree | "Apply diff, run `black` + `ruff --fix`, commit using **conventional commit** style (`feat(plan): ...`)." |
| 3.4 | Push & open PR | 3.1 & 3.3 | PR URL | "Push branch, open PR, assign reviewers from CODEOWNERS, add checklist markdown body." |

---

## Phase 4 – Verification Pipeline

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 4.1 | Coverage diff in CI | 0.3 & 3.4 | coverage artifact | "Extend `ci.yml`: after tests, run `diff‑cover` against base SHA, upload HTML report." |
| 4.2 | JUnit parser | 4.1 | `verification/parser.py` | "Parse `results.xml` into Verification table rows: {passed_before, passed_after}." |
| 4.3 | Merge‑gate policy | 4.2 & 2.5 | `verification/policy.py` | "Block PR if tests fail **OR** `plan_item.confidence < 0.8`; post GitHub Check summary." |

---

## Phase 5 – Tracking DB & Dashboard

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 5.1 | SQLAlchemy models | 0.3 | `db/models.py` + migration | "Translate entities Run, PlanItem, Change, Verification into SQLAlchemy models & autogenerate Alembic revision." |
| 5.2 | FastAPI service | 5.1 | `api/main.py` | "Expose REST `/runs`, `/plan_items`, `/changes` with pagination and Pydantic responses." |
| 5.3 | Monday.com sync | 5.2 | `integrations/monday.py` | "Use Monday GraphQL API to mirror `Run` status (columns: Stage, Confidence, Owner)." |
| 5.4 | Next.js dashboard | 5.2 | `web/` | "Scaffold Next.js 14 app; add `/runs` table using SWR > FastAPI; include dark‑mode toggle." |

---

## Phase 6 – Safety & Compliance

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 6.1 | Secret scanner wrapper | 0.3 | `security/secret_scan.py` | "Wrap `trufflehog` CLI to scan diff text; return list[Finding] with severity." |
| 6.2 | Redaction middleware | 6.1 | `security/redact.py` | "Replace detected secrets with `<SECRET_HASH_{n}>`; store mapping in Hashicorp Vault KV." |
| 6.3 | NO_LLM parser | 1.2 | `security/optout.py` | "Skip any file containing `# NO_LLM` (top 10 lines) from LLM context & processing." |

---

## Phase 7 – Prototype & Validation

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 7.1 | Repo list config | 1.1 | `targets.yaml` | "Create `targets.yaml` listing `infra/ops-tools` (language=python, branch=main)." |
| 7.2 | Dry‑run analysis | 7.1 & 2.4 | `run‑{id}.json` | "Invoke planner with `dry_run=True`; write PlanItems JSON to `runs/{id}/plan.json`." |
| 7.3 | Execute first changes | 7.2 & 3.* | initial PRs | "Run Change Engine on first 5 PlanItems (`batch_size=1`) and wait for CI." |
| 7.4 | Metrics & feedback | 4.2 & 5.4 | Markdown report | "Generate `reports/run_{id}.md` summarising pass‑rate, coverage delta, reviewer comments." |

---

## Phase 8 – Multi‑Repo Scale‑Out

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 8.1 | K8s dispatcher | 7.3 | `orchestration/dispatcher.py` | "Launch a Kubernetes `Job` per repo using Helm chart `llm-ops/plan-runner`." |
| 8.2 | Incident playbook | 8.1 | `docs/incident.md` | "Draft SOP: detection, mitigation, rollback (`git revert`, flag toggle)." |
| 8.3 | Grafana KPI panels | 5.4 & 8.1 | `dashboards/kpi.json` | "Create Grafana JSON with success_rate, mean_confidence, MTTR using PromQL." |

---

## Phase 9 – Observability & Operability

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 9.1 | JSON logging | 0.3 | `core/logging.py` | "Implement structured logging (ECS v1) via `python-json-logger`; include trace_id where present." |
| 9.2 | OpenTelemetry traces | 0.3 | `core/otel_middleware.py` | "Instrument planner & engine; export OTLP to `OTEL_EXPORTER_OTLP_ENDPOINT`." |
| 9.3 | Prom metrics exporter | 9.1 | `core/metrics.py` | "Expose `/metrics` with `planning_latency_seconds` histogram & `llm_cost_usd_total` counter." |
| 9.4 | Alert rules + runbook | 9.3 | `docs/alerting.md`, `alert_rules.yml` | "Create PrometheusRule: alert `HighVerificationFailures` when `failure_rate>0.05 for 10m`." |

---

## Phase 10 – LLM‑Ops & Prompt Regression

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 10.1 | Prompt registry | 2.2 | `prompts/registry.json` | "Generate SHA‑256 for each `.j2` file; store semver, checksum, created_at." |
| 10.2 | Golden‑set tests | 4.1 | `tests/prompt_regression.py` | "Compare freshly generated PlanItems against `tests/golden/*.jsonl`; fail if diff." |
| 10.3 | Cost dashboard | 9.3 | `dashboards/cost.json` | "Add Grafana panel showing `sum(llm_cost_usd_total)` and per‑Run breakdown using PromQL." |

---

## Phase 11 – Performance & Caching

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 11.1 | Redis prompt cache | 2.4 | `core/cache.py` | "Implement Redis‑based cache keyed by `(prompt_hash, file_sha)`; TTL 30 days." |
| 11.2 | Rate limiting & back‑pressure | 11.1 | `core/ratelimit.py` | "Add leaky‑bucket limiter (50 req/min) and exponential backoff when HTTP 429." |
| 11.3 | Celery job queue | 2.4 | `tasks/worker.py`, `docker/worker.Dockerfile` | "Use Celery + Redis broker to run planner & change engine tasks asynchronously." |

---

## Phase 12 – Framework Testing & Release

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 12.1 | Framework unit tests | 0.3 | `tests/unit/` | "Create pytest suite for `db`, `git_ops`, `cache`, aiming ≥90 % coverage." |
| 12.2 | Integration fixture repo | 3.4 | `tests/integration/fixture_repo/` | "Generate miniature Git repo; run end‑to‑end pipeline and assert PR opened & CI green." |
| 12.3 | Load test script | 11.3 | `scripts/load_test.py` | "Fire 10 000 PlanItems through planner; output rps, latency p95." |
| 12.4 | SemVer release workflow | 0.3 | `.github/workflows/release.yml` | "On tag vX.Y.Z, build & push Docker image and publish to PyPI using Poetry." |
| 12.5 | DB migration helpers | 5.1 | `db/migrate_cli.py` | "CLI to migrate SQLite → Postgres with data validation." |

---

## Phase 13 – Developer Experience & Docs

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 13.1 | CONTRIBUTING.md & ADR template | 0.1 | `CONTRIBUTING.md`, `docs/adr_template.md` | "Write contribution guidelines, code style rules, and lightweight ADR template." |
| 13.2 | CLI wrapper (`llm‑ops`) | 5.2 | `cli/__main__.py` | "Create Click‑based CLI with sub‑commands `plan`, `execute`, `status`." |
| 13.3 | Example codemods | 3.2 | `examples/` | "Add `rename_function.py` codemod and README explaining plugin interface." |

---

## Phase 14 – Security Hardening

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 14.1 | SSO / PAT rotation | 3.1 | `security/token_rotator.py` | "Rotate GitHub PAT via GitHub Apps every 24 h; store secret in Vault." |
| 14.2 | Audit log export | 9.1 | `security/audit.py` | "Ship structured logs to S3 bucket with server‑side encryption + lifecycle policy 90 days." |
| 14.3 | Signed commits | 3.3 | `engine/git_sign.py` | "Configure `git config user.signingkey` and sign all commits with GPG key in CI." |

---

## Phase 15 – Multi‑Language Support (Stubs)

| ID | Task | ⬆ | Output | 📝 Agent Prompt |
|----|------|---|--------|-----------------|
| 15.1 | Java/Kotlin AST stub | 1.2 | `crawler/ast_java.py` | "Create placeholder with TODO and interface matching Python builder." |
| 15.2 | Go AST stub | 1.2 | `crawler/ast_go.go` | "Add stub file returning `NotImplementedError`; include docstring with planned library (`go/ast`)." |

---

## Dependency Graph (v0.3)

```
0.1 → 0.2 → 0.3
0.3 → 1.* → 2.* → 3.* → 4.* → 5.*
1.2 → 6.3
0.3 → 6.1 → 6.2
2.4 → 11.* → 12.3
0.3 → 12.4
5.1 → 12.5
2.2 & 4.* → 10.*
0.3 → 9.*
7.3 & 5.4 → 8.*
0.1 & 5.2 → 13.*
3.* & 9.* → 14.*
1.2 → 15.*
```

---

### Next Steps (rev‑3)
1. **Scope freeze** – sign‑off v0.3 WBS by **May 2 2025**.
2. **Board sync** – update Monday.com with new phases & tasks.
3. **Parallelise** – kick‑off Phases 0, 1, 9 in parallel; schedule Phase 11 cache work before scaling.
4. **Gate rollouts** – enforce 10.2 golden‑set tests before any production PR.

© 2025


