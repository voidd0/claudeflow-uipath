# UiPath AgentHack 2026 — vøiddo Submission Spec

**Hackathon:** UiPath AgentHack 2026  
**Devpost:** https://uipath-agenthack.devpost.com/  
**Deadline:** June 29, 2026 @ 11:45pm PDT  
**Prize:** $48k+ ($8k Grand Prize, $5k Track winners)  
**Track:** Maestro BPMN (Track 1 — structured process orchestration)  
**Status:** `spec_ready` — build begins next daemon pass  

---

## Project Name

**ClaudeFlow — AI-Augmented Business Process Orchestrator**

---

## Elevator Pitch

ClaudeFlow connects Claude AI to UiPath Maestro BPMN to create self-healing, intelligently-escalating business process pipelines. Instead of rigid hand-coded exception paths, ClaudeFlow uses Claude to classify exceptions at runtime, generate resolution strategies, and decide whether to retry, escalate to human, or reroute — all within a live UiPath Orchestrator-managed BPMN process.

**Demo scenario:** Contract Review & Routing Pipeline  
An incoming document is classified by Claude (contract type, risk level, jurisdiction), validated for completeness, routed through UiPath Maestro BPMN stages (intake → classification → review assignment → approval → archive), with Claude handling any exception that falls outside the happy path (missing fields, ambiguous risk, language mismatch, reviewer unavailable).

---

## Why This Wins

1. **Judges see real business value immediately** — contract processing is a $50B+ enterprise problem every company has.
2. **Deep UiPath Maestro BPMN integration** — uses Orchestrator API, process instances, task assignment, human-in-loop escalation. Not a wrapper — it is the orchestration layer.
3. **Claude coding agent bonus points** — Claude is explicitly in UiPath's bonus list; ClaudeFlow makes Claude the exception-handler and decision brain.
4. **Exception handling depth** — every BPMN path has an AI fallback. Flaky stage? Claude re-plans. Missing data? Claude extracts from raw text. Reviewer load-balanced? Claude picks next available.
5. **6-week build window** — fully achievable by Jun 29.

---

## Architecture

```
[Document Input]
       │
       ▼
[Claude: Document Classification]
  - contract type (NDA / SLA / employment / vendor)
  - risk tier (low / medium / high / critical)
  - jurisdiction, language, completeness score
       │
       ▼
[UiPath Orchestrator API → Start BPMN Process Instance]
       │
       ▼
[Maestro BPMN Stages]
  Stage 1: Intake Validation
      → exception: Claude fills missing fields from document body
  Stage 2: Review Assignment
      → exception: Claude picks backup reviewer from roster
  Stage 3: Approval Gate (Human-in-Loop via UiPath Tasks)
      → escalation: Claude generates summary brief for reviewer
  Stage 4: Archive & Notification
      → exception: Claude retries or logs failure with explanation
       │
       ▼
[Audit Log + Dashboard]
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Process Orchestration | UiPath Maestro BPMN + Orchestrator API |
| AI Brain | Claude claude-sonnet-4-6 (via Anthropic SDK) |
| Language | Python 3.11 (orchestration layer) |
| Document parsing | PyMuPDF + pdfplumber |
| Human-in-loop | UiPath Tasks (Action Center) |
| API Transport | UiPath Orchestrator REST API v2 |
| Logging | Structured JSON → UiPath Insights / local SQLite |
| Demo UI | Simple HTML status dashboard (tools.voiddo.com style) |

---

## Build Plan (6 weeks to Jun 29)

### Week 1 (May 16–22): Foundation
- [ ] Register UiPath Automation Cloud free trial (support@voiddo.com)
- [ ] Create GitHub repo: `voidd0/claudeflow-uipath`
- [ ] Build `orchestrator_client.py` — UiPath Orchestrator REST API wrapper (auth, process start, task query, status)
- [ ] Build `claude_classifier.py` — Claude document classifier (type, risk, completeness, jurisdiction)
- [ ] Unit tests for both modules

### Week 2 (May 23–29): BPMN Process
- [ ] Design and upload Maestro BPMN process (4-stage contract pipeline)
- [ ] Wire Stage 1 (Intake Validation) with Claude exception handler
- [ ] Wire Stage 2 (Review Assignment) with Claude backup selection
- [ ] End-to-end test with sample PDF contracts (3 happy path, 3 exception cases)

### Week 3 (May 30–Jun 5): Human-in-Loop + Exception Depth
- [ ] Integrate UiPath Tasks (Action Center) for Stage 3 approval
- [ ] Build Claude brief generator — one-page summary for human reviewer
- [ ] Build exception retry logic with Claude re-plan on timeout/failure
- [ ] Add audit log with full decision trace (what Claude decided, why)

### Week 4 (Jun 6–12): Dashboard + QA
- [ ] Build HTML status dashboard (live process instances, stage progress, exception counts)
- [ ] Load test: 20 simultaneous process instances
- [ ] Fix all P0/P1 bugs

### Week 5 (Jun 13–19): Demo Package
- [ ] Record 5-min demo video (owner action — needs Devpost + screen recording)
- [ ] Write README with setup instructions, architecture diagram, one-command demo
- [ ] Create Devpost project page draft (owner submits)

### Week 6 (Jun 20–29): Polish + Submit
- [ ] Final QA pass
- [ ] Submit via Devpost before Jun 29 deadline
- [ ] Post on LinkedIn + Reddit r/uipath + r/ClaudeAI for Community Choice bonus

---

## Autonomous vs Owner Actions

**Autonomous (no owner needed):**
- All code, tests, GitHub repo, README, dashboard
- UiPath Automation Cloud free trial registration (support@voiddo.com)
- Devpost project page draft (text, screenshots, architecture)

**Owner-only:**
- Video recording (5-min screen capture demo)
- Final Devpost submission (Devpost login)
- Any UiPath paid tier if free quota insufficient

---

## Judging Alignment

| Criterion | ClaudeFlow approach |
|-----------|-------------------|
| Business impact | Contract processing pipeline — universal enterprise problem |
| UiPath platform depth | Maestro BPMN + Orchestrator API + Tasks (Action Center) + Insights |
| Technical execution | Exception handlers at every stage, Claude re-plan logic, audit trail |
| Deliverable completeness | Working demo + dashboard + README + video |
| Creativity | Claude as live runtime decision-maker inside a BPMN process |
| Presentation quality | Clean dashboard, architecture diagram, structured demo script |
| Coding agent bonus | Claude explicitly listed in UiPath bonus list |

---

## Next Autonomous Action

1. Register UiPath Automation Cloud trial at cloud.uipath.com with support@voiddo.com
2. Create GitHub repo `voidd0/claudeflow-uipath`
3. Build `orchestrator_client.py` stub (auth + process start + task query)
4. Build `claude_classifier.py` stub (document type + risk classification)
5. Update status to `build_active` in FAST-MONEY-RANKING

---

## Expected Value

- **Best case:** Grand Prize $8,000 + Track winner $5,000 = $13,000
- **Mid case:** Runner-up $3,000
- **Min case:** Community exposure + GitHub traffic for ClaudeFlow as open-source product
- **Bonus:** ClaudeFlow can become a standalone vøiddo product (AI BPMN orchestration SaaS, $199/mo tier)

---

*Spec created: 2026-05-16. Build starts: 2026-05-16 daemon pass.*
