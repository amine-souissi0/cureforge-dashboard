"""
Streamlit dashboard — Investor Outreach Status Board.

Run with:
    streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.database import OutreachRecord, SessionLocal, engine, init_db

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LongevityInTime — Investor Outreach",
    page_icon="🧬",
    layout="wide",
)

init_db()

STATUS_COLORS = {
    "pending": "#808080",
    "interested": "#22c55e",
    "not_interested": "#ef4444",
    "needs_info": "#f59e0b",
    "other": "#6366f1",
}

STATUS_EMOJI = {
    "pending": "⏳",
    "interested": "✅",
    "not_interested": "❌",
    "needs_info": "❓",
    "other": "💬",
}


@st.cache_data(ttl=30)
def load_records() -> pd.DataFrame:
    db = SessionLocal()
    try:
        rows = db.query(OutreachRecord).all()
        data = [
            {
                "ID": r.id,
                "Name": r.name,
                "Email": r.email,
                "Firm": r.firm or "",
                "Focus Area": r.focus_area or "",
                "Sent At": r.sent_at,
                "Reply Status": r.reply_status.value if r.reply_status else "pending",
                "Reply Received": r.reply_received_at,
                "Message ID": r.message_id or "",
            }
            for r in rows
        ]
        return pd.DataFrame(data)
    finally:
        db.close()


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🧬 LongevityInTime — Investor Outreach Dashboard")
st.caption("Real-time status board for investor email campaigns.")

if st.button("🔄 Refresh"):
    st.cache_data.clear()

df = load_records()

# ── Top-level Metrics ────────────────────────────────────────────────────────
if df.empty:
    st.info("No outreach records found. Run `scripts/run_outreach.py` to get started.")
    st.stop()

total = len(df)
sent = df["Sent At"].notna().sum()
replied = df["Reply Received"].notna().sum()
interested = (df["Reply Status"] == "interested").sum()
not_interested = (df["Reply Status"] == "not_interested").sum()
needs_info = (df["Reply Status"] == "needs_info").sum()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Investors", total)
col2.metric("Emails Sent", int(sent))
col3.metric("Replies Received", int(replied), f"{replied/sent*100:.0f}%" if sent else "—")
col4.metric("Interested", int(interested), f"{interested/replied*100:.0f}%" if replied else "—")
col5.metric("Needs Info", int(needs_info))

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
with st.expander("Filters", expanded=True):
    f_col1, f_col2, f_col3 = st.columns(3)

    all_statuses = sorted(df["Reply Status"].unique().tolist())
    selected_statuses = f_col1.multiselect(
        "Reply Status",
        options=all_statuses,
        default=all_statuses,
    )

    all_firms = sorted(df["Firm"].unique().tolist())
    selected_firms = f_col2.multiselect(
        "Firm",
        options=all_firms,
        default=all_firms,
    )

    search = f_col3.text_input("Search name / email", "")

filtered = df[
    df["Reply Status"].isin(selected_statuses)
    & df["Firm"].isin(selected_firms)
]
if search:
    mask = (
        filtered["Name"].str.contains(search, case=False, na=False)
        | filtered["Email"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

# ── Table ─────────────────────────────────────────────────────────────────────
st.subheader(f"Outreach Records ({len(filtered)} shown)")


def _color_status(val: str) -> str:
    color = STATUS_COLORS.get(val, "#808080")
    return f"color: {color}; font-weight: bold;"


display_cols = ["Name", "Email", "Firm", "Focus Area", "Sent At", "Reply Status", "Reply Received"]
styled = (
    filtered[display_cols]
    .style.map(_color_status, subset=["Reply Status"])
    .format(
        {
            "Sent At": lambda x: x.strftime("%Y-%m-%d %H:%M") if pd.notna(x) else "—",
            "Reply Received": lambda x: x.strftime("%Y-%m-%d %H:%M") if pd.notna(x) else "—",
        }
    )
)
st.dataframe(styled, use_container_width=True, hide_index=True)

# ── Status Breakdown Bar ──────────────────────────────────────────────────────
st.subheader("Status Breakdown")
status_counts = filtered["Reply Status"].value_counts().reset_index()
status_counts.columns = ["Status", "Count"]
st.bar_chart(status_counts.set_index("Status"))
