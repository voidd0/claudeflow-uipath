# ClaudeFlow — AI-Augmented BPMN Process Orchestrator

**UiPath AgentHack 2026 submission** | Track: Maestro BPMN | Prize: $8k–$48k

ClaudeFlow connects [Claude AI](https://anthropic.com/claude) to UiPath Maestro BPMN to create self-healing, intelligently-escalating business process pipelines. Instead of rigid hand-coded exception paths, ClaudeFlow uses Claude to classify exceptions at runtime, generate resolution strategies, and decide whether to retry, escalate to a human, or reroute — all within a live UiPath Orchestrator-managed BPMN process.

---

## Demo: Contract Review Pipeline

An incoming document is:
1. **Classified** by Claude (contract type, risk level, jurisdiction, completeness)
2. **Routed** through UiPath Maestro BPMN (intake → classification → review assignment → approval → archive)
3. **Exception-handled** at every stage — Claude decides retry / escalate / reroute when something goes wrong
4. **Escalated** to a human reviewer via UiPath Action Center for high-risk or critical documents

```
[Document Input]
       │
       ▼
[Claude: Document Classification]
  contract type · risk tier · jurisdiction · completeness score
       │
       ▼
[UiPath Orchestrator → Start Maestro BPMN Process]
       │
   ┌───┴───────────────────────────────────────┐
   │  Stage 1: Intake Validation               │
   │    → exception: Claude fills missing fields│
   │  Stage 2: Review Assignment               │
   │    → exception: Claude picks backup        │
   │  Stage 3: Approval Gate (Human-in-Loop)   │
   │    → Claude generates reviewer brief       │
   │  Stage 4: Archive & Notification          │
   │    → exception: Claude retry or log        │
   └───────────────────────────────────────────┘
       │
       ▼
[Audit Log + Status Dashboard]
```

---

## Quick Start

```bash
git clone https://github.com/voidd0/claudeflow-uipath
cd claudeflow-uipath
pip install -r requirements.txt

# Set environment variables
export ANTHROPIC_API_KEY=your_key
export UIPATH_ACCOUNT_NAME=your_account
export UIPATH_TENANT_NAME=your_tenant
export UIPATH_CLIENT_ID=your_client_id
export UIPATH_CLIENT_SECRET=your_client_secret
export UIPATH_FOLDER_ID=your_folder_id

# Run pipeline on a document
python3 -m claudeflow.pipeline contracts/sample_nda.txt

# Run tests
pytest claudeflow/tests/ -v
```

---

## Architecture

| Layer | Technology |
|-------|-----------|
| Process Orchestration | UiPath Maestro BPMN + Orchestrator REST API v2 |
| AI Brain | Claude claude-sonnet-4-6 (Anthropic) |
| Language | Python 3.10+ |
| Document parsing | PyMuPDF + pdfplumber |
| Human-in-loop | UiPath Tasks (Action Center) |
| Tests | pytest (12 passing — 6 unit + 6 e2e, fully mocked) |

---

## Key Features

- **Self-healing exceptions** — every BPMN stage has a Claude-powered exception handler; no stage fails silently
- **Risk-aware routing** — Claude classifies risk tier (low/medium/high/critical) and selects the appropriate reviewer from the roster
- **Human-in-loop integration** — critical and high-risk documents pause for human approval via UiPath Action Center
- **Reviewer briefs** — Claude generates a concise markdown brief for human reviewers (summary, key risks, recommended action)
- **Full audit log** — every decision, exception, and resolution is logged with timestamps and stage context
- **Missing-field recovery** — Stage 1 exception: when completeness is low, Claude extracts missing fields directly from the document text and recomputes the score before deciding to abort
- **Coding agent bonus** — Claude is listed in UiPath's official bonus coding agents list; ClaudeFlow uses it as the runtime decision brain

---

## Project Structure

```
claudeflow/
├── __init__.py
├── orchestrator_client.py   # UiPath Orchestrator REST API wrapper
├── claude_classifier.py     # Claude: classify + resolve + brief
├── field_filler.py          # Stage 1 exception: Claude recovers missing fields
├── pipeline.py              # Main 4-stage pipeline orchestrator
├── demo/
│   └── dashboard.html       # Status dashboard UI
└── tests/
    ├── test_classifier.py   # 6 unit tests (mocked)
    └── test_pipeline.py     # 6 e2e pipeline tests (mocked orchestrator + Claude)

contracts/
├── sample_nda.txt           # NDA: Acme Corp / Widget Ltd
├── sample_sla.txt           # SLA: CloudServices GmbH / TechCorp UK
└── sample_employment.txt    # Employment: voiddo Ltd / Senior Engineer
```

---

## Built by vøiddo

[vøiddo](https://voiddo.com) is a small independent studio shipping AI-flavoured products, browser extensions, and developer tools.  
Tools: [tools.voiddo.com](https://tools.voiddo.com) · Flagship: [scrb.voiddo.com](https://scrb.voiddo.com)
