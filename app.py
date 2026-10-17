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

tab_upload, tab_ledger = st.tabs(["Scan slip", "Ledger"])

with tab_upload:
    st.subheader("Upload payment slip")
    uploaded = st.file_uploader(
        "Image of handwritten or printed slip",
        type=["png", "jpg", "jpeg", "webp"],
    )

    if uploaded is not None:
        image_bytes = uploaded.getvalue()
        mime = uploaded.type or "image/jpeg"
        col_img, col_out = st.columns([1, 1])
        with col_img:
            try:
                st.image(Image.open(io.BytesIO(image_bytes)), caption=uploaded.name)
            except Exception:
                st.info(f"Uploaded: {uploaded.name}")

        if st.button("Analyze with Gemma 4", type="primary"):
            with st.spinner(f"Calling {GEMMA_MODEL}…"):
                try:
                    result = analyze_slip(image_bytes, mime_type=mime)
                    st.session_state["last_result"] = result
                    st.session_state["last_filename"] = uploaded.name
                except Exception as exc:
                    st.error(str(exc))
                    st.stop()

        result = st.session_state.get("last_result")
        if result:
            with col_out:
                st.markdown(f"**Payment type:** `{result['payment_type']}`")
                st.markdown(
                    f"**Amount:** {result.get('amount')} {result.get('currency') or ''}"
                )
                st.markdown(f"**Date:** {result.get('payment_date')}")
                st.markdown(f"**Payer:** {result.get('payer_name')}")
                st.markdown(f"**Payee:** {result.get('payee_name')}")
                st.markdown(f"**Unit / property:** {result.get('property_or_unit')}")
                st.markdown(f"**Period:** {result.get('period_covered')}")
                st.markdown(f"**Reference:** {result.get('reference_or_receipt_no')}")
                st.markdown(f"**Confidence:** {result.get('confidence')}")
                flags = result.get("risk_flags") or []
                if flags:
                    st.warning("Risk flags: " + "; ".join(flags))
                else:
                    st.success("No risk flags")
                st.text_area("WhatsApp draft", result.get("whatsapp_draft") or "", height=140)
                with st.expander("All fields"):
                    st.json(
                        {
                            k: v
                            for k, v in result.items()
                            if k != "raw_model_text"
                        }
                    )

            if st.button("Save to ledger"):
                row_id = save_slip(
                    result,
                    source_filename=st.session_state.get("last_filename"),
                )
                st.success(f"Saved slip #{row_id} to SQLite ledger.")

with tab_ledger:
    st.subheader("Payment ledger")
    filter_type = st.selectbox(
        "Filter by payment type",
        options=["all", *PAYMENT_TYPES],
    )
    rows = list_slips(payment_type=None if filter_type == "all" else filter_type)

    if not rows:
        st.info("No slips saved yet. Scan a slip and save it.")
    else:
        display = []
        for row in rows:
            display.append(
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
                    "source_filename": row["source_filename"],
                }
            )
        st.dataframe(display, use_container_width=True)

        export_path = Path("data") / "slips_export.csv"
        if st.button("Export CSV"):
            path = export_csv(
                export_path,
                payment_type=None if filter_type == "all" else filter_type,
            )
            csv_bytes = path.read_bytes()
            st.download_button(
                "Download CSV",
                data=csv_bytes,
                file_name="slips_export.csv",
                mime="text/csv",
            )
            st.caption(f"Also written to `{path}`.")
