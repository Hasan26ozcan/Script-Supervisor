# Technical Architecture Diagrams

This document provides a comprehensive set of technical diagrams for the
Creative Harness evaluation system. All diagrams use plain-text identifiers and
structural annotations suitable for inclusion in technical documentation.

> **Rendering note:** All diagrams use Mermaid syntax. GitHub renders these
> natively in markdown. For local rendering, install the
> [Markdown Preview Mermaid Support](https://marketplace.visualstudio.com/items?itemName=vstirbu.comments-preview-vscode)
> VS Code extension, or use `mmdc` to export to PNG/SVG.

---

## 1. Five-Layer Architecture — High Level

```mermaid
graph TD
    P["Presentation Layer<br/>FastAPI REST API<br/>Comparison UI<br/>Inspect AI CLI"]
    O["Orchestration Layer<br/>CorrectionLoop<br/>AdaptiveRouter<br/>EvaluationHarness"]
    S["Service Layer<br/>ModelGateway<br/>Rubric<br/>Mem0<br/>PreferenceStore<br/>CostBudget"]
    D["Persistence Layer<br/>PostgreSQL 16 (primary)<br/>JSONL (offline fallback)"]
    I["Infrastructure Layer<br/>Docker Compose<br/>Postgres 16<br/>Langfuse (optional)<br/>GitHub Actions CI/CD"]

    P --> O
    O --> S
    S --> D
    D --> I
    P -.->|optional tracing| I

    classDef presentation fill:#f0f9ff,stroke:#0284c7,stroke-width:2px,color:#07377e
    classDef orchestration fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#065f46
    classDef service fill:#fffbeb,stroke:#ea580c,stroke-width:2px,color:#78350f
    classDef persistence fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a
    classDef infrastructure fill:#f5f3ff,stroke:#4f46e5,stroke-width:2px,color:#312e81
    class P presentation
    class O orchestration
    class S service
    class D persistence
    class I infrastructure
```

The system is organized into five architectural layers, each with a clear
responsibility boundary:

| Layer | Components | Responsibility |
|---|---|---|
| **Presentation** | FastAPI REST API, Comparison UI (HTML), Inspect AI CLI | Expose endpoints, serve HTML UI, integrate with Inspect AI |
| **Orchestration** | CorrectionLoop, AdaptiveRouter, EvaluationHarness | Control flow for correction iterations, model escalation, statistical eval |
| **Service** | ModelGateway, Rubric, Mem0Manager, PreferenceStore, CostBudget | Provider abstraction, scoring, compression tracking, persistence, cost |
| **Persistence** | PostgreSQL 16 (primary), JSONL (offline fallback) | Durable storage for preferences, traces, rubric state, Mem0 entries |
| **Infrastructure** | Docker Compose, Postgres 16, optional Langfuse, GitHub Actions CI/CD | Container orchestration, database, observability, CI/CD |

---

## 2. Module Dependency Graph

Key internal package dependencies (selective view — see source for full detail):

```mermaid
graph LR
    subgraph app["app/"]
        MAIN["main.py"]
        LOOP["agent_loop.py"]
        GW["gateway.py"]
        RUB["rubric.py"]
        MEM["mem0.py"]
        PREF["preference_store.py"]
        EVAL["evaluation_harness.py"]
    end

    subgraph training["training/"]
        DPO["dpo_train.py"]
        EXPORT["export_dpo_dataset.py"]
    end

    subgraph evals["evals/"]
        INSPECT["inspect_preference_task.py"]
    end

    MAIN --> LOOP
    MAIN --> PREF
    MAIN --> MEM
    MAIN --> EVAL

    LOOP --> GW
    LOOP --> RUB

    MEM --> GW
    MEM --> PREF
    MEM --> RUB

    PREF --> GW
    PREF --> RUB

    EXPORT --> PREF
    DPO --> EXPORT

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

**Internal dependency table** — the `settings` object (`app/config.py`) and
schema types (`app/schemas.py`) are shared across nearly all modules but
omitted from the diagram for clarity:

| Module | Imports from |
|---|---|
| `app/main.py` | `agent_loop`, `gateway`, `rubric`, `preference_store`, `mem0`, `evaluation_harness`, `config`, `prompts`, `schemas` |
| `app/agent_loop.py` | `gateway`, `rubric`, `routing`, `prompts`, `schemas`, `config` |
| `app/gateway.py` | `config`, `schemas`, `logging_config`, `budget` |
| `app/rubric.py` | `config`, `schemas` |
| `app/mem0.py` | `gateway`, `rubric`, `prompts`, `schemas`, `config` |
| `app/preference_store.py` | `db`, `schemas`, `config` |
| `app/evaluation_harness.py` | `preference_store`, `schemas`, `config` |
| `training/export_dpo_dataset.py` | `preference_store` |
| `training/dpo_train.py` | `export_dpo_dataset`, `preference_store` |
| `evals/inspect_preference_task.py` | `schemas` |

---

## 3. Correction Loop — Detailed Sequence

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant CorrectionLoop
    participant AdaptiveRouter
    participant ModelGateway
    participant Rubric
    participant Persistence

    Client->>FastAPI: POST /run (brief, max_turns)
    FastAPI->>CorrectionLoop: CorrectionLoop(max_turns)
    CorrectionLoop->>AdaptiveRouter: load_from_file(routing_rules.yaml)

    loop for turn 1 to max_turns
        CorrectionLoop->>AdaptiveRouter: select_model("draft", trace_steps)
        AdaptiveRouter-->>CorrectionLoop: model_name
        CorrectionLoop->>ModelGateway: call(task, system_prompt, user_prompt, model)
        ModelGateway->>ModelGateway: record call (tokens, cost, latency)
        ModelGateway-->>CorrectionLoop: CallResult(text)

        CorrectionLoop->>CorrectionLoop: Draft(turn, content, metadata)

        alt reference_images present
            CorrectionLoop->>AdaptiveRouter: should_use_vision(trace_steps)
            alt vision approved
                CorrectionLoop->>ModelGateway: call_vision(task, system, vision_prompt, image_paths)
                ModelGateway-->>CorrectionLoop: CallResult(text)
            else
                CorrectionLoop->>ModelGateway: call("critique", system, text_prompt)
                ModelGateway-->>CorrectionLoop: CallResult(text)
            end
        else
            CorrectionLoop->>ModelGateway: call("critique", system, text_prompt)
            ModelGateway-->>CorrectionLoop: CallResult(text)
        end

        CorrectionLoop->>Rubric: parse_critique_text(text)
        Rubric-->>CorrectionLoop: scores, revision_notes
        CorrectionLoop->>Rubric: weighted_overall(scores)
        Rubric-->>CorrectionLoop: overall_score

        CorrectionLoop->>CorrectionLoop: TraceStep(draft, critique)
        CorrectionLoop->>CorrectionLoop: evaluate stop conditions

        alt threshold_met or plateau or cost_threshold
            CorrectionLoop-->>FastAPI: break loop
        else continue
            CorrectionLoop->>AdaptiveRouter: select_model("draft"/"revise", trace_steps)
        end
    end

    FastAPI->>Persistence: write trace JSON to data/traces/
    Persistence-->>FastAPI: OK
    FastAPI-->>Client: RunTrace (full trace)
```

---

## 4. Rubric Weight Update — Bradley-Terry Gradient

```mermaid
flowchart LR
    subgraph "Preference Ingest Path"
        HUMAN["Human submits preference<br/>(A wins over B)"] --> CRITIQUE_A["Critique candidate A<br/>scores_a = {c1:s1, c2:s2, ...}"]
        HUMAN --> CRITIQUE_B["Critique candidate B<br/>scores_b = {c1:s1, c2:s2, ...}"]
    end

    CRITIQUE_A --> DIFF["Per-criterion diff:<br/>diff = sa - sb"]
    CRITIQUE_B --> DIFF

    DIFF --> PREDICT["Predict A better?<br/>diff > 0"]
    PREDICT --> COMPARE["predicted == human_winner?"]

    COMPARE -->|correct| NUDGE_UP["Nudge weight UP<br/>w += lr * confidence"]
    COMPARE -->|incorrect| NUDGE_DOWN["Nudge weight DOWN<br/>w -= lr * confidence"]

    NUDGE_UP --> CONF["confidence = sigmoid(abs(diff))<br/>lr = 0.15 (default)"]
    NUDGE_DOWN --> CONF

    CONF --> CLAMP["clamp weight to [0.05, inf)"]
    CLAMP --> PERSIST_W["write rubric_weights.json"]
    CLAMP --> PERSIST_H["append rubric_weight_history.jsonl"]

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

**Mechanics:**
- Each criterion's score difference (`sa - sb`) is compared against the human's
  pick (A wins → `diff > 0` is correct)
- Confidence is scaled via the sigmoid of the absolute difference — larger
  score gaps produce more confident weight updates
- Weights are nudged up (correct prediction) or down (incorrect prediction)
  by `learning_rate × confidence`
- Weights are clamped to a minimum of 0.05 to prevent criteria from being
  fully ignored
- Every update is persisted to both `rubric_weights.json` (current state) and
  `rubric_weight_history.jsonl` (for tracking evolution over time)

---

## 5. Data Flow — End-to-End Pipeline

```mermaid
flowchart LR
    subgraph "Input"
        BRIEF["Creative Brief<br/>data/briefs/phase1_briefs.json"]
        IMAGES["Reference Images<br/>data/images/"]
    end

    subgraph "Generation"
        DRAFT["Draft<br/>gateway.call('draft')"]
        REVISE["Revise<br/>gateway.call('revise')"]
    end

    subgraph "Evaluation"
        CRITIQUE["Critique<br/>gateway.call('critique')<br/>or gateway.call_vision('visual_critique')"]
        RUBRIC["Rubric Scoring<br/>parse_critique + weighted_overall"]
        TRACE["RunTrace<br/>data/traces/{run_id}.json"]
    end

    subgraph "Human Feedback"
        COMPARE["POST /compare<br/>candidate_a vs candidate_b"]
        MEM0["Mem0Manager.ingest"]
        PREF_STORE["PreferenceStore.add"]
    end

    subgraph "Persistence"
        PG["PostgreSQL<br/>preferences table<br/>evaluation_runs table"]
        JSONL["JSONL Fallback<br/>data/preferences.jsonl<br/>data/mem0_entries.jsonl<br/>data/rubric_weights.json"]
    end

    subgraph "Training"
        EXPORT["export_dpo_dataset"]
        DPO["DPO Training<br/>TRL DPOTrainer"]
    end

    BRIEF --> DRAFT
    IMAGES --> DRAFT
    DRAFT --> CRITIQUE
    CRITIQUE --> RUBRIC
    RUBRIC --> TRACE
    REVISE --> CRITIQUE

    COMPARE --> MEM0
    COMPARE --> PREF_STORE
    COMPARE --> RUBRIC

    MEM0 --> JSONL
    PREF_STORE --> PG
    PREF_STORE --> JSONL
    RUBRIC --> JSONL

    PREF_STORE --> EXPORT
    EXPORT --> DPO

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

**Pipeline stages:**

1. **Input**: A creative brief and optional reference images are received
2. **Generation**: The draft model produces an initial shot list; revision
   models refine it based on critique feedback
3. **Evaluation**: A critic model scores the draft against rubric criteria;
   vision-grounded critique uses reference images when available
4. **Human Feedback**: Human raters submit pairwise preferences via the
   `/compare` endpoint; Mem0 tracks compression pairs; preferences are persisted
5. **Persistence**: Data is written to PostgreSQL (primary) and JSONL
   (fallback) for durability
6. **Training**: Preference data is exported to DPO format and used for
   fine-tuning with TRL's `DPOTrainer`

---

## 6. Database Schema — Entity Relationship

```mermaid
erDiagram
    preferences {
        string pair_id PK "UUID hex"
        string created_at "ISO datetime"
        string brief "Creative brief text"
        string prompt "Exact prompt used"
        string candidate_a "First candidate output"
        string candidate_b "Second candidate output"
        string winner "a | b | tie"
        string rater "Rater identity"
        string notes "Free-form notes"
    }

    evaluation_runs {
        string run_id PK "run_{timestamp}"
        string created_at "ISO datetime"
        string suite_name "Eval suite name"
        string dataset_name "Dataset identifier"
        int n_samples
        int holdout_size
        float accuracy
        string report_markdown_path
        string report_html_path
        string metrics_json_path
        string charts_json
    }

    comparison_pairs {
        string pair_id "UUID hex"
        string source "compare_api | phase5"
        string brief
        string candidate_a
        string candidate_b
        string reference_image "nullable"
    }

    rubric_weights {
        string criterion PK
        float weight
    }

    rubric_weight_history {
        string timestamp PK
        string pair_id "FK nullable"
        string brief "nullable"
        string winner "nullable"
        string weights "JSON object"
    }

    mem0_entries {
        string entry_id PK
        string source_pair_id
        string source
        string brief
        string prompt
        string candidate_a
        string candidate_b
        string expected_winner
        string status "active | stale | replaced"
        string created_at
        string last_validated_at "nullable"
        float effectiveness_score
        string validation_history "JSON array"
        string replacement_suggestion "nullable"
    }

    preferences }|--|| evaluation_runs : "summarized into"
    comparison_pairs }|--|| preferences : "source for"
    rubric_weights ||--o{ rubric_weight_history : "snapshot of"
```

---

## 7. API Endpoint Map

```mermaid
graph TD
    POST_RUN["POST /run - Execute correction loop"]
    GET_TRACE["GET /traces/{run_id} - Retrieve trace JSON"]
    POST_COMPARE["POST /compare - Record pairwise preference"]
    POST_EVAL["POST /evaluation/run - Run statistical suite"]
    GET_RUBRIC["GET /rubric - Current criteria + weights"]
    GET_RUBRIC_HISTORY["GET /rubric/history - Weight evolution"]
    GET_COMPARISONS["GET /comparison-pairs - All comparison pairs"]
    GET_MEM0_ENTRIES["GET /mem0/entries - All compression entries"]
    GET_MEM0_STALE["GET /mem0/stale - Stale entries"]
    POST_MEM0_VALIDATE["POST /mem0/validate - Re-validate all entries"]
    POST_MEM0_REFRESH["POST /mem0/refresh - Replace stale entries"]
    GET_COMPARE_UI["GET /compare-ui - Interactive HTML UI"]
    GET_HEALTH["GET /health - Liveness probe"]

    subgraph "Correction Loop"
        POST_RUN
        GET_TRACE
    end

    subgraph "Preference Management"
        POST_COMPARE
        GET_RUBRIC
        GET_RUBRIC_HISTORY
    end

    subgraph "Mem0 Compression Tracking"
        GET_MEM0_ENTRIES
        GET_MEM0_STALE
        POST_MEM0_VALIDATE
        POST_MEM0_REFRESH
    end

    subgraph "Evaluation"
        POST_EVAL
    end

    subgraph "Operational"
        GET_COMPARE_UI
        GET_HEALTH
        GET_COMPARISONS
    end

    POST_COMPARE --> GET_RUBRIC
    POST_COMPARE --> GET_MEM0_ENTRIES
    POST_EVAL --> GET_RUBRIC_HISTORY

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

---

## 8. Provider Integration — Gateway Abstraction

```mermaid
graph LR
    TASK["Logical task<br/>(draft, critique, revise,<br/>visual_critique)"] --> MODE_SELECT["AdaptiveRouter.select_model<br/>TASK_DEFAULT_MODEL fallback"]
    MODE_SELECT --> GW["ModelGateway"]

    subgraph Gateway["ModelGateway"]
        direction LR
        LEDGER["GatewayLedger - calls[]<br/>total_cost<br/>total_latency"]
        PRICES["MODEL_PRICES - input/output per 1M tokens"]
        BUDGET["CostBudget - per-run + daily limits"]
        GW --> LEDGER
        GW --> PRICES
        GW --> BUDGET
    end

    subgraph Provider["Provider Dispatch"]
        direction TB
        MOCK["MOCK_MODE (default)<br/>_mock_response<br/>_mock_vision_response"]
        ANTHROPIC["provider=anthropic<br/>Anthropic.messages.create<br/>tool_use for structured output"]
        GROQ["provider=groq<br/>Groq.chat.completions.create<br/>JSON extraction for structured output"]
    end

    GW --> MOCK
    GW --> ANTHROPIC
    GW --> GROQ

    LEDGER --> RECORD["CallResult - text, model, tokens,<br/>cost_usd, latency_ms"]

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

**Provider dispatch logic:**

- `MOCK_MODE` (default): returns synthetic responses for all tasks — no API
  keys or cost
- `provider=anthropic`: uses `AsyncAnthropic.messages.create` with native
  tool use for structured output (critique scores parsed reliably)
- `provider=groq`: uses `Groq.chat.completions.create` with JSON extraction
  for structured output

Every call is recorded by `GatewayLedger` with full provenance (model name,
token counts, cost in USD, latency in ms). `CostBudget` enforces per-run and
daily limits before any call is made.

---

## 9. Evaluation Harness — Statistical Pipeline

```mermaid
flowchart TD
    RAW_DATA["PreferenceStore.all()<br/>or fake preferences generator"] --> PREP["Filter non-tie pairs<br/>Extract A-win outcomes [0,1,...]"]

    PREP --> BOOTSTRAP["Bootstrap 95% CI on win rate<br/>5000 resamples<br/>percentile method<br/>seed=20260726"]
    PREP --> BINOMIAL["Binomial test vs 50/50 null<br/>scipy.stats.binomtest<br/>two-sided"]

    PREP --> BT_FIT["Bradley-Terry MLE fit<br/>optimize neg_log_likelihood<br/>BFGS solver"]

    RAW_DATA --> HEURISTIC["Heuristic judge<br/>sentence_count + action_verb_hits"]
    HEURISTIC --> AGREEMENT["Agreement rate<br/>human_label vs judge_prediction"]
    HEURISTIC --> KAPPA["Cohen's kappa<br/>(not computable if 1 rater/item)"]

    BOOTSTRAP --> POINT_CI["point_estimate, CI_lower, CI_upper"]
    BINOMIAL --> PVAL["p_value, significant_at_05"]
    BT_FIT --> STRENGTH["strength_gap_logit<br/>std_error<br/>P(A beats B)"]

    AGREEMENT --> ACC["agreement_rate"]
    KAPPA --> KAP["kappa_value or None"]

    POINT_CI --> METRICS["metrics dict"]
    PVAL --> METRICS
    STRENGTH --> METRICS
    ACC --> METRICS
    KAP --> METRICS

    METRICS --> CHARTS["Generate charts:<br/>win_rate_ci.png<br/>win_rate_trend.png<br/>samples_per_rater.png"]
    METRICS --> REPORTS["Write:<br/>evaluation_report.md<br/>evaluation_report.html<br/>metrics.json"]
    METRICS --> PERSIST["Persist run row to SQL<br/>Read back to confirm dialect"]

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

**Statistical methods in the pipeline:**

| Method | Purpose | Implementation |
|---|---|---|
| Bootstrap CI | Confidence interval on human win rate | 5000 resamples, percentile method, fixed seed |
| Binomial test | Significance of win rate vs 50/50 | `scipy.stats.binomtest`, two-sided |
| Bradley-Terry MLE | Relative candidate strength | `scipy.optimize.minimize`, BFGS solver |
| Cohen's κ | Inter-rater agreement | Standard formula, returns `None` if < 2 raters per item |

---

## 10. CI/CD Pipeline — Job Dependencies

```mermaid
graph TD
    TRIGGER["push / pull_request to main"]
    LINT["Lint - ruff check + format check<br/>mypy type checking"]
    SECURITY["Security - bandit static scan<br/>pip-audit dependency check"]
    TEST["Test - pytest with coverage<br/>PostgreSQL service container<br/>70% coverage gate"]
    EVAL_REG["Eval Regression - golden-qa dataset<br/>artifact upload"]
    SONAR["SonarCloud - code quality + coverage"]
    CODEQL["CodeQL - semantic analysis"]
    TRIVY_FS["Trivy Filesystem - vuln scan"]
    TRIVY_IMG["Trivy Docker Image - vuln scan"]
    GITGUARD["Gitleaks - secret scanning"]

    TRIGGER --> LINT
    TRIGGER --> SECURITY
    TRIGGER --> TEST
    TRIGGER --> EVAL_REG
    TRIGGER --> SONAR
    TRIGGER --> TRIVY_FS
    TRIGGER --> GITGUARD
    EVAL_REG --> TRIVY_IMG
    CODEQL -.->|"weekly cron"| CODEQL

    LINT --> GATE{"All jobs pass?"}
    SECURITY --> GATE
    TEST --> GATE
    EVAL_REG --> GATE
    SONAR --> GATE
    TRIVY_FS --> GATE
    GITGUARD --> GATE
    TRIVY_IMG --> GATE

    GATE -->|"success"| MERGE["Merge to main"]
    GATE -->|"failure"| BLOCK["Block PR"]

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

---

## 11. Configuration Binding — Environment to Components

All settings use the `HARNESS_` environment prefix, managed by a single
`Settings` class in `app/config.py` using `pydantic-settings`. A `.env` file
works out of the box for local development.

```mermaid
graph TD
    ENV["HARNESS_ environment variables<br/>.env file"]

    subgraph "Correction Loop"
        LOOP_CFG["max_turns, quality_threshold,<br/>plateau_epsilon,<br/>cost_efficiency_threshold"]
    end

    subgraph "Gateway / Provider"
        GW_CFG["mock_mode, provider,<br/>anthropic_api_key,<br/>groq_api_key"]
    end

    subgraph "Persistence"
        DB_CFG["database_url, database_echo,<br/>preferences_path,<br/>mem0_state_path"]
    end

    subgraph "Storage Paths"
        PATH_CFG["data_dir, traces_dir,<br/>rubric_weights_path,<br/>rubric_weight_history_path,<br/>comparison_pairs_path,<br/>evaluation_reports_dir"]
    end

    subgraph "Budgeting"
        BUDGET_CFG["run_budget_usd, daily_budget_usd"]
    end

    subgraph "Routing"
        ROUTE_CFG["routing_rules_path,<br/>routing_default_models"]
    end

    subgraph "Mem0"
        MEM_CFG["mem0_stale_margin"]
    end

    subgraph "Observability"
        OBS_CFG["langfuse_enabled,<br/>langfuse_public_key,<br/>langfuse_secret_key,<br/>langfuse_host"]
    end

    subgraph "Logging"
        LOG_CFG["log_level"]
    end

    ENV --> LOOP_CFG
    ENV --> GW_CFG
    ENV --> DB_CFG
    ENV --> PATH_CFG
    ENV --> BUDGET_CFG
    ENV --> ROUTE_CFG
    ENV --> MEM_CFG
    ENV --> OBS_CFG
    ENV --> LOG_CFG

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

### Full Configuration Reference

| Variable | Default | Type | Description |
|---|---|---|---|
| `HARNESS_MOCK_MODE` | `true` | bool | Mock responses; `false` for live API calls |
| `HARNESS_PROVIDER` | `anthropic` | str | LLM provider: `anthropic` or `groq` |
| `HARNESS_ANTHROPIC_API_KEY` | None | str | Required when mock mode is off |
| `HARNESS_GROQ_API_KEY` | None | str | Required when provider is `groq` |
| `HARNESS_MAX_TURNS` | `3` | int | Max correction-loop iterations |
| `HARNESS_QUALITY_THRESHOLD` | `8.0` | float | Quality score to stop the loop |
| `HARNESS_PLATEAU_EPSILON` | `0.3` | float | Score delta below which to stop |
| `HARNESS_COST_EFFICIENCY_THRESHOLD` | `0.0` | float | Min quality-per-dollar to continue |
| `HARNESS_DATABASE_URL` | PostgreSQL URL | str | Primary SQL database |
| `HARNESS_DATABASE_ECHO` | `false` | bool | SQL echo for debugging |
| `HARNESS_DATA_DIR` | `data` | str | Base data directory |
| `HARNESS_TRACES_DIR` | `data/traces` | str | Run traces output directory |
| `HARNESS_PREFERENCES_PATH` | `data/preferences.jsonl` | str | JSONL preference fallback |
| `HARNESS_MEM0_STATE_PATH` | `data/mem0_entries.jsonl` | str | Mem0 state file |
| `HARNESS_RUBRIC_WEIGHTS_PATH` | `data/rubric_weights.json` | str | Live rubric weights |
| `HARNESS_RUBRIC_WEIGHT_HISTORY_PATH` | `data/rubric_weight_history.jsonl` | str | Weight history log |
| `HARNESS_COMPARISON_PAIRS_PATH` | `data/comparisons/phase5_pairs.jsonl` | str | Comparison pairs source |
| `HARNESS_EVALUATION_REPORTS_DIR` | `docs/evaluation` | str | Eval output directory |
| `HARNESS_RUN_BUDGET_USD` | None | float | Per-run cost cap |
| `HARNESS_DAILY_BUDGET_USD` | None | float | Daily cost cap |
| `HARNESS_ROUTING_RULES_PATH` | `config/routing_rules.yaml` | str | Routing rules file path |
| `HARNESS_ROUTING_DEFAULT_MODES` | `{}` | dict | Fallback default models per task |
| `HARNESS_MEM0_STALE_MARGIN` | `1.0` | float | Margin below which a pair is stale |
| `HARNESS_LANGFUSE_ENABLED` | `false` | bool | Enable Langfuse tracing |
| `HARNESS_LANGFUSE_HOST` | `http://localhost:3000` | str | Langfuse server URL |
| `HARNESS_LANGFUSE_PUBLIC_KEY` | None | str | Langfuse public key |
| `HARNESS_LANGFUSE_SECRET_KEY` | None | str | Langfuse secret key |
| `HARNESS_LOG_LEVEL` | `INFO` | str | Logging level |

---

## 12. Docker Compose — Service Topology

```mermaid
graph TD
    subgraph "Default Profile"
        HARNESS["harness - FastAPI :8000<br/>HARNESS_MOCK_MODE<br/>HARNESS_DATABASE_URL"]
        POSTGRES["db - PostgreSQL 16 :5432<br/>POSTGRES_USER=postgres<br/>POSTGRES_DB=creative_harness"]
        VOLUME["data volume - ./data to /app/data"]
        HEALTH["healthcheck - /health endpoint<br/>pg_isready probe"]
    end

    subgraph "Observability Profile"
        LANGFUSE["langfuse - Langfuse :3000"]
        LANGFUSE_DB["langfuse-db - PostgreSQL 16 :5432<br/>POSTGRES_DB=langfuse"]
    end

    HARNESS -->|"primary persistence"| POSTGRES
    HARNESS -->|"volume mount"| VOLUME
    HARNESS -->|"health probe"| HEALTH
    HARNESS -.->|"optional tracing"| LANGFUSE
    LANGFUSE -->|"its own DB"| LANGFUSE_DB

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

**Service details:**

| Service | Profile | Ports | Notes |
|---|---|---|---|
| `harness` | default | 8000 | FastAPI app; mounts `./data` volume |
| `db` | default | 5432 | PostgreSQL 16; healthcheck via `pg_isready` |
| `langfuse` | observability | 3000 | Langfuse UI; MIT-licensed, self-hosted |
| `langfuse-db` | observability | 5432 | Separate Postgres for Langfuse |

**Usage:**
```bash
docker compose up -d                              # app + PostgreSQL
docker compose --profile observability up -d      # adds Langfuse
```

---

## 13. State Machine — Correction Loop Termination

```mermaid
stateDiagram-v2
    [*] --> TurnStart: turn = 1
    TurnStart --> GenerateDraft: gateway.call(task='draft')
    GenerateDraft --> GenerateCritique: gateway.call('critique' | 'visual_critique')
    GenerateCritique --> EvaluateScore: rubric.weighted_overall()

    EvaluateScore --> CheckThreshold: overall >= quality_threshold
    EvaluateScore --> CheckCost: quality_per_dollar < threshold
    EvaluateScore --> CheckPlateau: abs(delta) < plateau_epsilon
    EvaluateScore --> NextTurn: all checks pass

    CheckThreshold --> ThresholdMet: yes
    CheckThreshold --> CheckCost: no
    CheckCost --> CheckPlateau: no
    CheckPlateau --> CheckMaxTurns: no

    CheckMaxTurns --> NextTurn: turn < max_turns
    CheckMaxTurns --> MaxTurns: turn == max_turns

    ThresholdMet --> [*]: stop_reason = 'threshold_met'
    CheckPlateau --> Plateau: yes
    Plateau --> [*]: stop_reason = 'plateau'
    CheckCost --> CostThreshold: yes
    CostThreshold --> [*]: stop_reason = 'cost_threshold'
    MaxTurns --> [*]: stop_reason = 'max_turns'

    NextTurn --> TurnStart: turn += 1
```

**Stop conditions (evaluated in order after each turn):**

| Condition | Description | `stop_reason` value |
|---|---|---|
| Quality threshold | Overall score ≥ `HARNESS_QUALITY_THRESHOLD` (default 8.0) | `threshold_met` |
| Cost efficiency | Marginal quality-per-dollar < `HARNESS_COST_EFFICIENCY_THRESHOLD` | `cost_threshold` |
| Plateau | Score delta < `HARNESS_PLATEAU_EPSILON` (default 0.3) | `plateau` |
| Max turns | `turn == max_turns` | `max_turns` |

---

## 14. Mem0 Compression Pair Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Active: Mem0Manager.ingest_comparison_pair()
    Active --> ValidateEntry: POST /mem0/validate
    ValidateEntry --> CheckStale: predicted_winner != expected<br/>OR margin < stale_margin

    CheckStale --> Stale: true
    CheckStale --> Active: false

    Stale --> RefreshEntries: POST /mem0/refresh
    RefreshEntries --> Replaced: Mem0Manager.refresh_stale()
    Replaced --> [*]: status='replaced' - new entry created

    Active --> [*]: end of lifecycle
    Stale --> [*]: end of lifecycle

    note right of Active
        state: active
        effectiveness_score: margin
        last_validated_at: timestamp
    end note

    note right of Stale
        state: stale
        effectiveness_score: margin * 0.5
        replacement_suggestion: re-evaluate
    end note
```

**Lifecycle states:**

| State | Meaning | Trigger |
|---|---|---|
| `active` | Entry is valid; predicted winner matches expectation with sufficient margin | Ingest or validation success |
| `stale` | Entry no longer effective; needs replacement | Validation finds mismatch or small margin |
| `replaced` | Entry has been superseded by a new version | Refresh operation creates replacement |

---

## 15. Prompt Registry — Template Loading

```mermaid
graph TD
    REGISTRY["prompts/ directory - versioned YAML templates"]

    subgraph "Prompt Types"
        DRAFT["draft/v1.yaml - Shot list generation instructions"]
        CRITIQUE["critique/v1.yaml - Rubric-based scoring + revision notes"]
        VISION["vision_critique/v1.yaml - Reference image grounded critique"]
        REVISE["revise/v1.yaml - Incorporate critique notes"]
    end

    REGISTRY --> DRAFT
    REGISTRY --> CRITIQUE
    REGISTRY --> VISION
    REGISTRY --> REVISE

    DRAFT --> LOOP_DRAFT["CorrectionLoop._generate_draft() - get_prompt('draft')"]
    CRITIQUE --> LOOP_CRITIQUE["CorrectionLoop._generate_critique() - get_prompt('critique')"]
    VISION --> LOOP_VISION["CorrectionLoop._get_vision_critique_system() - get_prompt('vision_critique')"]
    REVISE --> LOOP_REVISE["CorrectionLoop._generate_draft() - task='revise' -> get_prompt('draft')"]

    CACHE["lru_cache(maxsize=128) - get_prompt()"] --> REGISTRY

    LOOP_DRAFT --> GW_CALL["ModelGateway.call()"]
    LOOP_CRITIQUE --> GW_CALL_V["ModelGateway.call()"]
    LOOP_VISION --> GW_CALL_IMG["ModelGateway.call_vision()"]

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

**Prompt types:**

| Task | Template | Criteria | Used In |
|---|---|---|---|
| `draft` | `prompts/draft/v1.yaml` | N/A (generation) | Turn 1: initial shot list |
| `critique` | `prompts/critique/v1.yaml` | clarity, tone_match, actionability | Text-only critique |
| `vision_critique` | `prompts/vision_critique/v1.yaml` | visual_continuity, lighting_match, mood_match | Vision-grounded critique |
| `revise` | `prompts/revise/v1.yaml` | N/A (generation) | Turn 2+: improved shot list |

Templates are loaded from YAML files and cached via `lru_cache(maxsize=128)`
in `app/prompts.py`. Versioning allows A/B testing different prompt
formulations without code changes.

---

## 16. Test Suite — Coverage Distribution

```mermaid
graph TD
    PYTEST["pytest - asyncio_mode=auto - testpaths=tests/"] --> UNIT["Unit Tests - app.rubric<br/>app.gateway<br/>app.budget<br/>app.schemas"]
    PYTEST --> INTEGRATION["Integration Tests - app.agent_loop<br/>app.main (TestClient)<br/>app.preference_store"]
    PYTEST --> EVAL["Eval Regression - evaluation_harness<br/>golden-qa outputs"]

    UNIT --> COVERAGE["--cov=app - 70% gate"]
    INTEGRATION --> COVERAGE
    EVAL --> COVERAGE

    PYTEST --> FIXTURES["pytest fixtures:<br/>MockGateway<br/>TestDatabase<br/>FakePreferences"]

    classDef default fill:#000000,stroke:#ffffff,stroke-width:1px,color:#ffffff
```

### Test Coverage Distribution

| Test Area | Coverage Share |
|---|---|
| agent_loop correction logic | 25% |
| gateway mock + live paths | 15% |
| rubric scoring + weight updates | 15% |
| preference_store postgres + jsonl | 12% |
| mem0 ingestion + validation | 10% |
| evaluation_harness statistics | 8% |
| routing yaml rules | 5% |
| schema validation | 5% |
| budget enforcement | 5% |

### Test Files

| File | Description |
|---|---|
| `test_agent_loop.py` | Correction loop integration tests |
| `test_agent_loop_coverage.py` | Edge case and coverage tests for the loop |
| `test_budget.py` | Cost budget enforcement and overflow |
| `test_dpo_train.py` | DPO training dry-run validation |
| `test_evaluation_harness.py` | Statistical evaluation pipeline |
| `test_fake_preferences.py` | Demo dataset generation |
| `test_gateway.py` | Gateway mock + live provider paths |
| `test_inspect_eval_task.py` | Inspect AI adapter |
| `test_main.py` | FastAPI endpoint tests (TestClient) |
| `test_mem0.py` | Mem0 store + manager |
| `test_mem0_store.py` | Mem0 entry persistence |
| `test_modern_evaluation_harness.py` | Modern eval harness |
| `test_preference_store.py` | PostgreSQL + JSONL preference storage |
| `test_prompts.py` | Prompt registry |
| `test_routing.py` | Adaptive router YAML rules |
| `test_rubric.py` | Rubric scoring + weight updates |
| `test_training_export.py` | DPO dataset export |
| `test_vision_critique.py` | Vision-grounded critique path |
| `test_phase1.py` | Phase 1 structured output validation |
| `test_phase3.py` | Phase 3 correction loop tests |
| `test_phase4.py` | Phase 4 vision effectiveness tests |
| `test_phase6.py` | Phase 6 rubric calibration tests |

---

## Appendix: Glossary

| Term | Definition |
|---|---|
| **Brief** | A creative scene description given to the shot-list generator |
| **Shot list** | A numbered sequence of camera shots for a scene |
| **Critique** | A model's evaluation of a shot list against the rubric |
| **Correction loop** | The iterative cycle of draft → critique → revise |
| **Rubric** | The scoring framework with weighted criteria |
| **Preference pair** | A human judgment: candidate A vs candidate B, which is better |
| **Mem0** | Compression pair tracking — re-validates comparison pairs over time |
| **DPO** | Direct Preference Optimization — turning preferences into fine-tuning data |
| **VLM** | Vision-Language Model — a model that processes both text and images |
| **Escalation** | Upgrading to a more capable (but costly) model when the cheap one fails |
| **Mock mode** | Synthetic responses without real API calls — for testing |
| **Gateway ledger** | Per-run record of all model calls, costs, and latencies |
