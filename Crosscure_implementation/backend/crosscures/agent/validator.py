"""Rule-based response validator — safety checks before returning to patient/physician."""
import re
from typing import List


DOSE_CHANGE_PATTERNS = [
    r"\b(increase|decrease|double|halve|stop taking|discontinue|change your dose)\b",
    r"\btake \d+\s?(mg|ml|mcg|units?)\b",
    r"\binstead of\b.*\b(mg|dose)\b",
]

DIAGNOSTIC_PATTERNS = [
    r"\byou have\b",
    r"\byou are diagnosed\b",
    r"\byou (likely|probably|definitely) have\b",
]

FABRICATION_PHRASES = [
    "according to your records from",
    "your doctor at",
    "your lab result from",
]


class ValidationResult:
    def __init__(self, is_valid: bool, violations: List[str], sanitized_output: str):
        self.is_valid = is_valid
        self.violations = violations
        self.sanitized_output = sanitized_output


SAFETY_DISCLAIMER = (
    "⚠️ Note: The following information is for context only and does not constitute medical advice. "
    "Please consult your healthcare provider before making any changes to your treatment.\n\n"
)


def validate_response(output: str, output_type: str = "patient_message") -> ValidationResult:
    violations = []
    text_lower = output.lower()

    for pattern in DOSE_CHANGE_PATTERNS:
        if re.search(pattern, text_lower):
            violations.append(f"Potential dosage instruction detected: pattern '{pattern}'")

    for pattern in DIAGNOSTIC_PATTERNS:
        if re.search(pattern, text_lower):
            violations.append(f"Potential diagnostic conclusion: pattern '{pattern}'")

    is_valid = len(violations) == 0
    sanitized = output if is_valid else SAFETY_DISCLAIMER + output

    return ValidationResult(is_valid=is_valid, violations=violations, sanitized_output=sanitized)
