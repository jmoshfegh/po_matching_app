from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import numpy as np
import pandas as pd
import streamlit as st

from core.matcher import ThreeWayMatcher, MatcherConfig
from core.discrepancy import ToleranceConfig


def _ensure_session_defaults() -> None:
    st.session_state.setdefault("match_params", [])
    st.session_state.setdefault("matched_df", None)
    st.session_state.setdefault("audit_trail", [])
    st.session_state.setdefault(
        "tolerance_config",
        {
            "amount_tolerance_pct": 2.0,
            "amount_tolerance_abs": 10.0,
            "quantity_tolerance_pct": 0.0,
            "use_stricter": True,
        },
    )


def _summary_metrics(df: pd.DataFrame) -> None:
    total = len(df)
    full = (df["match_status"] == "FULL MATCH").sum()
    partial = (df["match_status"] == "PARTIAL MATCH").sum()
    unmatched = (df["match_status"] == "UNMATCHED").sum()

    total_po_value = df["po_amount"].fillna(0).sum()
    total_invoiced = df["inv_amount"].fillna(0).sum()
    variance_amount = total_invoiced - total_po_value

    cols = st.columns(6)
    cols[0].metric("Total Records", total)
    cols[1].metric("Full Matches", full)
    cols[2].metric("Partial Matches", partial)
    cols[3].metric("Unmatched", unmatched)
    cols[4].metric("Total PO Value", f"${total_po_value:0.2f}")
    cols[5].metric("Total Invoiced", f"${total_invoiced:0.2f}", f"{variance_amount:0.2f}")


def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar.expander("Filters", expanded=True):
        status_options = st.multiselect(
            "Match Status",
            options=sorted(df["match_status"].dropna().unique().tolist()),
            default=sorted(df["match_status"].dropna().unique().tolist()),
        )

        vendors = sorted(df["vendor_name"].dropna().unique().tolist()) if "vendor_name" in df.columns else []
        vendor_filter = st.multiselect(
            "Vendor",
            options=vendors,
            default=vendors,
        )

        date_col = "doc_date" if "doc_date" in df.columns else None
        date_range: Optional[List[datetime]] = None
        if date_col:
            min_date = df[date_col].min()
            max_date = df[date_col].max()
            if pd.notna(min_date) and pd.notna(max_date):
                date_range = st.date_input(
                    "Document Date Range",
                    value=[min_date, max_date],
                )

        discrepancy_toggle = st.radio(
            "Discrepancy Flag",
            options=["All", "With Discrepancy", "Without Discrepancy"],
            index=0,
        )

        amount_min = float(df["po_amount"].fillna(0).min())
        amount_max = float(df["po_amount"].fillna(0).max())
        amount_range = st.slider(
            "PO Amount Range",
            min_value=amount_min,
            max_value=amount_max,
            value=(amount_min, amount_max),
        )

    filtered = df.copy()

    if status_options:
        filtered = filtered[filtered["match_status"].isin(status_options)]

    if vendor_filter and "vendor_name" in filtered.columns:
        filtered = filtered[filtered["vendor_name"].isin(vendor_filter)]

    if date_col and date_range and len(date_range) == 2:
        start, end = date_range
        filtered = filtered[
            (filtered[date_col] >= pd.to_datetime(start))
            & (filtered[date_col] <= pd.to_datetime(end))
        ]

    if discrepancy_toggle == "With Discrepancy":
        filtered = filtered[filtered["discrepancy_flag"].fillna(False)]
    elif discrepancy_toggle == "Without Discrepancy":
        filtered = filtered[~filtered["discrepancy_flag"].fillna(False)]

    filtered = filtered[
        (filtered["po_amount"].fillna(0) >= amount_range[0])
        & (filtered["po_amount"].fillna(0) <= amount_range[1])
    ]

    return filtered


def _row_color(row: pd.Series):
    color = row.get("status_color", "#ffffff")
    return [f"background-color: {color}"] * len(row)


def _recalculate_with_tolerance() -> None:
    """
    Re-run discrepancy and categorisation on the current matched_df
    using the tolerance values stored in session_state.
    """
    from core.discrepancy import DiscrepancyEngine
    from core.categorizer import Categorizer

    matched_df = st.session_state.get("matched_df")
    if matched_df is None or len(matched_df) == 0:
        return

    tol_cfg = ToleranceConfig(**st.session_state["tolerance_config"])
    engine = DiscrepancyEngine(tol_cfg)
    cat = Categorizer()

    df = engine.evaluate_dataframe(matched_df)
    df["discrepancy_flag"] = ~(
        df["amount_ok"].fillna(True) & df["quantity_ok"].fillna(True)
    )
    df = cat.categorize_dataframe(df)
    st.session_state["matched_df"] = df


