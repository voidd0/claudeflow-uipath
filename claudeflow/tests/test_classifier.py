"""
Unit tests for ClaudeFlow claude_classifier module.
Run: pytest tests/test_classifier.py -v
Tests use mocked Claude responses to avoid API calls.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from claudeflow.claude_classifier import (
    classify_document,
    resolve_exception,
    generate_reviewer_brief,
    DocumentClassification,
    ExceptionResolution,
)


SAMPLE_NDA_TEXT = """
NON-DISCLOSURE AGREEMENT
This Agreement is entered into as of January 15, 2026 between Acme Corp,
a Delaware corporation, and Widget Ltd, a UK limited company.
The parties agree to keep confidential all proprietary information shared
under this agreement for a period of 3 years.
Governing law: State of Delaware, United States.
"""

SAMPLE_CLASSIFICATION_JSON = {
    "contract_type": "NDA",
    "risk_tier": "low",
    "language": "en",
    "jurisdiction": "US-DE",
    "completeness_score": 82,
    "missing_fields": ["signature_block", "effective_date_confirmation"],
    "parties": ["Acme Corp", "Widget Ltd"],
    "summary": "3-year mutual NDA between Acme Corp (US) and Widget Ltd (UK), governed by Delaware law.",
    "routing_tag": "legal-review",
    "confidence": 91,
}

SAMPLE_EXCEPTION_JSON = {
    "resolution_action": "retry",
    "resolution_detail": "Reviewer mailbox temporarily unavailable. Retry assignment after 5 minutes.",
    "estimated_delay_minutes": 5,
    "requires_human": False,
}


def _mock_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


class TestClassifyDocument:
    def test_happy_path(self):
        with patch("claudeflow.claude_classifier._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _mock_message(
                json.dumps(SAMPLE_CLASSIFICATION_JSON)
            )
            mock_get.return_value = mock_client

            result = classify_document(SAMPLE_NDA_TEXT, filename="nda_2026.pdf")

        assert isinstance(result, DocumentClassification)
        assert result.contract_type == "NDA"
        assert result.risk_tier == "low"
        assert result.jurisdiction == "US-DE"
        assert result.completeness_score == 82
        assert "Acme Corp" in result.parties
        assert result.routing_tag == "legal-review"
        assert result.confidence == 91

    def test_truncates_long_text(self):
        """Classifier must not send more than 4000 chars to Claude."""
        long_text = "x" * 10000
        with patch("claudeflow.claude_classifier._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _mock_message(
                json.dumps(SAMPLE_CLASSIFICATION_JSON)
            )
            mock_get.return_value = mock_client

            classify_document(long_text)

            call_args = mock_client.messages.create.call_args
            user_msg = call_args.kwargs["messages"][0]["content"]
            assert len(user_msg) <= 4200  # filename + label + 4000 content

    def test_invalid_json_raises(self):
        with patch("claudeflow.claude_classifier._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _mock_message("not json at all")
            mock_get.return_value = mock_client

            with pytest.raises(json.JSONDecodeError):
                classify_document(SAMPLE_NDA_TEXT)


class TestResolveException:
    def test_retry_resolution(self):
        with patch("claudeflow.claude_classifier._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _mock_message(
                json.dumps(SAMPLE_EXCEPTION_JSON)
            )
            mock_get.return_value = mock_client

            result = resolve_exception(
                stage="review_assignment",
                exception_description="Reviewer mailbox returned 503",
                document_context={"contract_type": "NDA", "risk_tier": "low"},
            )

        assert isinstance(result, ExceptionResolution)
        assert result.resolution_action == "retry"
        assert result.estimated_delay_minutes == 5
        assert result.requires_human is False
        assert result.stage == "review_assignment"

    def test_escalation_resolution(self):
        escalate_json = {
            "resolution_action": "escalate",
            "resolution_detail": "Critical risk contract requires senior legal review.",
            "estimated_delay_minutes": 60,
            "requires_human": True,
        }
        with patch("claudeflow.claude_classifier._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _mock_message(
                json.dumps(escalate_json)
            )
            mock_get.return_value = mock_client

            result = resolve_exception(
                stage="approval_gate",
                exception_description="No approver available, risk tier is critical",
            )

        assert result.resolution_action == "escalate"
        assert result.requires_human is True
        assert result.estimated_delay_minutes == 60


class TestGenerateReviewerBrief:
    def test_returns_markdown(self):
        brief_text = "## Summary\nThis is an NDA.\n## Key Risks\nNone.\n## Recommended Action\nApprove."
        with patch("claudeflow.claude_classifier._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _mock_message(brief_text)
            mock_get.return_value = mock_client

            from claudeflow.claude_classifier import DocumentClassification
            clf = DocumentClassification(
                contract_type="NDA",
                risk_tier="low",
                language="en",
                jurisdiction="US-DE",
                completeness_score=82,
                missing_fields=[],
                parties=["Acme Corp"],
                summary="Test NDA",
                routing_tag="legal-review",
                confidence=90,
            )
            result = generate_reviewer_brief(SAMPLE_NDA_TEXT, clf)

        assert "## Summary" in result
        assert "## Key Risks" in result
