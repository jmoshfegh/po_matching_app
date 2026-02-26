from __future__ import annotations

import streamlit as st

from core.discrepancy import ToleranceConfig
from data.generator import DatasetGenerator
from ui import upload_page, parameter_page, match_page, report_page


def _init_session_state() -> None:
    st.session_state.setdefault("step", 1)
    st.session_state.setdefault("df_po", None)
    st.session_state.setdefault("df_grn", None)
    st.session_state.setdefault("df_inv", None)
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
    st.session_state.setdefault("fuzzy_threshold", 85)


def _reset_all() -> None:
    keys = [
        "step",
        "df_po",
        "df_grn",
        "df_inv",
        "match_params",
        "matched_df",
        "audit_trail",
        "tolerance_config",
        "fuzzy_threshold",
        "export_selection",
    ]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]
    _init_session_state()


def _load_sample_data() -> None:
    """
    Generate synthetic data in-memory and push into session_state.
    """
    gen = DatasetGenerator()
    df_po, df_grn, df_inv = gen.generate()

    # Light normalisation: mimic loader behaviour on key columns
    from core.loader import DataLoader

    loader = DataLoader()
    df_po = loader._clean_dataframe(loader._normalise_columns(df_po))
    df_grn = loader._clean_dataframe(loader._normalise_columns(df_grn))
    df_inv = loader._clean_dataframe(loader._normalise_columns(df_inv))

    st.session_state["df_po"] = df_po
    st.session_state["df_grn"] = df_grn
    st.session_state["df_inv"] = df_inv


def main() -> None:
    st.set_page_config(
        page_title="PO Matching System",
        layout="wide",
        initial_sidebar_state="expanded",
        page_icon="📊",
    )

    _init_session_state()

    # Sidebar
    with st.sidebar:
        st.title("PO Matching System")
        st.markdown("Three-way PO / GRN / Invoice matching for Accounts Payable.")

        step = st.session_state.get("step", 1)
        st.markdown(f"**Current Step:** {step} / 4")

        st.subheader("Discrepancy Tolerances")
        tol_cfg = st.session_state["tolerance_config"]
        tol_cfg["amount_tolerance_pct"] = st.slider(
            "Amount tolerance (%)",
            min_value=0.0,
            max_value=10.0,
            value=float(tol_cfg["amount_tolerance_pct"]),
            step=0.1,
        )
        tol_cfg["amount_tolerance_abs"] = st.slider(
            "Amount tolerance (absolute)",
            min_value=0.0,
            max_value=100.0,
            value=float(tol_cfg["amount_tolerance_abs"]),
            step=1.0,
        )
        tol_cfg["quantity_tolerance_pct"] = st.slider(
            "Quantity tolerance (%)",
            min_value=0.0,
            max_value=20.0,
            value=float(tol_cfg["quantity_tolerance_pct"]),
            step=0.5,
        )
        tol_cfg["use_stricter"] = st.checkbox(
            "Use stricter of % vs absolute",
            value=bool(tol_cfg.get("use_stricter", True)),
        )
        st.session_state["tolerance_config"] = tol_cfg

        st.subheader("Fuzzy Matching")
        st.session_state["fuzzy_threshold"] = st.slider(
            "Fuzzy match threshold",
            min_value=70,
            max_value=100,
            value=int(st.session_state.get("fuzzy_threshold", 85)),
            step=1,
        )

        st.markdown("---")
        if st.button("Reset All"):
            _reset_all()
            st.rerun()

        if st.button("Load Sample Data"):
            _load_sample_data()
            st.session_state["step"] = max(st.session_state.get("step", 1), 2)
            st.success("Sample data loaded.")

    # Progress bar
    step = st.session_state.get("step", 1)
    st.progress(step / 4.0)

    # Navigation buttons
    col_prev, col_next = st.columns([1, 1])
    with col_prev:
        if st.button("◀ Previous", disabled=step <= 1):
            st.session_state["step"] = max(1, step - 1)
            st.rerun()
    with col_next:
        if st.button("Next ▶", disabled=step >= 4):
            st.session_state["step"] = min(4, step + 1)
            st.rerun()

    # Main content per step
    if step == 1:
        upload_page.render()
    elif step == 2:
        parameter_page.render()
    elif step == 3:
        match_page.render()
    elif step == 4:
        report_page.render()


if __name__ == "__main__":
    main()
