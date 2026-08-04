# Technical Architecture Diagrams — Creative Harness

This document provides a comprehensive set of technical diagrams for the Creative Harness evaluation system. All diagrams use plain-text identifiers and structural annotations rather than decorative symbols, suitable for inclusion in technical documentation.

---

## 1. Five-Layer Architecture

```mermaid
graph TD
    subgraph Presentation["Presentation Layer"]
        direction TB
        API["FastAPI REST API"]
        UI["Comparison UI - HTML"]
        CLI["Inspect AI CLI"]
    end

    subgraph Orchestration["Orchestration Layer"]
        direction TB
        LOOP["CorrectionLoop"]
        ROUTER["AdaptiveRouter"]
        EVAL["EvaluationHarness"]
    end

    subgraph Service["Service Layer"]
        direction TB
        GW["ModelGateway"]
        RUB["Rubric"]
        MEM["Mem0Manager"]
        PREF["PreferenceStore"]
        BUD["CostBudget"]
    end

    subgraph Persistence["Persistence Layer"]
        direction TB
        PG["PostgreSQL 16"]
        JSONL["JSONL Files"]
    end

    subgraph Infra["Infrastructure Layer"]
        direction TB
        DOCKER["Docker Compose"]
        GHA["GitHub Actions CI/CD"]
        LANGFUSE["Langfuse - optional"]
    end

    API --> LOOP
    API --> EVAL
    UI --> API
    CLI --> API

    LOOP --> GW
    LOOP --> RUB
    LOOP --> ROUTER

    EVAL --> PREF
    EVAL --> PG

    API --> RUB
    API --> PREF
    API --> MEM

    GW --> BUD
    RUB --> JSONL
    MEM --> JSONL

    PREF --> PG
    PREF --> JSONL

    PG --> DOCKER
    JSONL --> DOCKER
    GHA --> DOCKER
    GW -.->|optional tracing| LANGFUSE

    classDef layer fill:#f8f9fa,stroke:#495057,stroke-width:1px;
    classDef component fill:#ffffff,stroke:#6c757d,stroke-width:1px;
    class Presentation,Orchestration,Service,Persistence,Infra layer;
    class API,UI,CLI,LOOP,ROUTER,EVAL,GW,RUB,MEM,PREF,BUD,PG,JSONL,DOCKER,GHA,LANGFUSE component;
```

---

## 2. Module Dependency Graph

```mermaid
graph LR
    subgraph app["app/ module"]
        direction LR
        MAIN["main.py"]
        LOOP["agent_loop.py"]
        GW["gateway.py"]
        RUB["rubric.py"]
        MEM["mem0.py"]
        PREF["preference_store.py"]
        DB["db.py"]
        ROUTE["routing.py"]
        CFG["config.py"]
        SCHEMA["schemas.py"]
        PROMPT["prompts.py"]
        BUDGET["budget.py"]
        EVAL["evaluation_harness.py"]
        LOG["logging_config.py"]
    end

    subgraph training["training/ module"]
        DPO["dpo_train.py"]
        EXPORT["export_dpo_dataset.py"]
        FAKE["generate_fake_preferences.py"]
        MIGRATE["migrate_preferences_to_db.py"]
    end

    subgraph evals["evals/ module"]
        INSPECT["inspect_preference_task.py"]
    end

    MAIN --> LOOP
    MAIN --> RUB
    MAIN --> PREF
    MAIN --> MEM
    MAIN --> EVAL
    MAIN --> CFG

    LOOP --> GW
    LOOP --> RUB
    LOOP --> ROUTE
    LOOP --> PROMPT
    LOOP --> SCHEMA

    GW --> BUDGET
    GW --> CFG
    GW --> LOG
    GW --> SCHEMA

    RUB --> CFG
    RUB --> SCHEMA

    MEM --> GW
    MEM --> RUB
    MEM --> PREF
    MEM --> SCHEMA

    PREF --> DB
    PREF --> CFG
    PREF --> SCHEMA

    DB --> CFG

    ROUTE --> CFG
    ROUTE --> SCHEMA

    EVAL --> PREF
    EVAL --> CFG
    EVAL --> SCHEMA

    SCHEMA --> CFG

    EXPORT --> PREF

    MIGRATE --> PREF
    MIGRATE --> DB

    FAKE --> PREF
    FAKE --> SCHEMA

    INSPECT --> SCHEMA

    classDef app_module fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;
    classDef training_module fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    classDef eval_module fill:#fce4ec,stroke:#880e4f,stroke-width:2px;
    class MAIN,LOOP,GW,RUB,MEM,PREF,DB,ROUTE,CFG,SCHEMA,PROMPT,BUDGET,EVAL,LOG app_module;
    class DPO,EXPORT,FAKE,MIGRATE training_module;
    class INSPECT eval_module;
```

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
        activate ModelGateway
        ModelGateway->>ModelGateway: record call (tokens, cost, latency)
        ModelGateway-->>CorrectionLoop: CallResult(text)
        deactivate ModelGateway

        CorrectionLoop->>CorrectionLoop: Draft(turn, content, metadata)

        alt reference_images present
            CorrectionLoop->>AdaptiveRouter: should_use_vision(trace_steps)
            alt vision approved
                CorrectionLoop->>ModelGateway: call_vision(task, system, vision_prompt, image_paths)
                activate ModelGateway
                ModelGateway-->>CorrectionLoop: CallResult(text)
                deactivate ModelGateway
            else
                CorrectionLoop->>ModelGateway: call("critique", system, text_prompt)
                activate ModelGateway
                ModelGateway-->>CorrectionLoop: CallResult(text)
                deactivate ModelGateway
            end
        else
            CorrectionLoop->>ModelGateway: call("critique", system, text_prompt)
            activate ModelGateway
            ModelGateway-->>CorrectionLoop: CallResult(text)
            deactivate ModelGateway
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

    classDef step fill:#f5f5f5,stroke:#9e9e9e,stroke-width:1px;
    class HUMAN,CRITIQUE_A,CRITIQUE_B,DIFF,PREDICT,COMPARE,NUDGE_UP,NUDGE_DOWN,CONF,CLAMP,PERSIST_W,PERSIST_H step;
