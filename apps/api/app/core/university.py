"""University email classification system.

Provides configurable email pattern matching to determine user category
from university email addresses. This avoids hard-coding assumptions about
email formats and allows easy adaptation when the university changes its
email patterns.
"""

import re

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class EmailClassification:
    """Result of university email classification."""

    def __init__(
        self,
        is_university_email: bool,
        category: str | None = None,
        domain: str | None = None,
        matched_pattern: str | None = None,
    ):
        self.is_university_email = is_university_email
        self.category = category  # "student", "faculty", etc.
        self.domain = domain
        self.matched_pattern = matched_pattern


def extract_email_domain(email: str) -> str:
    """Extract the domain part from an email address."""
    return email.split("@")[-1].lower().strip() if "@" in email else ""


def classify_university_email(email: str) -> EmailClassification:
    """Classify a university email address against configured patterns.

    This system is designed to be configurable — when the university
    changes its email format, only the UNIVERSITY_EMAIL_PATTERNS config
    needs to be updated.

    Args:
        email: The full email address to classify

    Returns:
        EmailClassification with the determination
    """
    email_lower = email.lower().strip()
    domain = extract_email_domain(email_lower)

    patterns = settings.UNIVERSITY_EMAIL_PATTERNS

    for category, pattern_list in patterns.items():
        for pattern_str in pattern_list:
            try:
                if re.match(pattern_str, email_lower):
                    logger.info(
                        "University email classified",
                        email_domain=domain,
                        category=category,
                        pattern=pattern_str,
                    )
                    return EmailClassification(
                        is_university_email=True,
                        category=category,
                        domain=domain,
                        matched_pattern=pattern_str,
                    )
            except re.error as exc:
                logger.error(
                    "Invalid email pattern in configuration",
                    pattern=pattern_str,
                    error=str(exc),
                )
                continue

    logger.info(
        "Email does not match any university pattern",
        email_domain=domain,
    )
    return EmailClassification(
        is_university_email=False,
        category=None,
        domain=domain,
        matched_pattern=None,
    )


def is_valid_university_email(email: str) -> bool:
    """Quick check if an email matches any university pattern."""
    return classify_university_email(email).is_university_email


def get_user_category_from_email(email: str) -> str | None:
    """Get the user category derived from university email pattern.

    Returns None if the email doesn't match any pattern.
    """
    classification = classify_university_email(email)
    return classification.category if classification.is_university_email else None
