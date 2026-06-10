"""Deterministic outreach quality checks."""

from __future__ import annotations

import re

from pydantic import Field

from saas_lead_agent.schemas import CompanyProfile, CompanySignal, Contact, OutreachDraft
from saas_lead_agent.schemas.base import StrictBaseModel


class OutreachQualityResult(StrictBaseModel):
    quality_score: int = Field(ge=0, le=100)
    passed: bool
    issues: list[str] = Field(default_factory=list)
    personalization_hooks: list[str] = Field(default_factory=list)
    spam_terms: list[str] = Field(default_factory=list)
    placeholder_terms: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=0)


class OutreachQualityThresholds(StrictBaseModel):
    passing_score: int = Field(default=70, ge=0, le=100)
    min_personalization_hooks: int = Field(default=2, ge=0)
    min_body_words: int = Field(default=35, ge=0)
    max_body_words: int = Field(default=200, ge=1)
    min_subject_chars: int = Field(default=8, ge=1)
    max_subject_chars: int = Field(default=120, ge=1)


class OutreachQualityEngine:
    """Score generated outreach copy with deterministic first-pass rules."""

    _SPAM_TERMS = {
        "100% guaranteed",
        "act now",
        "free money",
        "limited time",
        "no risk",
        "risk-free",
        "!!!",
    }
    _CTA_TERMS = {
        "call",
        "chat",
        "connect",
        "demo",
        "discuss",
        "meeting",
        "next week",
        "open to",
        "worth",
    }
    _PLACEHOLDER_LITERALS = {"todo", "lorem ipsum", "insert company", "your company"}
    _PLACEHOLDER_PATTERNS = (
        re.compile(r"\[[^\]]+\]"),
        re.compile(r"\{\{[^}]+\}\}"),
        re.compile(r"\{[^}]+\}"),
    )
    _WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")

    def __init__(self, thresholds: OutreachQualityThresholds | None = None) -> None:
        self.thresholds = thresholds or OutreachQualityThresholds()

    def evaluate(
        self,
        *,
        profile: CompanyProfile | None,
        contact: Contact | None,
        signals: list[CompanySignal],
        draft: OutreachDraft,
    ) -> OutreachQualityResult:
        text = f"{draft.email_subject} {draft.email_body}"
        normalized = text.lower()
        body_words = self._WORD_PATTERN.findall(draft.email_body)
        word_count = len(body_words)

        issues: list[str] = []
        score = 100

        placeholders = self._placeholder_terms(text)
        if placeholders:
            issues.append("draft contains unresolved placeholder text")
            score -= 50

        spam_terms = sorted(term for term in self._SPAM_TERMS if term in normalized)
        if spam_terms:
            issues.append("draft contains spammy or high-pressure wording")
            score -= min(25, 10 * len(spam_terms))

        hooks = self._personalization_hooks(
            normalized=normalized,
            profile=profile,
            contact=contact,
            signals=signals,
        )
        if len(hooks) < self.thresholds.min_personalization_hooks:
            issues.append("draft has low personalization density")
            score -= 20

        if not self._has_cta(normalized):
            issues.append("draft is missing a clear call to action")
            score -= 20

        if word_count < self.thresholds.min_body_words:
            issues.append("email body is too short for useful personalization")
            score -= 15
        elif word_count > self.thresholds.max_body_words:
            issues.append("email body is too long for initial outbound")
            score -= 10

        subject_length = len(draft.email_subject.strip())
        if subject_length < self.thresholds.min_subject_chars:
            issues.append("email subject is too short")
            score -= 10
        elif subject_length > self.thresholds.max_subject_chars:
            issues.append("email subject is too long")
            score -= 10

        quality_score = max(0, min(100, score))
        passed = (
            quality_score >= self.thresholds.passing_score and not placeholders and not spam_terms
        )

        return OutreachQualityResult(
            quality_score=quality_score,
            passed=passed,
            issues=issues,
            personalization_hooks=hooks,
            spam_terms=spam_terms,
            placeholder_terms=placeholders,
            word_count=word_count,
        )

    def _placeholder_terms(self, text: str) -> list[str]:
        found: set[str] = set()
        lowered = text.lower()
        for literal in self._PLACEHOLDER_LITERALS:
            if literal in lowered:
                found.add(literal)
        for pattern in self._PLACEHOLDER_PATTERNS:
            found.update(match.group(0) for match in pattern.finditer(text))
        return sorted(found)

    def _personalization_hooks(
        self,
        *,
        normalized: str,
        profile: CompanyProfile | None,
        contact: Contact | None,
        signals: list[CompanySignal],
    ) -> list[str]:
        hooks: list[str] = []
        if contact and contact.name:
            first_name = contact.name.split()[0].lower()
            if first_name and first_name in normalized:
                hooks.append("contact_name")
        if contact and contact.title and contact.title.lower() in normalized:
            hooks.append("contact_title")
        if profile and profile.name and profile.name.lower() in normalized:
            hooks.append("company_name")
        if profile and self._any_keyword_overlap(profile.products, normalized):
            hooks.append("product_context")
        if profile and profile.funding_stage and profile.funding_stage.lower() in normalized:
            hooks.append("funding_stage")
        if any(self._signal_referenced(signal, normalized) for signal in signals):
            hooks.append("buying_signal")
        return hooks

    def _any_keyword_overlap(self, values: list[str], normalized: str) -> bool:
        for value in values:
            terms = [term for term in self._WORD_PATTERN.findall(value.lower()) if len(term) >= 5]
            if any(term in normalized for term in terms):
                return True
        return False

    def _signal_referenced(self, signal: CompanySignal, normalized: str) -> bool:
        if signal.signal_type in normalized:
            return True
        terms = [
            term for term in self._WORD_PATTERN.findall(signal.details.lower()) if len(term) >= 6
        ]
        return any(term in normalized for term in terms)

    def _has_cta(self, normalized: str) -> bool:
        return any(term in normalized for term in self._CTA_TERMS)