```

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
        RUBRIC["Rubric Scoring<br/>parse_critique_text + weighted_overall"]
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

    classDef store fill:#fffde7,stroke:#f9a825,stroke-width:1px;
    class PG,JSONL store;
```

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
    POST_RUN["POST /run<br/>Execute correction loop"]
    GET_TRACE["GET /traces/{run_id}<br/>Retrieve trace JSON"]
    POST_COMPARE["POST /compare<br/>Record pairwise preference"]
    POST_EVAL["POST /evaluation/run<br/>Run statistical suite"]
    GET_RUBRIC["GET /rubric<br/>Current criteria + weights"]
    GET_RUBRIC_HISTORY["GET /rubric/history<br/>Weight evolution"]
    GET_COMPARISONS["GET /comparison-pairs<br/>All comparison pairs"]
    GET_MEM0_ENTRIES["GET /mem0/entries<br/>All compression entries"]
    GET_MEM0_STALE["GET /mem0/stale<br/>Stale entries"]
    POST_MEM0_VALIDATE["POST /mem0/validate<br/>Re-validate all entries"]
    POST_MEM0_REFRESH["POST /mem0/refresh<br/>Replace stale entries"]
    GET_COMPARE_UI["GET /compare-ui<br/>Interactive HTML UI"]
    GET_HEALTH["GET /health<br/>Liveness probe"]

    subgraph "Correction Loop"<br/>POST_RUN
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

    classDef group fill:#f5f5f5,stroke:#9e9e9e,stroke-width:1px;
    class POST_RUN,GET_TRACE,POST_COMPARE,GET_RUBRIC,GET_RUBRIC_HISTORY,GET_COMPARISONS,GET_MEM0_ENTRIES,GET_MEM0_STALE,POST_MEM0_VALIDATE,POST_MEM0_REFRESH,GET_COMPARE_UI,GET_HEALTH,POST_EVAL group;
