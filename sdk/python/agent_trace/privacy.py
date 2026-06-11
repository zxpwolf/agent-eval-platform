"""Privacy utilities for PII detection and masking.

This module provides tools to detect and mask personally identifiable information (PII)
in trace data before storage or export.
"""

import re
from typing import Any, Dict, Optional, Pattern


class PIIMasker:
    """Detects and masks PII in text data.

    Supports detection and masking of:
    - Email addresses
    - Phone numbers
    - IP addresses
    - Credit card numbers
    - Social Security Numbers (SSN)
    - API keys and tokens
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._patterns: Dict[str, Pattern] = {
            "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "phone": re.compile(r'\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b'),
            "ip_address": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
            "credit_card": re.compile(r'\b\d{4}[-.]?\d{4}[-.]?\d{4}[-.]?\d{4}\b'),
            "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            "api_key": re.compile(r'\b(?:sk-[a-zA-Z0-9]{20,}|api[_-]?key[_-]?[=:]\s*\S+)\b'),
        }
        self._mask_values: Dict[str, str] = {
            "email": "[EMAIL_REDACTED]",
            "phone": "[PHONE_REDACTED]",
            "ip_address": "[IP_REDACTED]",
            "credit_card": "[CREDIT_CARD_REDACTED]",
            "ssn": "[SSN_REDACTED]",
            "api_key": "[API_KEY_REDACTED]",
        }

    def mask_text(self, text: str) -> str:
        """Mask PII in a text string."""
        if not self.enabled or not isinstance(text, str):
            return text

        masked = text
        for pii_type, pattern in self._patterns.items():
            masked = pattern.sub(self._mask_values[pii_type], masked)

        return masked

    def mask_data(self, data: Any, max_depth: int = 5) -> Any:
        """Recursively mask PII in data structures."""
        if not self.enabled:
            return data

        if max_depth <= 0:
            return data

        if isinstance(data, str):
            return self.mask_text(data)

        if isinstance(data, dict):
            return {
                key: self.mask_data(value, max_depth - 1)
                for key, value in data.items()
            }

        if isinstance(data, (list, tuple)):
            masked_items = [self.mask_data(item, max_depth - 1) for item in data]
            return type(data)(masked_items)

        return data

    def add_pattern(self, name: str, pattern: str, mask_value: str):
        """Add a custom PII pattern."""
        self._patterns[name] = re.compile(pattern)
        self._mask_values[name] = mask_value

    def remove_pattern(self, name: str):
        """Remove a PII pattern."""
        self._patterns.pop(name, None)
        self._mask_values.pop(name, None)


# Global PII masker instance
_default_masker: Optional[PIIMasker] = None


def get_masker() -> PIIMasker:
    """Get the global PII masker instance."""
    global _default_masker
    if _default_masker is None:
        _default_masker = PIIMasker()
    return _default_masker


def set_masker(masker: PIIMasker):
    """Set the global PII masker."""
    global _default_masker
    _default_masker = masker


def mask_pii(data: Any) -> Any:
    """Convenience function to mask PII in data."""
    return get_masker().mask_data(data)
