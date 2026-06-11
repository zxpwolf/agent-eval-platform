"""Test PII masking functionality."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from agent_trace.privacy import PIIMasker, mask_pii


def test_email_masking():
    """Test email address masking."""
    masker = PIIMasker()
    text = "Contact us at support@example.com or admin@test.org"
    masked = masker.mask_text(text)
    assert "[EMAIL_REDACTED]" in masked
    assert "example.com" not in masked
    print("✓ Email masking works")


def test_phone_masking():
    """Test phone number masking."""
    masker = PIIMasker()
    text = "Call 123-456-7890 or (555) 123-4567"
    masked = masker.mask_text(text)
    assert "[PHONE_REDACTED]" in masked
    print("✓ Phone masking works")


def test_ip_masking():
    """Test IP address masking."""
    masker = PIIMasker()
    text = "Server at 192.168.1.1 responded"
    masked = masker.mask_text(text)
    assert "[IP_REDACTED]" in masked
    assert "192.168.1.1" not in masked
    print("✓ IP masking works")


def test_dict_masking():
    """Test masking in dictionaries."""
    masker = PIIMasker()
    data = {
        "user": "john",
        "email": "john@example.com",
        "phone": "123-456-7890",
        "nested": {
            "contact": "admin@test.org"
        }
    }
    masked = masker.mask_data(data)
    assert masked["email"] == "[EMAIL_REDACTED]"
    assert masked["phone"] == "[PHONE_REDACTED]"
    assert masked["nested"]["contact"] == "[EMAIL_REDACTED]"
    print("✓ Dict masking works")


def test_list_masking():
    """Test masking in lists."""
    masker = PIIMasker()
    data = ["user@example.com", "normal text", "192.168.1.1"]
    masked = masker.mask_data(data)
    assert masked[0] == "[EMAIL_REDACTED]"
    assert masked[1] == "normal text"
    assert masked[2] == "[IP_REDACTED]"
    print("✓ List masking works")


def test_disable_masking():
    """Test disabling masking."""
    masker = PIIMasker(enabled=False)
    text = "Email: user@example.com"
    masked = masker.mask_text(text)
    assert masked == text
    print("✓ Disabled masking works")


def test_custom_pattern():
    """Test adding custom PII pattern."""
    masker = PIIMasker()
    masker.add_pattern("custom_id", r'\bID-\d{4}\b', '[CUSTOM_ID]')
    text = "User ID-1234 accessed resource"
    masked = masker.mask_text(text)
    assert "[CUSTOM_ID]" in masked
    print("✓ Custom pattern works")


if __name__ == "__main__":
    print("PII Masking - Test Suite")
    print("=" * 50)

    tests = [
        test_email_masking,
        test_phone_masking,
        test_ip_masking,
        test_dict_masking,
        test_list_masking,
        test_disable_masking,
        test_custom_pattern,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