```

---

## 8. Provider Integration — Gateway Abstraction

```mermaid
graph LR
    TASK["Logical task<br/>(draft, critique, revise,<br/>visual_critique)"] --> MODE_SELECT["AdaptiveRouter.select_model<br/>+ TASK_DEFAULT_MODEL fallback"]

    MODE_SELECT --> GW["ModelGateway"]

    subgraph Gateway["ModelGateway"]
        direction LR
        LEDGER["GatewayLedger<br/>calls[]<br/>total_cost<br/>total_latency"]
        PRICES["MODEL_PRICES<br/>input/output per 1M tokens"]
        BUDGET["CostBudget<br/>per-run + daily limits"]

        GW --> LEDGER
        GW --> PRICES
        GW --> BUDGET
    end

    subgraph Provider["Provider Dispatch"]
        direction TB
        MOCK["MOCK_MODE (default)<br/>_mock_response<br/>_mock_vision_response"]
        ANTHROPIC["provider=anthropic<br/>AsyncAnthropic.messages.create<br/>tool_use for structured output"]
        GROQ["provider=groq<br/>Groq.chat.completions.create<br/>JSON extraction for structured output"]
    end

    GW --> MOCK
    GW --> ANTHROPIC
    GW --> GROQ

    LEDGER --> RECORD["CallResult<br/>text, model, tokens,<br/>cost_usd, latency_ms"]

    classDef infra fill:#e8f5e9,stroke:#2e7d32,stroke-width:1px;
    class LEDGER,PRICES,BUDGET,RECORD infra;
```

---

## 9. Evaluation Harness — Statistical Pipeline

```mermaid
flowchart TD
    RAW_DATA["PreferenceStore.all()<br/>or fake preferences generator"] --> PREP["Filter non-tie pairs<br/>Extract A-win outcomes [0,1,...]"]

    PREP --> BOOTSTRAP["Bootstrap CI on win rate<br/>5000 resamples<br/>percentile method<br/>seed=20260726"]
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

    classDef transform fill:#f3e5f5,stroke:#6a1b9a,stroke-width:1px;
    class BOOTSTRAP,BINOMIAL,BT_FIT,HEURISTIC,AGREEMENT,KAPPA,POINT_CI,PVAL,STRENGTH,ACC,KAP transform;

    classDef output fill:#e0f2f1,stroke:#00695c,stroke-width:1px;
    class CHARTS,REPORTS,PERSIST output;
```

---

## 10. CI/CD Pipeline — Job Dependencies

```mermaid
graph TD
    TRIGGER["push / pull_request to main"]
    LINT["Lint:<br/>ruff check + format check<br/>mypy type checking"]
    SECURITY["Security:<br/>bandit static scan<br/>pip-audit dependency check"]
    TEST["Test:<br/>pytest with coverage<br/>PostgreSQL service container<br/>70% coverage gate"]
    EVAL_REG["Eval Regression:<br/>golden-qa dataset<br/>artifact upload"]
    SONAR["SonarCloud:<br/>code quality + coverage"]
    CODEQL["CodeQL:<br/>semantic analysis"]

    TRIGGER --> LINT
    TRIGGER --> SECURITY
    TRIGGER --> TEST
    TRIGGER --> EVAL_REG
    TRIGGER --> SONAR
    TRIGGER --> CODEQL

    LINT --> GATE{"All jobs pass?"}
    SECURITY --> GATE
    TEST --> GATE
    EVAL_REG --> GATE
    SONAR --> GATE
    CODEQL --> GATE

    GATE -->|"success"| MERGE["Merge to main"]
    GATE -->|"failure"| BLOCK["Block PR"]

    classDef trigger fill:#e3f2fd,stroke:#1565c0;
    classDef job fill:#fafafa,stroke:#616161;
    classDef result fill:#e8f5e9,stroke:#2e7d32;
    classDef blocked fill:#ffebee,stroke:#c62828;

    class TRIGGER trigger;
    class LINT,SECURITY,TEST,EVAL_REG,SONAR,CODEQL job;
    class MERGE result;
    class BLOCK blocked;
