from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from fpdf import FPDF


DataFrameLike = pd.DataFrame
BufferOrPath = Union[str, BytesIO]


@dataclass
class ExportResult:
    excel_bytes: Optional[bytes] = None
    pdf_bytes: Optional[bytes] = None
    csv_bytes: Optional[bytes] = None


class Exporter:
    """
    Handles exporting matched results and summaries to Excel, CSV and PDF.
    """

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Excel export
    # ------------------------------------------------------------------
    def export_to_excel(
        self,
        matched_df: DataFrameLike,
        audit_trail: Optional[DataFrameLike] = None,
        output: Optional[BufferOrPath] = None,
    ) -> bytes:
        """
        Export to a multi-sheet Excel workbook with:
        1. All Matches
        2. Full Matches
        3. Partial Matches
        4. Unmatched
        5. Audit Trail
        """
        buf = output if isinstance(output, BytesIO) else BytesIO()

        full = matched_df.copy()

        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            full.to_excel(writer, sheet_name="All Matches", index=False)

            full_matches = full[full["match_status"] == "FULL MATCH"]
            partial_matches = full[full["match_status"] == "PARTIAL MATCH"]
            unmatched = full[full["match_status"] == "UNMATCHED"]

            full_matches.to_excel(writer, sheet_name="Full Matches", index=False)
            partial_matches.to_excel(writer, sheet_name="Partial Matches", index=False)
            unmatched.to_excel(writer, sheet_name="Unmatched", index=False)

            if audit_trail is not None:
                audit_trail.to_excel(writer, sheet_name="Audit Trail", index=False)
            else:
                # Still create an empty sheet to keep structure consistent
                pd.DataFrame().to_excel(writer, sheet_name="Audit Trail", index=False)

        if isinstance(output, str):
            # Caller provided a file path; write bytes there.
            with open(output, "wb") as f:  # pragma: no cover - simple IO
                f.write(buf.getvalue())
        return buf.getvalue()

    # ------------------------------------------------------------------
    # CSV export (discrepancies only)
    # ------------------------------------------------------------------
    def export_discrepancies_csv(
        self,
        matched_df: DataFrameLike,
        output: Optional[BufferOrPath] = None,
    ) -> bytes:
        discrepancies = matched_df[matched_df["discrepancy_flag"].fillna(False)].copy()

        buf = output if isinstance(output, BytesIO) else BytesIO()
        discrepancies.to_csv(buf, index=False)

        if isinstance(output, str):
            with open(output, "wb") as f:  # pragma: no cover - simple IO
                f.write(buf.getvalue())
        return buf.getvalue()

    # ------------------------------------------------------------------
    # PDF summary export
    # ------------------------------------------------------------------
    def export_summary_pdf(
        self,
        matched_df: DataFrameLike,
        output: Optional[BufferOrPath] = None,
    ) -> bytes:
        """
        Build a compact summary PDF report with high-level KPIs.
        Uses fpdf2 for simplicity.
        """
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "PO Matching Summary Report", ln=True)

        pdf.set_font("Helvetica", "", 10)

        # KPIs
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

        pdf.ln(4)
        pdf.cell(0, 8, f"Total records: {total}", ln=True)
        pdf.cell(0, 8, f"Full matches: {full}", ln=True)
        pdf.cell(0, 8, f"Partial matches: {partial}", ln=True)
        pdf.cell(0, 8, f"Unmatched: {unmatched}", ln=True)

        pdf.ln(4)
        pdf.cell(0, 8, f"Total PO value: ${total_po_value:0.2f}", ln=True)
        pdf.cell(0, 8, f"Total invoiced: ${total_invoiced:0.2f}", ln=True)
        pdf.cell(0, 8, f"Variance amount: ${variance_amount:0.2f}", ln=True)
        pdf.cell(0, 8, f"Over-billed total: ${over_billed_total:0.2f}", ln=True)

        pdf.ln(4)
        pdf.cell(0, 8, f"Match rate: {match_rate:0.1f}%", ln=True)

        buf = output if isinstance(output, BytesIO) else BytesIO()
        pdf.output(buf)  # type: ignore[arg-type]

        if isinstance(output, str):
            with open(output, "wb") as f:  # pragma: no cover - simple IO
                f.write(buf.getvalue())
        return buf.getvalue()

