"""SlipsLedger — photo of a payment slip → Gemma 4 → SQLite ledger + CSV."""

from __future__ import annotations

import html
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

st.set_page_config(
    page_title="SlipsLedger · The Slip Ledger",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

STYLE_PATH = Path(__file__).resolve().parent / "assets" / "style.css"


def inject_broadsheet_css() -> None:
    css = STYLE_PATH.read_text(encoding="utf-8") if STYLE_PATH.exists() else ""
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)


def section_kicker(kicker: str, title: str) -> None:
    st.markdown(
        f"""
<div class="sl-section">
  <p class="sl-section-kicker">{kicker}</p>
  <h2 class="sl-section-title">{title}</h2>
  <div class="sl-rule-thin"></div>
</div>
""",
        unsafe_allow_html=True,
    )


inject_broadsheet_css()

st.markdown(
    """
<div class="sl-masthead">
  <p class="sl-kicker-brand">The Slip Ledger</p>
  <h1>SLIPSLEDGER</h1>
  <div class="sl-rule-thick"></div>
  <p class="sl-tagline">Scan · Extract · Ledger</p>
</div>

<div class="sl-lede-wrap">
  <h2>Photo of a payment slip, printed into a structured ledger.</h2>
  <p>
    Upload a rent, utility, security, cleaner, or estate-dues slip.
    <strong>Gemma&nbsp;4</strong> classifies and extracts the facts —
    risk flags, a WhatsApp confirmation, and a CSV-ready SQLite ledger.
  </p>
</div>
""",
    unsafe_allow_html=True,
)

if not os.getenv("GEMINI_API_KEY", "").strip():
    st.warning(
        "GEMINI_API_KEY is not set. Copy `.env.example` to `.env`, add your Gemini API key, "
        "and restart. Without Gemma there is no product."
    )

# ---------------------------------------------------------------------------
# Section A · Scan
# ---------------------------------------------------------------------------
section_kicker("Section A · Scan", "Upload the slip")

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
            width="stretch",
        )
    except Exception:
        st.info(f"Uploaded: {uploaded.name}")

    if st.button("Analyze with Gemma 4", type="primary", width="stretch"):
        with st.spinner(f"Calling {GEMMA_MODEL} (retries on temporary API errors)…"):
            try:
                result = analyze_slip(image_bytes, mime_type=mime)
            except Exception as exc:
                st.error(str(exc))
                st.info(
                    "Tip: Google sometimes returns INTERNAL 500 briefly. "
                    "Wait a few seconds and press Analyze again — the client retries automatically."
                )
            else:
                st.session_state["last_result"] = result
                st.session_state["last_filename"] = uploaded.name
                row_id = save_slip(result, source_filename=uploaded.name)
                st.session_state["last_saved_id"] = row_id

result = st.session_state.get("last_result")

# ---------------------------------------------------------------------------
# Section B · Dispatch
# ---------------------------------------------------------------------------
section_kicker("Section B · Dispatch", "Gemma report")

if not result:
    st.info(
        "Upload a slip in Section A and press **Analyze with Gemma 4** "
        "to print classification, fields, risk flags, and WhatsApp copy here."
    )
else:
    saved_id = st.session_state.get("last_saved_id")
    if saved_id is not None:
        st.success(f"Filed in the ledger as id **{saved_id}**.")

    st.markdown(
        '<p class="sl-section-kicker">Classification</p>',
        unsafe_allow_html=True,
    )
    pay_type = html.escape(str(result.get("payment_type") or ""))
    confidence = html.escape(str(result.get("confidence") if result.get("confidence") is not None else "—"))
    st.markdown(
        f"""
<div class="sl-panel">
  <div class="sl-field-row"><span class="label">Payment type</span><span class="value"><code>{pay_type}</code></span></div>
  <div class="sl-field-row"><span class="label">Confidence</span><span class="value">{confidence}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="sl-section-kicker">Extracted fields</p>',
        unsafe_allow_html=True,
    )
    fields = [
        ("Amount", f"{result.get('amount')} {result.get('currency') or ''}".strip()),
        ("Payment date", result.get("payment_date")),
        ("Payer", result.get("payer_name")),
        ("Payee", result.get("payee_name")),
        ("Unit / property", result.get("property_or_unit")),
        ("Period covered", result.get("period_covered")),
        ("Reference", result.get("reference_or_receipt_no")),
        ("Notes", result.get("notes")),
    ]
    rows_html = []
    for label, value in fields:
        display = html.escape(str(value)) if value not in (None, "") else "—"
        rows_html.append(
            f'<div class="sl-field-row"><span class="label">{html.escape(label)}</span>'
            f'<span class="value">{display}</span></div>'
        )
    st.markdown(
        f'<div class="sl-panel">{"".join(rows_html)}</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="sl-section-kicker">Risk flags</p>',
        unsafe_allow_html=True,
    )
    flags = result.get("risk_flags") or []
    if flags:
        for flag in flags:
            st.warning(flag)
    else:
        st.success("No risk flags on this slip.")

    st.markdown(
        '<p class="sl-section-kicker">WhatsApp message</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sl-copy-hint">Copy for WhatsApp · Ctrl+A then Ctrl+C</p>',
        unsafe_allow_html=True,
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

    if st.button("Save again to ledger", width="stretch"):
        row_id = save_slip(
            result,
            source_filename=st.session_state.get("last_filename"),
        )
        st.session_state["last_saved_id"] = row_id
        st.success(f"Saved again as id **{row_id}**.")

# ---------------------------------------------------------------------------
# Section C · Ledger
# ---------------------------------------------------------------------------
section_kicker("Section C · Ledger", "SQLite archive & CSV")
st.caption(f"Database file: `{Path('data') / 'slips.db'}`")

filter_type = st.selectbox(
    "Filter by payment type",
    options=["all", *PAYMENT_TYPES],
    key="ledger_filter",
)
rows = list_slips(payment_type=None if filter_type == "all" else filter_type)

if not rows:
    st.info("No slips in the ledger yet. Analyze a slip above — it auto-files here.")
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
    st.dataframe(display, width="stretch", hide_index=True)

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
        width="stretch",
        type="primary",
    )
    st.caption(f"CSV also written to `{path}` ({len(rows)} row(s)).")
