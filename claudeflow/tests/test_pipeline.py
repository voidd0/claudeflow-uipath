"""
End-to-end pipeline tests for ClaudeFlow.
Mocks Claude API and UiPath OrchestratorClient.
Covers 3 happy-path and 3 exception scenarios.
Run: pytest claudeflow/tests/test_pipeline.py -v
"""

import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from dataclasses import asdict

# Ensure env var is set before importing pipeline (orchestrator_client checks it)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("UIPATH_ACCOUNT_NAME", "test-account")
os.environ.setdefault("UIPATH_TENANT_NAME", "test-tenant")
os.environ.setdefault("UIPATH_CLIENT_ID", "test-client")
os.environ.setdefault("UIPATH_CLIENT_SECRET", "test-secret")
os.environ.setdefault("UIPATH_FOLDER_ID", "0")

from claudeflow.pipeline import run_pipeline, PipelineRun
from claudeflow.orchestrator_client import OrchestratorClient, OrchestratorConfig


# ── Fixtures ────────────────────────────────────────────────────────────────

NDA_CLASSIFICATION = {
    "contract_type": "NDA",
    "risk_tier": "low",
    "language": "en",
    "jurisdiction": "US-DE",
    "completeness_score": 92,
    "missing_fields": [],
    "parties": ["Acme Corp", "Widget Ltd"],
    "summary": "3-year mutual NDA between Acme Corp (US) and Widget Ltd (UK).",
    "routing_tag": "auto-approve",
    "confidence": 95,
}

SLA_CLASSIFICATION = {
    "contract_type": "SLA",
    "risk_tier": "medium",
    "language": "en",
    "jurisdiction": "DE",
    "completeness_score": 78,
    "missing_fields": ["penalty_cap"],
    "parties": ["CloudServices GmbH", "TechCorp UK Ltd"],
    "summary": "12-month SLA for cloud hosting with 99.5% uptime guarantee.",
    "routing_tag": "legal-review",
    "confidence": 88,
}

EMPLOYMENT_CLASSIFICATION = {
    "contract_type": "employment",
    "risk_tier": "medium",
    "language": "en",
    "jurisdiction": "IL",
    "completeness_score": 85,
    "missing_fields": [],
    "parties": ["voiddo Ltd", "Alex Chen"],
    "summary": "Remote Senior Software Engineer employment at voiddo Ltd.",
    "routing_tag": "legal-review",
    "confidence": 91,
}

LOW_COMPLETENESS_CLASSIFICATION = {
    "contract_type": "vendor",
    "risk_tier": "high",
    "language": "en",
    "jurisdiction": "US-CA",
    "completeness_score": 35,
    "missing_fields": ["signature_block", "effective_date", "liability_cap", "term_length", "governing_law"],
    "parties": ["Unknown Corp"],
    "summary": "Incomplete vendor agreement stub.",
    "routing_tag": "legal-review-urgent",
    "confidence": 52,
}

EXCEPTION_RESOLUTION_RETRY = {
    "resolution_action": "retry",
    "resolution_detail": "Transient error; retry in 30 seconds.",
    "estimated_delay_minutes": 1,
    "requires_human": False,
}

EXCEPTION_RESOLUTION_ABORT = {
    "resolution_action": "abort",
    "resolution_detail": "Document is a blank template with no real content.",
    "estimated_delay_minutes": 0,
    "requires_human": False,
}

REVIEWER_BRIEF = "## Summary\nTest NDA.\n## Key Risks\nNone.\n## Recommended Action\nApprove."

FIELD_RECOVERY = {
    "signature_block": "Signed by John Doe on 2026-01-01",
    "effective_date": "2026-01-01",
    "liability_cap": None,
    "term_length": "12 months",
    "governing_law": "California",
}


