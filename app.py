"""SlipsLedger — photo of a payment slip → Gemma 4 → SQLite ledger + CSV."""

from __future__ import annotations

import io
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

from src.db import export_csv, init_db, list_slips, save_slip
from src.gemma_client import GEMMA_MODEL, analyze_slip
from src.prompts import PAYMENT_TYPES

load_dotenv()
init_db()

st.set_page_config(page_title="SlipsLedger", page_icon="🧾", layout="wide")
st.title("SlipsLedger")
st.caption(
    f"Photo of a rent/utility/security slip → **{GEMMA_MODEL}** "
    "(Gemma 4 via Gemini API) → structured ledger + CSV."
)

if not os.getenv("GEMINI_API_KEY", "").strip():
    st.warning(
        "GEMINI_API_KEY is not set. Copy `.env.example` to `.env`, add your Gemini API key, "
        "and restart. Without Gemma there is no product."
    )

# ---------------------------------------------------------------------------
# 1) Upload
# ---------------------------------------------------------------------------
st.header("1. Upload slip")
uploaded = st.file_uploader(
    "Image of handwritten or printed slip (PNG / JPG / WEBP)",
    type=["png", "jpg", "jpeg", "webp"],
)

if uploaded is not None:
    image_bytes = uploaded.getvalue()
    mime = uploaded.type or "image/jpeg"
    try:
        st.image(
            Image.open(io.BytesIO(image_bytes)),
            caption=uploaded.name,
            use_container_width=True,
        )
    except Exception:
        st.info(f"Uploaded: {uploaded.name}")

    if st.button("Analyze with Gemma 4", type="primary", use_container_width=True):
        with st.spinner(f"Calling {GEMMA_MODEL}…"):
            try:
                result = analyze_slip(image_bytes, mime_type=mime)
            except Exception as exc:
                st.error(str(exc))
                st.stop()
        st.session_state["last_result"] = result
        st.session_state["last_filename"] = uploaded.name
        # Auto-save every successful analyze so ledger/CSV are never "missing"
        row_id = save_slip(result, source_filename=uploaded.name)
        st.session_state["last_saved_id"] = row_id

result = st.session_state.get("last_result")

# ---------------------------------------------------------------------------
# 2) Results (full width — no side-by-side squeeze)
# ---------------------------------------------------------------------------
st.header("2. Gemma results")
if not result:
    st.info("Upload a slip and click **Analyze with Gemma 4** to see classification, fields, risk flags, and WhatsApp text here.")
else:
    saved_id = st.session_state.get("last_saved_id")
    if saved_id is not None:
        st.success(f"Saved to SQLite ledger as id **{saved_id}**.")

    st.subheader("Classification")
    st.markdown(f"**Payment type:** `{result.get('payment_type')}`")
    st.markdown(f"**Confidence:** {result.get('confidence')}")

    st.subheader("Extracted fields")
    fields = {
        "Amount": f"{result.get('amount')} {result.get('currency') or ''}".strip(),
        "Payment date": result.get("payment_date"),
        "Payer": result.get("payer_name"),
        "Payee": result.get("payee_name"),
        "Unit / property": result.get("property_or_unit"),
        "Period covered": result.get("period_covered"),
        "Reference / receipt no.": result.get("reference_or_receipt_no"),
        "Notes": result.get("notes"),
    }
    for label, value in fields.items():
        st.markdown(f"**{label}:** {value if value not in (None, '') else '—'}")

    st.subheader("Risk flags")
    flags = result.get("risk_flags") or []
    if flags:
        for flag in flags:
            st.warning(flag)
    else:
        st.success("No risk flags")

    st.subheader("WhatsApp message")
    st.caption(
        "Copy the text below and paste into WhatsApp to confirm the payment. "
        "Select all in the box (Ctrl+A) then Ctrl+C, or copy from the code block."
    )
    draft = result.get("whatsapp_draft") or ""
    if draft:
        st.code(draft, language=None)
        st.text_area(
            "WhatsApp-ready confirmation (editable before copy)",
            value=draft,
            height=160,
            key="whatsapp_draft_area",
        )
    else:
        st.warning("Gemma did not return a WhatsApp draft for this slip.")

    with st.expander("Raw extracted JSON"):
        st.json({k: v for k, v in result.items() if k != "raw_model_text"})

    if st.button("Save again to ledger", use_container_width=True):
        row_id = save_slip(
            result,
            source_filename=st.session_state.get("last_filename"),
        )
        st.session_state["last_saved_id"] = row_id
        st.success(f"Saved again as id **{row_id}**.")

# ---------------------------------------------------------------------------
# 3) Ledger + CSV (always visible — not hidden in a tab)
# ---------------------------------------------------------------------------
st.header("3. SQLite ledger & CSV export")
st.caption(f"Database file: `{Path('data') / 'slips.db'}`")

filter_type = st.selectbox(
    "Filter by payment type",
    options=["all", *PAYMENT_TYPES],
    key="ledger_filter",
)
rows = list_slips(payment_type=None if filter_type == "all" else filter_type)

if not rows:
    st.info("No slips in the ledger yet. Analyze a slip above — it auto-saves here.")
else:
    display = [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "payment_type": row["payment_type"],
            "amount": row["amount"],
            "currency": row["currency"],
            "payment_date": row["payment_date"],
            "payer_name": row["payer_name"],
            "payee_name": row["payee_name"],
            "property_or_unit": row["property_or_unit"],
            "confidence": row["confidence"],
            "risk_flags": "; ".join(row.get("risk_flags") or []),
            "whatsapp_draft": row.get("whatsapp_draft") or "",
            "source_filename": row["source_filename"],
        }
        for row in rows
    ]
    st.dataframe(display, use_container_width=True, hide_index=True)

    export_path = Path("data") / "slips_export.csv"
    path = export_csv(
        export_path,
        payment_type=None if filter_type == "all" else filter_type,
    )
    csv_bytes = path.read_bytes()
    st.download_button(
        label="Download CSV (from SQLite)",
        data=csv_bytes,
        file_name="slips_export.csv",
        mime="text/csv",
        use_container_width=True,
        type="primary",
    )
    st.caption(f"CSV also written to `{path}` ({len(rows)} row(s)).")
