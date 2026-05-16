"""
Claude-powered document classifier for ClaudeFlow.
Classifies incoming documents (type, risk tier, jurisdiction,
completeness) and generates structured metadata for BPMN routing.
Also handles exception resolution: given a BPMN stage failure,
Claude proposes the recovery action.
"""

import os
import json
import anthropic
from dataclasses import dataclass
from typing import Literal


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


ContractType = Literal["NDA", "SLA", "employment", "vendor", "licensing", "other"]
RiskTier = Literal["low", "medium", "high", "critical"]
Language = Literal["en", "de", "fr", "es", "ja", "ko", "other"]


@dataclass
class DocumentClassification:
    contract_type: ContractType
    risk_tier: RiskTier
    language: Language
    jurisdiction: str            # e.g. "US-CA", "DE", "EU"
    completeness_score: int      # 0–100
    missing_fields: list[str]
    parties: list[str]           # extracted party names
    summary: str                 # one-sentence human-readable summary
    routing_tag: str             # e.g. "legal-review", "auto-approve", "escalate-cto"
    confidence: int              # 0–100


@dataclass
class ExceptionResolution:
    stage: str                   # BPMN stage where exception occurred
    exception_description: str
    resolution_action: str       # "retry" | "escalate" | "reroute" | "skip" | "abort"
    resolution_detail: str       # specific instruction for the resolution
    estimated_delay_minutes: int
    requires_human: bool


_CLASSIFICATION_SYSTEM = """
You are a contract intelligence classifier for ClaudeFlow, an AI-augmented BPMN process orchestrator.
Your job: analyze a business document and return a structured JSON classification.

Return ONLY valid JSON matching this schema exactly:
{
  "contract_type": "NDA" | "SLA" | "employment" | "vendor" | "licensing" | "other",
  "risk_tier": "low" | "medium" | "high" | "critical",
  "language": "en" | "de" | "fr" | "es" | "ja" | "ko" | "other",
  "jurisdiction": "<jurisdiction string, e.g. US-CA, DE, EU, UK>",
  "completeness_score": <0-100>,
  "missing_fields": ["<field name>", ...],
  "parties": ["<party name>", ...],
  "summary": "<one sentence>",
  "routing_tag": "<one of: auto-approve | legal-review | legal-review-urgent | escalate-cto | flag-for-deletion>",
  "confidence": <0-100>
}

Risk tier guidelines:
- low: standard form, no unusual clauses, completeness >= 85
- medium: non-standard terms, completeness 60-84, or unfamiliar jurisdiction
- high: IP assignment, liability cap < $50k, exclusivity, jurisdiction mismatch
- critical: unlimited liability, missing signatures, suspicious parties, fraud indicators

Routing tag guidelines:
- auto-approve: low risk, completeness >= 90, known parties
- legal-review: medium risk or completeness 60-89
- legal-review-urgent: high risk
- escalate-cto: critical risk or IP assignment
- flag-for-deletion: incomplete stub, blank template, or test document
"""

_EXCEPTION_SYSTEM = """
You are an exception resolver for ClaudeFlow BPMN process orchestration.
A BPMN stage has failed. Return ONLY valid JSON:
{
  "resolution_action": "retry" | "escalate" | "reroute" | "skip" | "abort",
  "resolution_detail": "<specific actionable instruction>",
  "estimated_delay_minutes": <integer>,
  "requires_human": true | false
}

Guidelines:
- retry: transient error, network timeout, temp unavailability — retry after brief delay
- escalate: ambiguous decision, missing required human approval, policy unclear
- reroute: stage not applicable for this document type — use alternate path
- skip: optional stage, safe to bypass given context
- abort: data integrity risk, fraud flag, unrecoverable state
"""


def classify_document(text: str, filename: str = "") -> DocumentClassification:
    """
    Classify a document using Claude.
    text: extracted plaintext content of the document.
    filename: optional filename for additional context.
    """
    user_content = f"Filename: {filename}\n\nDocument content (first 4000 chars):\n{text[:4000]}"

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=_CLASSIFICATION_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()
    data = json.loads(raw)

    return DocumentClassification(
        contract_type=data["contract_type"],
        risk_tier=data["risk_tier"],
        language=data["language"],
        jurisdiction=data["jurisdiction"],
        completeness_score=int(data["completeness_score"]),
        missing_fields=data.get("missing_fields", []),
        parties=data.get("parties", []),
        summary=data["summary"],
        routing_tag=data["routing_tag"],
        confidence=int(data["confidence"]),
    )


def resolve_exception(
    stage: str,
    exception_description: str,
    document_context: dict | None = None,
) -> ExceptionResolution:
    """
    Ask Claude how to resolve a BPMN stage exception.
    document_context: optional dict with classification metadata for smarter resolution.
    """
    ctx_str = ""
    if document_context:
        ctx_str = f"\nDocument context: {json.dumps(document_context, ensure_ascii=False)}"

    user_content = (
        f"BPMN Stage: {stage}\n"
        f"Exception: {exception_description}"
        f"{ctx_str}"
    )

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=_EXCEPTION_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()
    data = json.loads(raw)

    return ExceptionResolution(
        stage=stage,
        exception_description=exception_description,
        resolution_action=data["resolution_action"],
        resolution_detail=data["resolution_detail"],
        estimated_delay_minutes=int(data.get("estimated_delay_minutes", 0)),
        requires_human=bool(data.get("requires_human", False)),
    )


def generate_reviewer_brief(
    document_text: str,
    classification: DocumentClassification,
) -> str:
    """
    Generate a concise one-page reviewer brief for the human-in-loop approval stage.
    Returns markdown-formatted text.
    """
    prompt = (
        f"Generate a concise reviewer brief (max 200 words, markdown) for this document.\n\n"
        f"Classification:\n"
        f"- Type: {classification.contract_type}\n"
        f"- Risk: {classification.risk_tier}\n"
        f"- Jurisdiction: {classification.jurisdiction}\n"
        f"- Parties: {', '.join(classification.parties)}\n"
        f"- Missing fields: {', '.join(classification.missing_fields) or 'none'}\n"
        f"- Summary: {classification.summary}\n\n"
        f"Document excerpt (first 2000 chars):\n{document_text[:2000]}\n\n"
        f"Output: a brief with sections: ## Summary, ## Key Risks, ## Recommended Action"
    )

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()
