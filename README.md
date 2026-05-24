# AI Compiler — Natural Language → App Config

> **Multi-stage AI pipeline that converts plain English app descriptions into validated, executable JSON configurations (DB schema, API, UI, Auth).**

---

## Architecture

```
User Prompt
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Stage 1: Intent Extractor                           │
│  Parse features, entities, roles, ambiguities       │
└──────────────────────┬──────────────────────────────┘
                       │ structured intent
                       ▼
┌─────────────────────────────────────────────────────┐
│ Stage 2: System Design Layer                        │
│  Entities + fields, flows, role-permission matrix,  │
│  pages with access control                          │
└──────────────────────┬──────────────────────────────┘
                       │ architecture
                       ▼
┌─────────────────────────────────────────────────────┐
│ Stage 3: Schema Generator (4 parallel schemas)      │
│  ┌──────────┐  ┌──────────┐  ┌──────┐  ┌────────┐  │
│  │ DB Schema│  │API Schema│  │  UI  │  │  Auth  │  │
│  └──────────┘  └──────────┘  └──────┘  └────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ 4 schemas
                       ▼
┌─────────────────────────────────────────────────────┐
│ Stage 4: Validation + Repair Engine (CORE)          │
│  • JSON repair (syntax, truncation)                 │
│  • Schema validation (jsonschema)                   │
│  • Cross-layer consistency checks:                  │
│    - API endpoints ↔ DB tables                      │
│    - UI bindings ↔ API endpoints                    │
│    - Auth roles ↔ System design roles               │
│  • Level-1: Auto-repair (no LLM)                   │
│  • Level-2: Targeted LLM repair (broken layer only) │
│  • Never: blind full retry                          │
└──────────────────────┬──────────────────────────────┘
                       │ validated + refined output
                       ▼
              Executable JSON Config
         (DB + API + UI + Auth schemas)
```

---

## Quickstart

```bash
# 1. Clone / download
cd ai-compiler

# 2. Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Start
chmod +x start.sh && ./start.sh

# 4. Open frontend
open frontend/index.html
# (make sure backend URL in index.html points to localhost:8000)
```

---

## Project Structure

```
ai-compiler/
├── pipeline/
│   ├── __init__.py           # exports run_pipeline
│   ├── orchestrator.py       # Stage wiring + metrics
│   ├── stage1_intent.py      # Stage 1: Intent extraction
│   ├── stage2_design.py      # Stage 2: System design
│   ├── stage3_schemas.py     # Stage 3: 4x schema generation
│   ├── validator.py          # Stage 4: Validation + repair engine
│   ├── schemas.py            # JSON schema contracts
│   └── llm.py                # Claude API wrapper (retry, logging)
├── api/
│   └── server.py             # FastAPI server
├── frontend/
│   └── index.html            # Demo UI
├── evaluation/
│   ├── dataset.json          # 10 real + 10 edge case prompts
│   └── run_eval.py           # Evaluation runner + metrics
├── requirements.txt
├── start.sh
└── README.md
```

---

## API

### `POST /compile`

```json
{
  "prompt": "Build a CRM with login, contacts, dashboard, payments..."
}
```

**Response:**
```json
{
  "success": true,
  "intent": { "app_name": "...", "features": [...], "roles": [...] },
  "system_design": { "entities": [...], "flows": [...], "pages": [...] },
  "db_schema":  { "tables": [...] },
  "api_schema": { "endpoints": [...] },
  "ui_schema":  { "pages": [...] },
  "auth_schema": { "strategy": "jwt", "rules": [...] },
  "assumptions": [...],
  "refinement_notes": [...],
  "issues_found": [...],
  "metrics": {
    "total_latency_seconds": 18.4,
    "retries": 0,
    "issues_detected": 2,
    "tables_generated": 7,
    "endpoints_generated": 24,
    "pages_generated": 8,
    "auth_rules_generated": 15
  }
}
```

---

## Validation + Repair System

The **core differentiator**. Three repair levels:

| Level | Trigger | Action | LLM call? |
|-------|---------|--------|-----------|
| 1 | Missing required fields, type mismatch | Auto-fill with typed defaults | No |
| 2 | Cross-layer inconsistency (error severity) | Targeted re-generation of broken layer | Yes, 1 call |
| 3 | Unresolvable conflict | Document in `issues_found`, continue | No |

Cross-layer checks:
- **API → DB**: every endpoint resource maps to a DB table
- **UI → API**: every component's `api_binding` maps to a real endpoint
- **Auth → Design**: all roles in auth rules exist in system design
- **Pages → Design**: every page in system design has a UI schema entry

---

## Evaluation

```bash
# Run full evaluation (20 prompts)
python evaluation/run_eval.py

# Run only real prompts
python evaluation/run_eval.py --subset real

# Quick test (first 3 prompts)
python evaluation/run_eval.py --limit 3
```

Tracks: success rate, retries per request, failure types, latency, pass rate per prompt.

---

## Design Decisions & Tradeoffs

### Why 5 stages instead of 1 prompt?
Single-prompt approach produces structurally inconsistent output under real-world conditions. Multi-stage gives each concern a dedicated prompt with a focused contract, making validation and repair targeted rather than global.

### Why targeted repair instead of full retry?
Full retry is 4–5x more expensive and often re-introduces different errors. Level-2 targeted repair re-runs only the broken layer with the specific error context, achieving higher reliability at lower cost.

### Latency vs quality
Each pipeline run makes 5–6 LLM calls (4 stages + refinement + optional repair). Average latency: 15–25s. Tradeoff: quality and consistency are significantly higher than single-prompt approaches. For production, stages 1–2 could be cached (same app type → similar architecture).

### Temperature = 0.1
Low temperature for all stages. Deterministic output is more important than creativity here. The LLM's job is structured transformation, not generation.
