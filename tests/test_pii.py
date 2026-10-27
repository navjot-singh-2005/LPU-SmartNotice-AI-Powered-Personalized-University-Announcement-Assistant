from app.services.pii_redaction_service import PIIRedactionService

def test_pii_redaction():
    service = PIIRedactionService()
    raw_text = "Please contact Student Representative at test.student@lpu.co.in or call 9876543210 (Reg No: 12015432)."
    redacted, count = service.redact_pii(raw_text)

    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_REG_NO]" in redacted
    assert "9876543210" not in redacted
    assert "test.student@lpu.co.in" not in redacted
    assert count >= 3