```

---

## 11. Configuration Binding — Environment to Components

```mermaid
graph TD
    ENV["Environment Variables<br/>HARNESS_ prefix + .env file"]

    subgraph "Correction Loop"
        MAX_TURNS["max_turns: int = 3"]
        THRESHOLD["quality_threshold: float = 8.0"]
        PLATEAU["plateau_epsilon: float = 0.3"]
        COST_THRESH["cost_efficiency_threshold: float = 0.0"]
    end

    subgraph "Gateway / Provider"
        MOCK["mock_mode: bool = True"]
        PROVIDER["provider: str = 'anthropic'"]
        ANTHROPIC_KEY["anthropic_api_key: Optional[str]"]
        GROQ_KEY["groq_api_key: Optional[str]"]
    end

    subgraph "Persistence"
        DB_URL["database_url: str"]
        DB_ECHO["database_echo: bool = False"]
        PREF_PATH["preferences_path: str"]
        MEM0_PATH["mem0_state_path: str"]
    end

    subgraph "Storage Paths"
        DATA_DIR["data_dir: str = 'data'"]
        TRACES_DIR["traces_dir: str = 'data/traces'"]
        RUBRIC_PATH["rubric_weights_path: str"]
        RUBRIC_HIST["rubric_weight_history_path: str"]
        COMPARE_PATH["comparison_pairs_path: str"]
        EVAL_DIR["evaluation_reports_dir: str"]
    end

    subgraph "Budgeting"
        RUN_BUDGET["run_budget_usd: Optional[float]"]
        DAILY_BUDGET["daily_budget_usd: Optional[float]"]
    end

    subgraph "Routing"
        ROUTE_PATH["routing_rules_path: str"]
        ROUTE_DEFAULTS["routing_default_models: dict"]
    end

    subgraph "Mem0"
        STALE_MARGIN["mem0_stale_margin: float = 1.0"]
    end

    subgraph "Observability"
        LANGFUSE_EN["langfuse_enabled: bool = False"]
        LANGFUSE_PUB["langfuse_public_key: Optional[str]"]
        LANGFUSE_SEC["langfuse_secret_key: Optional[str]"]
        LANGFUSE_HOST["langfuse_host: str"]
    end

    subgraph "Logging"
        LOG_LEVEL["log_level: str = 'INFO'"]
    end

    ENV --> MAX_TURNS
    ENV --> THRESHOLD
    ENV --> PLATEAU
    ENV --> COST_THRESH
    ENV --> MOCK
    ENV --> PROVIDER
    ENV --> ANTHROPIC_KEY
    ENV --> GROQ_KEY
    ENV --> DB_URL
    ENV --> DB_ECHO
    ENV --> PREF_PATH
    ENV --> MEM0_PATH
    ENV --> DATA_DIR
    ENV --> TRACES_DIR
    ENV --> RUBRIC_PATH
    ENV --> RUBRIC_HIST
    ENV --> COMPARE_PATH
    ENV --> EVAL_DIR
    ENV --> RUN_BUDGET
    ENV --> DAILY_BUDGET
    ENV --> ROUTE_PATH
    ENV --> ROUTE_DEFAULTS
    ENV --> STALE_MARGIN
    ENV --> LANGFUSE_EN
    ENV --> LANGFUSE_PUB
    ENV --> LANGFUSE_SEC
    ENV --> LANGFUSE_HOST
    ENV --> LOG_LEVEL

    classDef env fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;
    classDef group fill:#fafafa,stroke:#424242,stroke-width:1px;
    class ENV env;
    class MAX_TURNS,THRESHOLD,PLATEAU,COST_THRESH,MOCK,PROVIDER,ANTHROPIC_KEY,GROQ_KEY,DB_URL,DB_ECHO,PREF_PATH,MEM0_PATH,DATA_DIR,TRACES_DIR,RUBRIC_PATH,RUBRIC_HIST,COMPARE_PATH,EVAL_DIR,RUN_BUDGET,DAILY_BUDGET,ROUTE_PATH,ROUTE_DEFAULTS,STALE_MARGIN,LANGFUSE_EN,LANGFUSE_PUB,LANGFUSE_SEC,LANGFUSE_HOST,LOG_LEVEL group;
```

---

## 12. Docker Compose — Service Topology

```mermaid
graph TD
    subgraph "Default Profile"
        HARNESS["harness<br/>FastAPI :8000<br/>HARNESS_MOCK_MODE<br/>HARNESS_DATABASE_URL"]
        POSTGRES["db<br/>PostgreSQL 16 :5432<br/>POSTGRES_USER=postgres<br/>POSTGRES_DB=creative_harness"]
        VOLUME["data volume<br/>./data -> /app/data"]
        HEALTH["healthcheck<br/>/health endpoint<br/>pg_isready probe"]
    end

    subgraph "Observability Profile"
        LANGFUSE["langfuse<br/>Langfuse :3000"]
        LANGFUSE_DB["langfuse-db<br/>PostgreSQL 16 :5432<br/>POSTGRES_DB=langfuse"]
    end

    HARNESS -->|"primary persistence"| POSTGRES
    HARNESS -->|"volume mount"| VOLUME
    HARNESS -->|"health probe"| HEALTH
    HARNESS -.->|"optional tracing"| LANGFUSE
    LANGFUSE -->|"its own DB"| LANGFUSE_DB

    classDef service fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px;
    classDef storage fill:#fff8e1,stroke:#ff6f00,stroke-width:1px;
    classDef probe fill:#fce4ec,stroke:#880e4f,stroke-width:1px;
    class HARNESS,POSTGRES,LANGFUSE,LANGFUSE_DB service;
    class VOLUME storage;
    class HEALTH probe;
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
    Replaced --> [*]: status='replaced'<br/>new entry created

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

