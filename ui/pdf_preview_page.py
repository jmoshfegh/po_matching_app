from __future__ import annotations

import streamlit as st

from core.pdf_extractor import PDFExtractionResult


class PDFPreviewPage:
    """
    Standalone page for detailed PDF inspection.
    Accessible from the upload page when a PDF has LOW confidence.
    """

    def render(self, pdf_file, extraction_result: PDFExtractionResult):

        st.title("📄 PDF Table Inspector")
        st.caption(
            f"File: **{extraction_result.filename}** | "
            f"{extraction_result.total_pages} pages | "
            f"{extraction_result.tables_found} tables found"
        )

        if extraction_result.tables_found == 0:
            st.error("No tables were detected in this PDF.")
            st.markdown(
                """
            **Possible reasons:**
            - The PDF contains scanned images (not text)
            - The PDF uses non-standard table formatting
            - The content is entirely text without tables

            **Solutions:**
            1. Use Adobe Acrobat to export as Excel
            2. Use Microsoft Word: Open PDF → Save As Excel
            3. Manually copy data into a spreadsheet template
            """
            )
            return

        tab_labels = [
            f"Table {t.table_index + 1} (p.{t.page_number})"
            for t in extraction_result.extracted_tables
        ]
        tabs = st.tabs(tab_labels)

        for tab, table in zip(tabs, extraction_result.extracted_tables):
            with tab:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Rows", table.row_count)
                m2.metric("Columns", table.col_count)
                m3.metric("Accuracy", f"{table.accuracy_score * 100:.1f}%")
                m4.metric("Confidence", table.confidence)

                st.markdown(
                    f"**Suggested Type:** `{table.suggested_doc_type}` | "
                    f"**Method:** `{table.extraction_method}`"
                )

                for w in table.warnings:
                    st.warning(w)

                st.markdown("**Full Extracted Table:**")
                edited_df = st.data_editor(
                    table.dataframe,
                    use_container_width=True,
                    num_rows="dynamic",
                    key=f"editor_table_{table.table_index}",
                )

                col_a, col_b = st.columns(2)
                with col_a:
                    doc_type_override = st.selectbox(
                        "Use this table as:",
                        ["PO", "GRN", "INV"],
                        index=["PO", "GRN", "INV"].index(
                            table.suggested_doc_type
                        )
                        if table.suggested_doc_type in ["PO", "GRN", "INV"]
                        else 0,
                        key=f"type_sel_{table.table_index}",
                    )
                with col_b:
                    if st.button(
                        f"✅ Use This Table as {doc_type_override}",
                        key=f"use_table_{table.table_index}",
                    ):
                        state_key = f"df_{doc_type_override.lower()}"
                        st.session_state[state_key] = edited_df
                        st.success(
                            f"Table set as {doc_type_override}! "
                            f"Return to upload page to continue."
                        )

