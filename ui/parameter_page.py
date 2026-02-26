from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from core.detector import ParameterDetector


CONF_COLOR = {
    "HIGH": "green",
    "MEDIUM": "orange",
    "LOW": "red",
}


def _ensure_session_defaults() -> None:
    st.session_state.setdefault("match_params", [])


def _build_badge(conf: str) -> str:
    color = CONF_COLOR.get(conf, "gray")
    return f"<span style='background-color:{color};color:white;padding:2px 6px;border-radius:4px;font-size:11px;'>{conf}</span>"


def render() -> None:
    """
    Step 2: Show detected parameters and allow selection.
    """
    _ensure_session_defaults()

    st.header("Step 2 — Confirm Matching Parameters")

    df_po = st.session_state.get("df_po")
    df_grn = st.session_state.get("df_grn")
    df_inv = st.session_state.get("df_inv")

    if df_po is None or df_grn is None or df_inv is None:
        st.warning("Please complete **Step 1 — Upload Documents** first.")
        return

    detector = ParameterDetector()
    suggestions = detector.detect(df_po, df_grn, df_inv)

    st.subheader("Detected Parameters")

    # Build table with confidence badges and sample values
    table_rows = []
    for s in suggestions:
        table_rows.append(
            {
                "Parameter": s["parameter"],
                "Confidence": s["confidence"],
                "Present In": ", ".join(s["present_in"]) or "—",
                "Sample Values": ", ".join(map(str, s["sample_values"])) or "—",
                "Confidence Badge": _build_badge(s["confidence"]),
            }
        )

    df_table = pd.DataFrame(table_rows)

    st.write(
        "Review the detected parameters below. High-confidence suggestions are good "
        "candidates for matching keys."
    )

    if not df_table.empty:
        st.write(
            df_table.style.hide(axis="index"),
            unsafe_allow_html=True,
        )
    else:
        st.info("No parameters could be detected. You may add custom parameters below.")

    all_params: List[str] = df_table["Parameter"].tolist() if not df_table.empty else []

    st.subheader("Choose Parameters for Matching")
    selected = st.multiselect(
        "Select one or more parameters to use as composite matching keys:",
        options=all_params,
        default=[p for p in all_params if p in ("po_number", "vendor_name")],
    )

    custom_param = st.text_input(
        "Add a custom column name (optional):",
        help="Use this if your data contains an additional column you want to match on.",
    )
    if custom_param:
        if custom_param not in selected:
            selected.append(custom_param)

    if not selected:
        st.warning("You must select at least one parameter to proceed.")

    proceed_disabled = len(selected) == 0

    col1, col2 = st.columns([1, 3])
    with col1:
        proceed = st.button(
            "Proceed to Matching",
            type="primary",
            disabled=proceed_disabled,
        )
    with col2:
        st.caption("The button will be enabled once you select at least one parameter.")

    if proceed and not proceed_disabled:
        st.session_state["match_params"] = selected
        st.success("Matching parameters saved. Continue to **Step 3 — Matching & Editing**.")

