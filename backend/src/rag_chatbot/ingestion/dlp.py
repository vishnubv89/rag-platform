"""
Data Loss Prevention — scans text before ingestion.

Two modes:
  1. Regex rules (always active when dlp_enabled=True): detects common PII
     patterns (SSN, credit cards, email, phone, AWS keys).
  2. Nightfall API (when nightfall_api_key is set): cloud-based DLP scan.

Returns DLPResult(allowed, findings) where findings is a list of
{detector, match_count} dicts. Raises DLPBlockedError if blocked.
"""
import re
from dataclasses import dataclass, field

from rag_chatbot.config import settings


class DLPBlockedError(Exception):
    """Raised when ingestion is blocked by DLP policy."""
    def __init__(self, findings: list[dict]):
        self.findings = findings
        super().__init__(f"DLP blocked: {findings}")


@dataclass
class DLPResult:
    allowed: bool
    findings: list[dict] = field(default_factory=list)


_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ssn",         re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b")),
    ("aws_key",     re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
]


async def scan_text(text: str) -> DLPResult:
    """Scan text for PII/secrets. Returns DLPResult; raises DLPBlockedError if blocked."""
    if not settings.dlp_enabled:
        return DLPResult(allowed=True)

    findings: list[dict] = []

    # Regex scan
    for name, pattern in _PATTERNS:
        matches = pattern.findall(text)
        if matches:
            findings.append({"detector": name, "match_count": len(matches)})

    # Nightfall scan (when configured)
    if settings.nightfall_api_key and findings == []:
        findings.extend(await _nightfall_scan(text))

    blocked = any(f["detector"] in ("ssn", "credit_card", "aws_key", "private_key") for f in findings)
    if blocked:
        raise DLPBlockedError(findings)
    return DLPResult(allowed=True, findings=findings)


async def _nightfall_scan(text: str) -> list[dict]:
    """Call Nightfall v3 API. Returns [] on error (fail-open)."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://api.nightfall.ai/v3/scan",
                headers={"Authorization": f"Bearer {settings.nightfall_api_key}"},
                json={
                    "payload": [text[:50_000]],  # Nightfall 50KB limit per item
                    "policy": {
                        "detectionRules": [
                            {"name": "PII", "logicalOp": "ANY",
                             "detectors": [
                                {"detectorType": "NIGHTFALL_DETECTOR",
                                 "nightfallDetector": "CREDIT_CARD_NUMBER",
                                 "minNumFindings": 1, "minConfidence": "LIKELY"},
                                {"detectorType": "NIGHTFALL_DETECTOR",
                                 "nightfallDetector": "US_SOCIAL_SECURITY_NUMBER",
                                 "minNumFindings": 1, "minConfidence": "LIKELY"},
                                {"detectorType": "NIGHTFALL_DETECTOR",
                                 "nightfallDetector": "API_KEY",
                                 "minNumFindings": 1, "minConfidence": "LIKELY"},
                            ]},
                        ]
                    },
                },
            )
        if r.status_code != 200:
            return []
        data = r.json()
        findings = []
        for item in data.get("findings", [[]]):
            for f in item:
                detector = f.get("detector", {}).get("displayName", "unknown")
                findings.append({"detector": detector, "match_count": 1})
        return findings
    except Exception:
        return []  # fail-open
