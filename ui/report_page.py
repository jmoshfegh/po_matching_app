from __future__ import annotations

from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from core.exporter import Exporter


def render() -> None:
    """
    Step 4: Summary dashboard and export options.
    """
    st.header("Step 4 — Reports & Export")

    matched_df: pd.DataFrame | None = st.session_state.get("matched_df")
    audit_trail = st.session_state.get("audit_trail", [])

    if matched_df is None or matched_df.empty:
        st.warning("No matched data available. Complete **Step 3 — Matching** first.")
        return

    # KPI tiles
    total = len(matched_df)
    full = (matched_df["match_status"] == "FULL MATCH").sum()
    partial = (matched_df["match_status"] == "PARTIAL MATCH").sum()
    unmatched = (matched_df["match_status"] == "UNMATCHED").sum()

    total_po_value = matched_df["po_amount"].fillna(0).sum()
    total_invoiced = matched_df["inv_amount"].fillna(0).sum()
    variance_amount = total_invoiced - total_po_value
    over_billed_total = matched_df.loc[
        matched_df["match_subtype"] == "Over-billed", "amount_variance"
    ].fillna(0).sum()

    match_rate = (full / total * 100) if total else 0.0

    st.subheader("Key Metrics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Match Rate", f"{match_rate:0.1f}%")
    c2.metric("Total Variance", f"${variance_amount:0.2f}")
    c3.metric("Over-billed Total", f"${over_billed_total:0.2f}")
    c4.metric("Total Records", total)

    # Charts
    st.subheader("Visualisations")

    col1, col2 = st.columns(2)
    with col1:
        status_counts = (
            matched_df["match_status"]
            .value_counts()
            .rename_axis("match_status")
            .reset_index(name="count")
        )
        fig_pie = px.pie(
            status_counts,
            names="match_status",
            values="count",
            title="Match Status Distribution",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        if "vendor_name" in matched_df.columns:
            by_vendor = (
                matched_df.groupby("vendor_name")["amount_variance"]
                .sum()
                .reset_index()
            )
            fig_bar = px.bar(
                by_vendor,
                x="vendor_name",
                y="amount_variance",
                title="Variance by Vendor",
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No vendor information found to build variance-by-vendor chart.")

    # Export options
    st.subheader("Export Options")
    exporter = Exporter()

    # Build audit trail DataFrame
    audit_df = pd.DataFrame(audit_trail) if audit_trail else pd.DataFrame()

    excel_bytes = exporter.export_to_excel(matched_df, audit_trail=audit_df)
    csv_bytes = exporter.export_discrepancies_csv(matched_df)
    pdf_bytes = exporter.export_summary_pdf(matched_df)

    st.download_button(
        "Download Full Results (Excel)",
        data=excel_bytes,
        file_name="po_matching_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.download_button(
        "Download Discrepancies Only (CSV)",
        data=csv_bytes,
        file_name="po_discrepancies.csv",
        mime="text/csv",
    )

    st.download_button(
        "Download Summary Report (PDF)",
        data=pdf_bytes,
        file_name="po_matching_summary.pdf",
        mime="application/pdf",
    )

