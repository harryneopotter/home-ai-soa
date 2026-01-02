import re
from typing import Dict, Any, Tuple, List

PII_PATTERNS = {
    "credit_card": {
        "pattern": r"\b(?:4[0-9]{3}|5[1-5][0-9]{2}|3[47][0-9]{2}|6(?:011|5[0-9]{2}))[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{3,4}\b",
        "redact": lambda m: f"****-****-****-{m.group()[-4:]}",
        "severity": "critical",
    },
    "bank_account": {
        "pattern": r"\b(?:account|acct)[#:\s]*([0-9]{6,17})\b",
        "redact": lambda m: f"{m.group(0).split(m.group(1))[0]}****{m.group(1)[-4:]}",
        "severity": "critical",
    },
    "routing_number": {
        "pattern": r"\b(?:routing|rtg|aba)[#:\s]*([0-9]{9})\b",
        "redact": lambda m: f"{m.group(0).split(m.group(1))[0]}[ROUTING REDACTED]",
        "severity": "critical",
    },
    "ssn": {
        "pattern": r"\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b",
        "redact": "[SSN REDACTED]",
        "severity": "critical",
    },
    "ein": {
        "pattern": r"\b[0-9]{2}-[0-9]{7}\b",
        "redact": "[TAX ID REDACTED]",
        "severity": "high",
    },
    "phone": {
        "pattern": r"\b(?:\+1[-.\s]?)?(?:\(?[0-9]{3}\)?[-.\s]?)?[0-9]{3}[-.\s]?[0-9]{4}\b",
        "redact": lambda m: f"***-***-{m.group()[-4:]}",
        "severity": "medium",
    },
    "email": {
        "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "redact": lambda m: f"{m.group()[0]}***@***.{m.group().split('.')[-1]}",
        "severity": "medium",
    },
    "cvv": {
        "pattern": r"\b(?:cvv|cvc|csc)[:\s]*([0-9]{3,4})\b",
        "redact": lambda m: f"{m.group(0).split(m.group(1))[0]}[CVV REDACTED]",
        "severity": "critical",
    },
    "card_expiry": {
        "pattern": r"\b(?:exp|expir)[a-z]*[:\s]*([0-9]{2}/[0-9]{2,4})\b",
        "redact": lambda m: f"{m.group(0).split(m.group(1))[0]}[EXPIRY REDACTED]",
        "severity": "high",
    },
}


class PIIRedactor:
    def __init__(self, patterns: Dict[str, Any] = PII_PATTERNS):
        self.patterns = patterns

    def redact(self, text: str) -> Tuple[str, Dict[str, int]]:
        if not text:
            return "", {}

        redacted_text = text
        pii_counts = {}

        for pii_type, config in self.patterns.items():
            pattern = config["pattern"]
            redact_fn = config["redact"]

            matches = re.findall(pattern, redacted_text, flags=re.IGNORECASE)
            if matches:
                pii_counts[pii_type] = len(matches)
                redacted_text = re.sub(
                    pattern, redact_fn, redacted_text, flags=re.IGNORECASE
                )

        return redacted_text, pii_counts


if __name__ == "__main__":
    test_text = """
    My credit card is 4111-1111-1111-1234 and my bank account is account #1234567890.
    My SSN is 123-45-6789. Contact me at 555-123-4567 or test@example.com.
    CVV: 123, Exp: 12/25.
    """
    redactor = PIIRedactor()
    redacted, counts = redactor.redact(test_text)
    print(f"Redacted Text:\n{redacted}")
    print(f"PII Counts: {counts}")
