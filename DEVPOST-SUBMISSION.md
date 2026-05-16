# ClaudeFlow — UiPath AgentHack 2026 Submission Copy

Updated: 2026-05-16

## Hackathon
- URL: https://uipath-agenthack.devpost.com/
- Deadline: June 29, 2026 at 11:45pm PDT
- Track: Maestro BPMN (Track 1)

---

## Project Name
ClaudeFlow

## Tagline (≤160 chars)
AI-augmented BPMN process orchestration: Claude handles exceptions at every UiPath Maestro stage — retry, escalate, or reroute at runtime, no hard-coded catch blocks.

## What it does
ClaudeFlow connects Claude AI to UiPath Maestro BPMN to create self-healing business process pipelines.

Traditional BPMN processes fail hard when something unexpected happens — a missing field, a reviewer at capacity, an ambiguous risk level. ClaudeFlow replaces every hand-coded exception path with a Claude-powered decision: given the full context of the failure, Claude returns a structured resolution (retry / escalate / reroute / skip / abort) with a specific instruction for the orchestrator to follow.

**Demo: Contract Review Pipeline**

An incoming contract document is:
1. **Classified** by Claude — contract type, risk tier, jurisdiction, parties, completeness score
2. **Routed** into a 4-stage UiPath Maestro BPMN process
3. **Exception-handled** at every stage by Claude when something falls outside the happy path
4. **Escalated** to a human via UiPath Action Center when risk is critical or completeness is too low

ClaudeFlow is not a wrapper — it lives inside the orchestration layer. UiPath starts the BPMN instance; Claude decides what happens when the process hits a wall.

## How we built it
- **Claude 3.5 Sonnet** for document classification and exception resolution (structured JSON output via tool use)
- **UiPath Orchestrator REST API** to start BPMN process instances, monitor stage status, and create Action Center tasks
- **Python bridge** (`claudeflow` package) with four stages mapped to UiPath BPMN activities
- **Prompt caching** for the classification system prompt (saves ~80% of token cost on repeat runs)
- **Full audit log** for every pipeline run — every Claude call, every resolution, every escalation

## Challenges we ran into
- UiPath Maestro BPMN instances are stateful — had to design the Python bridge to poll stage completion rather than use callbacks
- Claude classification JSON schema needed several iterations to match the exact routing fields UiPath needed
- Human-in-loop escalation via Action Center required mapping Claude's "requires_human" flag to a real task payload

## Accomplishments that we're proud of
- Zero hand-coded exception paths — Claude handles every edge case in the demo
- Full pipeline runs in under 2 seconds for low-risk documents (auto-approve path)
- Reviewer load-balancing: Claude picks backup reviewers when the primary is at capacity
- Complete audit trail with timestamps, Claude decisions, and stage durations

## What we learned
Integrating an LLM into a BPMN process requires careful schema design. Claude needs enough context about the BPMN stage to make a good resolution decision — but the context window has to stay bounded. The solution: pass only the stage-level failure description and the document classification summary, not the full document.

## What's next for ClaudeFlow
- Add UiPath Studio XAML process templates that call ClaudeFlow as a custom activity
- Expand to invoice approval and vendor onboarding workflows
- Multi-agent variant: two Claude agents review each other's exception resolution before a final decision

## Built With
claude, uipath-orchestrator, uipath-maestro-bpmn, python, anthropic-sdk, action-center, prompt-caching

## Try it out
- Live demo: https://voiddo.com/devpost/claudeflow/
- GitHub: https://github.com/voidd0/claudeflow-uipath

---

## VIDEO SCRIPT (2-3 min)

### 0:00-0:15 — Problem
"BPMN process exception handling is hard-coded. When something breaks, the process stops or falls to a default path. ClaudeFlow replaces every hard-coded exception with a Claude AI decision."

### 0:15-0:30 — Show the demo page
Open https://voiddo.com/devpost/claudeflow/. Select "Mutual NDA" (medium risk).

### 0:30-0:60 — Run the pipeline
Click "Run ClaudeFlow Pipeline". Show:
- Claude classification output populating (type, risk tier, parties, completeness 78%)
- Stage 1: Intake Validation → EXCEPTION (missing effective_date)
- Claude resolution: reroute — extracted inferred date from context
- Stage 2: Review Assignment → Completed → Legal Team selected
- Stage 3: Approval Gate → Awaiting Human (completeness < 85)
- Audit log streaming in real time

### 0:60-1:30 — High-risk case
Switch to "Enterprise SLA". Run again. Show:
- High risk tier, unlimited liability clause detected
- Stage 2 exception: reviewer at capacity, Claude picks backup
- Stage 3: Escalated to CTO (unlimited liability + jurisdiction mismatch)
- Final status: escalated_to_cto

### 1:30-2:00 — Happy path
Switch to "Employment Offer". Run. Show:
- Low risk, completeness 96%, all fields present
- All stages complete in sequence
- Stage 3: AUTO-APPROVED (no human needed)
- Total: 1175ms

### 2:00-2:20 — Code
Show briefly: claude_classifier.py (classification schema), pipeline.py (4 stages), orchestrator_client.py (UiPath API). "Each stage calls Claude only on exception — it doesn't add latency to the happy path."

### 2:20-2:30 — Close
"ClaudeFlow: AI-augmented BPMN. Every exception, handled. Claude decides. UiPath executes."
