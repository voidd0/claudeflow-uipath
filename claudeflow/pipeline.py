"""
ClaudeFlow main pipeline.
Orchestrates the 4-stage contract review BPMN process:
  1. Intake Validation (Claude classifies document)
  2. Review Assignment (Claude picks reviewer)
  3. Approval Gate (Human-in-loop via UiPath Tasks)
  4. Archive & Notification

Each stage has a Claude-powered exception handler.
"""

import os
import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from claudeflow.orchestrator_client import OrchestratorClient, OrchestratorConfig, client_from_env
from claudeflow.claude_classifier import (
    classify_document,
    resolve_exception,
    generate_reviewer_brief,
    DocumentClassification,
)
from claudeflow.field_filler import fill_missing_fields, compute_recovery_score


log = logging.getLogger("claudeflow.pipeline")


REVIEWER_ROSTER = [
    {"name": "Legal Team", "email": "legal@example.com", "specialties": ["NDA", "licensing"]},
    {"name": "Procurement", "email": "procurement@example.com", "specialties": ["vendor", "SLA"]},
    {"name": "HR Compliance", "email": "hr@example.com", "specialties": ["employment"]},
    {"name": "CTO Office", "email": "cto@example.com", "specialties": ["critical"]},
]


@dataclass
class PipelineRun:
    run_id: str
    document_path: str
    stage: str = "pending"
    classification: dict | None = None
    assigned_reviewer: str = ""
    task_id: int | None = None
    job_id: int | None = None
    status: str = "running"  # running | completed | failed | escalated
    audit_log: list[dict] = None

    def __post_init__(self):
        if self.audit_log is None:
            self.audit_log = []

    def log_event(self, event: str, detail: str = "", **kwargs):
        entry = {"ts": time.time(), "stage": self.stage, "event": event, "detail": detail, **kwargs}
        self.audit_log.append(entry)
        log.info("[%s] %s — %s %s", self.run_id, self.stage, event, detail)


def _pick_reviewer(classification: DocumentClassification) -> dict:
    """Route to the right reviewer based on contract type and risk."""
    if classification.risk_tier == "critical":
        return REVIEWER_ROSTER[3]  # CTO Office
    for r in REVIEWER_ROSTER:
        if classification.contract_type in r["specialties"]:
            return r
    return REVIEWER_ROSTER[0]  # Legal Team fallback


