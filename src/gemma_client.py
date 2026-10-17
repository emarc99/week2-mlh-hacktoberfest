"""Gemma 4 multimodal client via the Gemini API (google-genai)."""

from __future__ import annotations

import io
import json
import os
import re
import time
from typing import Any

from google import genai
from google.genai import types
from PIL import Image

from src.prompts import PAYMENT_TYPES, USER_PROMPT

# Core model — without this call there is no SlipsLedger product.
GEMMA_MODEL = "gemma-4-26b-a4b-it"
_MAX_IMAGE_EDGE = 1600
_RETRY_ATTEMPTS = 4
_RETRY_BASE_SEC = 1.5


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


def _prepare_image(image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Downscale large uploads so multimodal calls are more reliable."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception:
        return image_bytes, mime_type or "image/jpeg"

    if max(img.size) > _MAX_IMAGE_EDGE:
        img.thumbnail((_MAX_IMAGE_EDGE, _MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue(), "image/jpeg"


def _is_retryable(exc: BaseException) -> bool:
    text = str(exc).lower()
    markers = (
        "500",
        "503",
        "429",
        "internal",
        "unavailable",
        "timeout",
        "temporar",
        "resource_exhausted",
        "deadline",
    )
    return any(m in text for m in markers)


def _friendly_api_error(exc: BaseException) -> str:
    text = str(exc)
    if "INTERNAL" in text or "500" in text:
        return (
            "Gemini API returned a temporary INTERNAL (500) error while calling Gemma 4. "
            "This is usually transient on Google’s side — wait a few seconds and click "
            "Analyze again. If it keeps failing, try a smaller/clearer photo."
        )
    if "429" in text or "resource_exhausted" in text.lower():
        return (
            "Gemini API rate limit hit. Wait briefly, then click Analyze again."
        )
    if "API_KEY" in text.upper() or "403" in text or "401" in text:
        return (
            "Gemini API rejected the key. Check GEMINI_API_KEY in `.env` "
            "(never commit it) and restart Streamlit."
        )
    return f"Gemma API call failed: {text[:500]}"


def analyze_slip(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
    """Send a slip photo to Gemma 4 and return normalized extraction fields."""
    api_key = _require_api_key()
    client = genai.Client(api_key=api_key)
    payload, payload_mime = _prepare_image(image_bytes, mime_type)

    # Gemma via Gemini API is more reliable without system_instruction —
    # role text is folded into USER_PROMPT instead.
    last_error: BaseException | None = None
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=GEMMA_MODEL,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(
                                data=payload, mime_type=payload_mime
                            ),
                            types.Part.from_text(text=USER_PROMPT),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(temperature=0.2),
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
        except Exception as exc:  # noqa: BLE001 — surface friendly API failures
            last_error = exc
            if attempt < _RETRY_ATTEMPTS and _is_retryable(exc):
                time.sleep(_RETRY_BASE_SEC * attempt)
                continue
            raise RuntimeError(_friendly_api_error(exc)) from exc

    raise RuntimeError(_friendly_api_error(last_error or RuntimeError("unknown")))