def render() -> None:
    """
    Step 3: Run matching and provide interactive review/editing tools.
    """
    _ensure_session_defaults()

    st.header("Step 3 — Matching & Editing")

    df_po = st.session_state.get("df_po")
    df_grn = st.session_state.get("df_grn")
    df_inv = st.session_state.get("df_inv")
    match_params = st.session_state.get("match_params") or []

    if df_po is None or df_grn is None or df_inv is None:
        st.warning("Please complete **Step 1 — Upload Documents** first.")
        return

    if not match_params:
        st.warning("Please choose matching parameters in **Step 2 — Parameters** before proceeding.")
        return

    # Recalculate when tolerance sliders change
    _recalculate_with_tolerance()

    if st.session_state.get("matched_df") is None:
        st.info("Run matching using the button below.")
        if st.button("Run Matching", type="primary"):
            tol_cfg = ToleranceConfig(**st.session_state["tolerance_config"])
            matcher = ThreeWayMatcher(
                MatcherConfig(
                    fuzzy_threshold=st.session_state.get("fuzzy_threshold", 85),
                    tolerance=tol_cfg,
                )
            )
            matched = matcher.match(df_po, df_grn, df_inv, match_params=match_params)
            st.session_state["matched_df"] = matched
            st.success("Matching completed.")
        return

    df_matched: pd.DataFrame = st.session_state["matched_df"]

    _summary_metrics(df_matched)

    filtered = _apply_filters(df_matched)

    st.subheader("Matched Records")
    styled = filtered.style.apply(_row_color, axis=1)
    st.dataframe(styled, use_container_width=True)

    st.subheader("Edit Notes")
    edited = st.data_editor(
        filtered[["editable_notes"]].copy(),
        num_rows="fixed",
        use_container_width=True,
        key="notes_editor",
    )

    # Apply note edits back to main DataFrame
    if not edited.empty:
        df_matched.loc[edited.index, "editable_notes"] = edited["editable_notes"]
        st.session_state["matched_df"] = df_matched

    st.subheader("Row Details & Overrides")
    selected_index = st.number_input(
        "Enter row index to review/override:",
        min_value=int(filtered.index.min()) if not filtered.empty else 0,
        max_value=int(filtered.index.max()) if not filtered.empty else 0,
        step=1,
        value=int(filtered.index.min()) if not filtered.empty else 0,
    )

    if not filtered.empty and selected_index in filtered.index:
        row = filtered.loc[selected_index]
        st.json(row.to_dict())

        override_status = st.selectbox(
            "Override Match Status",
            options=["", "FULL MATCH", "PARTIAL MATCH", "UNMATCHED"],
            index=0,
        )
        override_reason = st.text_area(
            "Override Reason (required if overriding):",
            "",
        )
        if st.button("Save Override"):
            if override_status and not override_reason.strip():
                st.error("Please provide a reason for the override.")
            elif override_status:
                df_matched.loc[selected_index, "match_status"] = override_status
                st.session_state["matched_df"] = df_matched

                audit_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "row_index": int(selected_index),
                    "original_status": row.get("match_status"),
                    "new_status": override_status,
                    "reason": override_reason.strip(),
                }
                st.session_state["audit_trail"].append(audit_entry)
                st.success("Override saved and audit trail updated.")

    st.subheader("Bulk Actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Approve All Full Matches"):
            # No-op placeholder: in a real system this might write back to ERP.
            st.success("All full matches approved (logical action only).")

    with col2:
        if st.button("Flag Selected for Review"):
            df_matched.loc[filtered.index, "editable_notes"] = df_matched.loc[
                filtered.index, "editable_notes"
            ].fillna("") + " [FLAGGED FOR REVIEW]"
            st.session_state["matched_df"] = df_matched
            st.success("Selected rows flagged for review.")

    with col3:
        if st.button("Export Selected Rows"):
            st.session_state["export_selection"] = filtered.index.tolist()
            st.success("Selected rows marked for export. Use the Report page to download.")