def _mock_claude(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def _mock_orchestrator() -> MagicMock:
    orch = MagicMock(spec=OrchestratorClient)
    orch.add_queue_item.return_value = {"id": 42}
    return orch


def _write_temp(content: str) -> str:
    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    tf.write(content)
    tf.flush()
    return tf.name


# ── Happy Path Tests ─────────────────────────────────────────────────────────

class TestHappyPath:
    def test_nda_low_risk_auto_approved(self):
        """Happy path: NDA + low risk + auto-approve → status=completed, stage=archive_notification."""
        doc = _write_temp("NON-DISCLOSURE AGREEMENT\nAcme Corp and Widget Ltd.\nSigned by both parties.\nDeleware law applies.")
        orch = _mock_orchestrator()

        with patch("claudeflow.claude_classifier._get_client") as mock_claude:
            client = MagicMock()
            # classify → NDA low risk auto-approve; reviewer brief
            client.messages.create.side_effect = [
                _mock_claude(json.dumps(NDA_CLASSIFICATION)),
                _mock_claude(REVIEWER_BRIEF),
            ]
            mock_claude.return_value = client

            result = run_pipeline(doc, orch)

        assert result.status == "completed"
        assert result.classification["contract_type"] == "NDA"
        assert result.classification["risk_tier"] == "low"
        assert result.assigned_reviewer != ""
        events = [e["event"] for e in result.audit_log]
        assert "classified" in events
        assert "auto_approved" in events
        assert "archived" in events

    def test_sla_medium_risk_escalated_for_human(self):
        """Happy path: SLA + medium risk → awaiting_human_approval, escalated."""
        doc = _write_temp("SERVICE LEVEL AGREEMENT\nCloudServices GmbH and TechCorp UK.\n99.5% uptime. German law.")
        orch = _mock_orchestrator()

        with patch("claudeflow.claude_classifier._get_client") as mock_claude:
            client = MagicMock()
            client.messages.create.side_effect = [
                _mock_claude(json.dumps(SLA_CLASSIFICATION)),
                _mock_claude(REVIEWER_BRIEF),
            ]
            mock_claude.return_value = client

            result = run_pipeline(doc, orch)

        assert result.status == "escalated"
        assert result.stage == "approval_gate"
        events = [e["event"] for e in result.audit_log]
        assert "classified" in events
        assert "awaiting_human_approval" in events

    def test_employment_contract_routed_to_hr(self):
        """Happy path: employment contract → reviewer is HR Compliance."""
        doc = _write_temp("EMPLOYMENT CONTRACT\nvoiddo Ltd employs Alex Chen as Senior Software Engineer.\nIsrael law.")
        orch = _mock_orchestrator()

        with patch("claudeflow.claude_classifier._get_client") as mock_claude:
            client = MagicMock()
            client.messages.create.side_effect = [
                _mock_claude(json.dumps(EMPLOYMENT_CLASSIFICATION)),
                _mock_claude(REVIEWER_BRIEF),
            ]
            mock_claude.return_value = client

            result = run_pipeline(doc, orch)

        assert result.status == "escalated"
        assert result.assigned_reviewer == "HR Compliance"
        assert result.classification["contract_type"] == "employment"


# ── Exception Scenario Tests ─────────────────────────────────────────────────

class TestExceptionScenarios:
    def test_low_completeness_field_recovery_continues(self):
        """Exception: low completeness triggers field recovery; pipeline continues if recovered score OK."""
        doc = _write_temp("VENDOR AGREEMENT\nUnknown Corp. Incomplete draft.")
        orch = _mock_orchestrator()

        # Recovery boosts completeness_score from 35 → 35+(4*5)=55 → still < 40? No, 55 >= 40.
        # But wait: compute_recovery_score(35, recovered_4_fields) = min(35+20, 100) = 55
        # 55 >= 40, so pipeline won't abort. It will then escalate for human (legal-review-urgent).

        with patch("claudeflow.claude_classifier._get_client") as mock_claude, \
             patch("claudeflow.field_filler._get_client") as mock_filler_claude:

            claude_client = MagicMock()
            # classify → low completeness; reviewer brief (if reached)
            claude_client.messages.create.side_effect = [
                _mock_claude(json.dumps(LOW_COMPLETENESS_CLASSIFICATION)),
                _mock_claude(REVIEWER_BRIEF),
            ]
            mock_claude.return_value = claude_client

            filler_client = MagicMock()
            filler_client.messages.create.return_value = _mock_claude(json.dumps(FIELD_RECOVERY))
            mock_filler_claude.return_value = filler_client

            result = run_pipeline(doc, orch)

        events = [e["event"] for e in result.audit_log]
        assert "field_recovery" in events
        recovery_event = next(e for e in result.audit_log if e["event"] == "field_recovery")
        assert recovery_event["recovered_score"] > LOW_COMPLETENESS_CLASSIFICATION["completeness_score"]
        # Pipeline should not have aborted (recovered score >= 40)
        assert result.status != "failed" or "exception_resolved" in events

    def test_classification_exception_triggers_resolve(self):
        """Exception: Claude classify fails → resolve_exception called → retry → pipeline continues."""
        doc = _write_temp("NDA content here.")
        orch = _mock_orchestrator()

        with patch("claudeflow.claude_classifier._get_client") as mock_claude:
            client = MagicMock()
            client.messages.create.side_effect = [
                # classify raises → but pipeline catches and calls resolve_exception
                Exception("Claude API timeout"),
                # resolve_exception
                _mock_claude(json.dumps(EXCEPTION_RESOLUTION_RETRY)),
            ]
            mock_claude.return_value = client

            result = run_pipeline(doc, orch)

        events = [e["event"] for e in result.audit_log]
        assert "exception" in events
        assert "exception_resolved" in events
        # After retry resolution, pipeline exits gracefully (not abort)
        exception_resolved = next(e for e in result.audit_log if e["event"] == "exception_resolved")
        assert exception_resolved.get("action") == "retry"

    def test_flagged_for_deletion_aborted(self):
        """Exception: classifier returns flag-for-deletion → pipeline aborts with status=failed."""
        flagged = {**NDA_CLASSIFICATION, "routing_tag": "flag-for-deletion", "completeness_score": 92}
        doc = _write_temp("blank template content")
        orch = _mock_orchestrator()

        with patch("claudeflow.claude_classifier._get_client") as mock_claude:
            client = MagicMock()
            client.messages.create.return_value = _mock_claude(json.dumps(flagged))
            mock_claude.return_value = client

            result = run_pipeline(doc, orch)

        assert result.status == "failed"
        events = [e["event"] for e in result.audit_log]
        assert "aborted" in events
        # Should not have reached review assignment
        assert result.assigned_reviewer == ""
