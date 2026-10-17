"""Prompts for Gemma 4 slip classification and extraction."""

PAYMENT_TYPES = (
    "rent",
    "utility",
    "security",
    "compound_cleaner",
    "service_charge",
    "other",
)

SYSTEM_INSTRUCTION = """You are SlipsLedger's slip analyst for Nigerian rental compounds.
Given a photo of a handwritten or printed payment slip, classify the payment and extract
structured fields. Be precise with amounts and dates. Flag risks that matter in a dispute
(missing amount, unclear payer/payee, overwritten figures, no date, possible duplicate
wording, illegible key fields).

Respond with ONLY valid JSON matching the schema. No markdown fences."""

EXTRACTION_SCHEMA_HINT = """{
  "payment_type": "rent|utility|security|compound_cleaner|service_charge|other",
  "amount": number or null,
  "currency": "NGN" or other ISO-like code,
  "payment_date": "YYYY-MM-DD" or null,
  "payer_name": string or null,
  "payee_name": string or null,
  "property_or_unit": string or null,
  "period_covered": string or null,
  "reference_or_receipt_no": string or null,
  "notes": string or null,
  "confidence": number between 0 and 1,
  "risk_flags": [string],
  "whatsapp_draft": string
}"""

USER_PROMPT = f"""Analyze this payment slip image.

Allowed payment_type values exactly:
- rent
- utility (PHCN/NEPA, water, waste)
- security (vigilante/gate)
- compound_cleaner (sanitation)
- service_charge (estate dues)
- other

Return JSON with this shape:
{EXTRACTION_SCHEMA_HINT}

whatsapp_draft: a short polite WhatsApp message a tenant or agent could send confirming
the payment details you extracted (include type, amount, date, unit if known).
If a field is unreadable, use null and add a risk_flags entry.
"""
