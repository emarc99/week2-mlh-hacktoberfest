"""SQLite ledger for extracted payment slips."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "slips.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS slips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                payment_type TEXT NOT NULL,
                amount REAL,
                currency TEXT,
                payment_date TEXT,
                payer_name TEXT,
                payee_name TEXT,
                property_or_unit TEXT,
                period_covered TEXT,
                reference_or_receipt_no TEXT,
                notes TEXT,
                confidence REAL,
                risk_flags TEXT,
                whatsapp_draft TEXT,
                source_filename TEXT
            )
            """
        )
        conn.commit()


def save_slip(result: dict[str, Any], source_filename: str | None = None) -> int:
    init_db()
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO slips (
                created_at, payment_type, amount, currency, payment_date,
                payer_name, payee_name, property_or_unit, period_covered,
                reference_or_receipt_no, notes, confidence, risk_flags,
                whatsapp_draft, source_filename
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                result.get("payment_type"),
                result.get("amount"),
                result.get("currency"),
                result.get("payment_date"),
                result.get("payer_name"),
                result.get("payee_name"),
                result.get("property_or_unit"),
                result.get("period_covered"),
                result.get("reference_or_receipt_no"),
                result.get("notes"),
                result.get("confidence"),
                json.dumps(result.get("risk_flags") or []),
                result.get("whatsapp_draft"),
                source_filename,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_slips(payment_type: str | None = None) -> list[dict[str, Any]]:
    init_db()
    query = "SELECT * FROM slips"
    params: tuple[Any, ...] = ()
    if payment_type and payment_type != "all":
        query += " WHERE payment_type = ?"
        params = (payment_type,)
    query += " ORDER BY id DESC"

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            item["risk_flags"] = json.loads(item.get("risk_flags") or "[]")
        except json.JSONDecodeError:
            item["risk_flags"] = []
        out.append(item)
    return out


def export_csv(path: Path | str, payment_type: str | None = None) -> Path:
    path = Path(path)
    rows = list_slips(payment_type=payment_type)
    fieldnames = [
        "id",
        "created_at",
        "payment_type",
        "amount",
        "currency",
        "payment_date",
        "payer_name",
        "payee_name",
        "property_or_unit",
        "period_covered",
        "reference_or_receipt_no",
        "notes",
        "confidence",
        "risk_flags",
        "whatsapp_draft",
        "source_filename",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            export_row = dict(row)
            flags = export_row.get("risk_flags") or []
            export_row["risk_flags"] = (
                "; ".join(flags) if isinstance(flags, list) else str(flags)
            )
            writer.writerow(export_row)
    return path
