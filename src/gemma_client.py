"""Gemma 4 multimodal client via the Gemini API (google-genai)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from google import genai
from google.genai import types

from src.prompts import PAYMENT_TYPES, SYSTEM_INSTRUCTION, USER_PROMPT

# Core model — without this call there is no SlipsLedger product.
GEMMA_MODEL = "gemma-4-26b-a4b-it"


def _require_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export GEMINI_API_KEY before running Streamlit."
        )
    return key


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text


def _normalize_result(raw: dict[str, Any]) -> dict[str, Any]:
    payment_type = str(raw.get("payment_type") or "other").strip().lower()
    if payment_type not in PAYMENT_TYPES:
        payment_type = "other"

    amount = raw.get("amount")
    try:
        amount = float(amount) if amount is not None and amount != "" else None
    except (TypeError, ValueError):
        amount = None

    confidence = raw.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
        if confidence is not None:
            confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = None

    risk_flags = raw.get("risk_flags") or []
    if isinstance(risk_flags, str):
        risk_flags = [risk_flags]
    risk_flags = [str(f) for f in risk_flags if f]

    return {
        "payment_type": payment_type,
        "amount": amount,
        "currency": raw.get("currency") or "NGN",
        "payment_date": raw.get("payment_date"),
        "payer_name": raw.get("payer_name"),
        "payee_name": raw.get("payee_name"),
        "property_or_unit": raw.get("property_or_unit"),
        "period_covered": raw.get("period_covered"),
        "reference_or_receipt_no": raw.get("reference_or_receipt_no"),
        "notes": raw.get("notes"),
        "confidence": confidence,
        "risk_flags": risk_flags,
        "whatsapp_draft": raw.get("whatsapp_draft") or "",
        "raw_model_text": raw.get("raw_model_text"),
    }


def analyze_slip(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
    """Send a slip photo to Gemma 4 and return normalized extraction fields."""
    api_key = _require_api_key()
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=GEMMA_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    types.Part.from_text(text=USER_PROMPT),
                ],
            )
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2,
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemma returned an empty response.")

    try:
        parsed = json.loads(_strip_json_fences(text))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemma returned non-JSON output: {text[:500]}"
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Gemma JSON was not an object.")

    parsed["raw_model_text"] = text
    return _normalize_result(parsed)