def run_pipeline(document_path: str, orchestrator: OrchestratorClient) -> PipelineRun:
    """
    Execute the full 4-stage contract review pipeline for a single document.
    Returns a PipelineRun with complete audit log.
    """
    run_id = f"cf-{int(time.time())}"
    run = PipelineRun(run_id=run_id, document_path=document_path)
    doc_text = Path(document_path).read_text(encoding="utf-8", errors="ignore")
    clf: DocumentClassification | None = None

    # ── Stage 1: Intake Validation ────────────────────────────────────────────
    run.stage = "intake_validation"
    run.log_event("started")
    try:
        clf = classify_document(doc_text, filename=Path(document_path).name)
        run.classification = asdict(clf)
        run.log_event("classified",
                      contract_type=clf.contract_type,
                      risk_tier=clf.risk_tier,
                      completeness=clf.completeness_score,
                      routing_tag=clf.routing_tag)

        if clf.routing_tag == "flag-for-deletion":
            run.status = "failed"
            run.log_event("aborted", detail="Document flagged for deletion by classifier")
            return run

        # Attempt field recovery before deciding to abort
        if clf.missing_fields and clf.completeness_score < 75:
            recovered = fill_missing_fields(doc_text, clf.missing_fields, Path(document_path).name)
            recovered_score = compute_recovery_score(clf.completeness_score, recovered)
            run.log_event("field_recovery",
                          recovered_count=sum(1 for v in recovered.values() if v),
                          original_score=clf.completeness_score,
                          recovered_score=recovered_score,
                          fields=recovered)
            run.classification["recovered_fields"] = recovered
            run.classification["completeness_score"] = recovered_score
            clf = DocumentClassification(**{**asdict(clf), "completeness_score": recovered_score})

        if clf.completeness_score < 40:
            resolution = resolve_exception(
                stage="intake_validation",
                exception_description=f"Completeness score too low after recovery: {clf.completeness_score}",
                document_context=asdict(clf),
            )
            run.log_event("exception_resolved",
                          action=resolution.resolution_action,
                          detail=resolution.resolution_detail)
            if resolution.resolution_action == "abort":
                run.status = "failed"
                return run

    except Exception as exc:
        run.log_event("exception", detail=str(exc))
        resolution = resolve_exception("intake_validation", str(exc))
        run.log_event("exception_resolved",
                      action=resolution.resolution_action,
                      detail=resolution.resolution_detail)
        if resolution.resolution_action == "abort":
            run.status = "failed"
            return run

    # ── Stage 2: Review Assignment ────────────────────────────────────────────
    if clf is None:
        run.log_event("skipped", detail="Stage 1 did not produce classification; cannot assign reviewer")
        run.status = "failed"
        return run

    run.stage = "review_assignment"
    run.log_event("started")
    try:
        reviewer = _pick_reviewer(clf)
        run.assigned_reviewer = reviewer["name"]
        run.log_event("assigned", reviewer=reviewer["name"], email=reviewer["email"])
    except Exception as exc:
        run.log_event("exception", detail=str(exc))
        resolution = resolve_exception("review_assignment", str(exc), asdict(clf))
        run.log_event("exception_resolved", action=resolution.resolution_action,
                      detail=resolution.resolution_detail)
        if resolution.resolution_action in ("abort", "escalate"):
            run.status = "escalated"
            return run

    # ── Stage 3: Approval Gate (Human-in-Loop) ────────────────────────────────
    run.stage = "approval_gate"
    run.log_event("started")
    try:
        brief = generate_reviewer_brief(doc_text, clf)
        run.log_event("brief_generated", chars=len(brief))
        # In production: orchestrator.add_queue_item / start UiPath task
        # Here we record the task payload for demo purposes
        task_payload = {
            "document_path": document_path,
            "classification": asdict(clf),
            "reviewer": reviewer,
            "brief": brief,
        }
        run.log_event("task_payload_ready", reviewer=reviewer["name"])
        # Simulate auto-approval for low-risk in demo mode
        if clf.risk_tier == "low" and clf.routing_tag == "auto-approve":
            run.log_event("auto_approved", detail="Low-risk auto-approve path")
        else:
            run.log_event("awaiting_human_approval", requires_human=True)
            run.status = "escalated"
            return run
    except Exception as exc:
        run.log_event("exception", detail=str(exc))
        resolution = resolve_exception("approval_gate", str(exc), asdict(clf))
        run.log_event("exception_resolved", action=resolution.resolution_action)

    # ── Stage 4: Archive & Notification ──────────────────────────────────────
    run.stage = "archive_notification"
    run.log_event("started")
    try:
        archive_path = Path(document_path).with_suffix(".processed.json")
        archive_data = {
            "run_id": run.run_id,
            "classification": asdict(clf),
            "reviewer": reviewer,
            "status": "archived",
        }
        archive_path.write_text(json.dumps(archive_data, indent=2))
        run.log_event("archived", path=str(archive_path))
        run.status = "completed"
    except Exception as exc:
        run.log_event("exception", detail=str(exc))
        resolution = resolve_exception("archive_notification", str(exc))
        run.log_event("exception_resolved", action=resolution.resolution_action)
        if resolution.resolution_action != "skip":
            run.status = "failed"

    return run


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python -m claudeflow.pipeline <document.txt>")
        sys.exit(1)
    orchestrator = client_from_env()
    result = run_pipeline(sys.argv[1], orchestrator)
    print(json.dumps(asdict(result), indent=2, default=str))