---

## 15. Prompt Registry — Template Loading

```mermaid
graph TD
    REGISTRY["prompts/ directory<br/>versioned YAML templates"]

    subgraph PromptTypes["Prompt Types"]
        DRAFT["draft/v1.yaml<br/>Shot list generation instructions"]
        CRITIQUE["critique/v1.yaml<br/>Rubric-based scoring + revision notes"]
        VISION["vision_critique/v1.yaml<br/>Reference image grounded critique"]
        REVISE["revise/v1.yaml<br/>Incorporate critique notes"]
    end

    REGISTRY --> DRAFT
    REGISTRY --> CRITIQUE
    REGISTRY --> VISION
    REGISTRY --> REVISE

    DRAFT --> LOOP_DRAFT["CorrectionLoop._generate_draft()<br/>get_prompt('draft')"]
    CRITIQUE --> LOOP_CRITIQUE["CorrectionLoop._generate_critique()<br/>get_prompt('critique')"]
    VISION --> LOOP_VISION["CorrectionLoop._get_vision_critique_system()<br/>get_prompt('vision_critique')"]
    REVISE --> LOOP_REVISE["CorrectionLoop._generate_draft()<br/>task='revise' -> get_prompt('draft')"]

    CACHE["lru_cache(maxsize=128)<br/>get_prompt()"] --> REGISTRY

    LOOP_DRAFT --> GW_CALL["ModelGateway.call()"]
    LOOP_CRITIQUE --> GW_CALL_V["ModelGateway.call()"]
    LOOP_VISION --> GW_CALL_IMG["ModelGateway.call_vision()"]

    classDef registry fill:#e8f5e9,stroke:#1b5e20;
    classDef caller fill:#e3f2fd,stroke:#0d47a1;
    class REGISTRY,CACHE registry;
    class LOOP_DRAFT,LOOP_CRITIQUE,LOOP_VISION,LOOP_REVISE,GW_CALL,GW_CALL_V,GW_CALL_IMG caller;
```

---

## 16. Test Suite — Coverage Areas

```mermaid
pie showData
    title Test Coverage Distribution
    "agent_loop correction logic" : 25
    "gateway mock + live paths" : 15
    "rubric scoring + weight updates" : 15
    "preference_store postgres + jsonl" : 12
    "mem0 ingestion + validation" : 10
    "evaluation_harness statistics" : 8
    "routing yaml rules" : 5
    "schema validation" : 5
    "budget enforcement" : 5
```

```mermaid
graph TD
    PYTEST["pytest<br/>asyncio_mode=auto<br/>testpaths=tests/"] --> UNIT["Unit Tests<br/>app.rubric<br/>app.gateway<br/>app.budget<br/>app.schemas"]
    PYTEST --> INTEGRATION["Integration Tests<br/>app.agent_loop<br/>app.main (TestClient)<br/>app.preference_store"]
    PYTEST --> EVAL["Eval Regression<br/>evaluation_harness<br/>golden-qa outputs"]

    UNIT --> COVERAGE["--cov=app<br/>70% gate"]
    INTEGRATION --> COVERAGE
    EVAL --> COVERAGE

    PYTEST --> FIXTURES["pytest fixtures:<br/>MockGateway<br/>TestDatabase<br/>FakePreferences"]

    classDef runner fill:#fafafa,stroke:#424242;
    classDef level fill:#e8f5e9,stroke:#1b5e20;
    classDef result fill:#fff3e0,stroke:#e65100;

    class PYTEST runner;
    class UNIT,INTEGRATION,EVAL level;
    class COVERAGE,FIXTURES result;
```
