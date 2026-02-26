from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List

import streamlit as st

from core.loader import DataLoader


DOC_TYPES = ["Auto-detect", "PO", "GRN", "INV"]


def _ensure_session_defaults() -> None:
    st.session_state.setdefault("df_po", None)
    st.session_state.setdefault("df_grn", None)
    st.session_state.setdefault("df_inv", None)


def render() -> None:
    """
    Step 1: Upload spreadsheets and ingest via DataLoader.
    """
    _ensure_session_defaults()

    st.header("Step 1 — Upload Documents")
    st.markdown(
        "Upload your **Purchase Orders (PO)**, **Goods Receipt Notes (GRN)**, "
        "and **Invoices (INV)** as Excel or CSV files."
    )

    uploaded_files = st.file_uploader(
        "Upload one or more files",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Upload at least one PO, GRN, or Invoice file to continue.")
        return

    st.subheader("Document Type Confirmation")
    st.caption(
        "The app will attempt to auto-detect document types, but you can override "
        "them below if necessary."
    )

    # Let user optionally specify explicit types; we will still auto-detect
    # via DataLoader and rely on its ambiguity flag for UI guidance.
    explicit_type_labels: Dict[str, str] = {}
    for f in uploaded_files:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text(f.name)
        with col2:
            choice = st.selectbox(
                "Type",
                DOC_TYPES,
                key=f"doctype_{f.name}",
            )
            if choice != "Auto-detect":
                explicit_type_labels[f.name] = choice

    if st.button("Load Documents"):
        loader = DataLoader()
        temp_paths: List[Path] = []
        explicit_types: Dict[Path, str] = {}

        for f in uploaded_files:
            suffix = Path(f.name).suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(f.getbuffer())
                tmp_path = Path(tmp.name)
                temp_paths.append(tmp_path)
                if f.name in explicit_type_labels:
                    explicit_types[tmp_path] = explicit_type_labels[f.name]

        loaded = loader.load_files(temp_paths, explicit_types=explicit_types or None)

        st.session_state["df_po"] = loaded.df_po
        st.session_state["df_grn"] = loaded.df_grn
        st.session_state["df_inv"] = loaded.df_inv

        if loaded.manual_type_assignment_required and not explicit_type_labels:
            st.warning(
                "Some files could not be confidently classified. "
                "Consider specifying document types explicitly from the dropdowns above."
            )
        else:
            st.success("Documents loaded successfully. You can proceed to parameter selection.")

