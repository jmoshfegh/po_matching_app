from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

import fitz  # PyMuPDF

try:
    import camelot  # type: ignore
except Exception:  # pragma: no cover - optional dependency issues handled at runtime
    camelot = None  # type: ignore

try:
    import tabula  # type: ignore
except Exception:  # pragma: no cover
    tabula = None  # type: ignore

try:
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None  # type: ignore


@dataclass
class ExtractedTable:
    table_index: int
    page_number: int
    dataframe: pd.DataFrame
    extraction_method: str  # "camelot_lattice" | "camelot_stream" | "tabula" | "pdfplumber"
    accuracy_score: float   # 0.0 to 1.0
    row_count: int
    col_count: int
    has_headers: bool
    suggested_doc_type: str  # "PO" | "GRN" | "INV" | "UNKNOWN"
    confidence: str          # "HIGH" | "MEDIUM" | "LOW"
    warnings: List[str]


@dataclass
class PDFExtractionResult:
    filename: str
    total_pages: int
    tables_found: int
    extracted_tables: List[ExtractedTable]
    best_table: Optional[ExtractedTable]
    extraction_method_used: str
    overall_confidence: str
    error_message: Optional[str]
    page_thumbnails: List[bytes]


class PDFExtractor:
    def __init__(self) -> None:
        self.doc_type_keywords = {
            "PO": [
                "purchase order",
                "po number",
                "po no",
                "po #",
                "po_id",
                "order number",
                "order date",
                "buyer",
                "ship to",
                "delivery date",
                "requisition",
            ],
            "GRN": [
                "goods receipt",
                "grn",
                "grn number",
                "receipt note",
                "received",
                "delivery note",
                "goods received",
                "receiving report",
                "grn_id",
                "receipt no",
            ],
            "INV": [
                "invoice",
                "invoice number",
                "invoice no",
                "inv #",
                "bill to",
                "bill number",
                "due date",
                "tax invoice",
                "inv_id",
                "remit to",
                "payment terms",
                "vat",
            ],
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract(self, file_path: str, password: Optional[str] = None) -> PDFExtractionResult:
        """
        Main entry point. Orchestrates full extraction pipeline and returns a PDFExtractionResult.
        """
        # 1. Validate file and open with fitz
        try:
            doc = fitz.open(file_path)
        except Exception as e:  # fitz specific errors are subclasses of Exception
            raise e

        total_pages = doc.page_count

        # 2. Generate thumbnails (max 10 pages)
        page_thumbnails: List[bytes] = []
        max_thumbs = min(total_pages, 10)
        for page_index in range(max_thumbs):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
            page_thumbnails.append(pix.tobytes("png"))

        doc.close()

        extracted_tables: List[ExtractedTable] = []
        extraction_method_used = ""
        error_message: Optional[str] = None

        # 3. Extraction pipeline: camelot lattice -> camelot stream -> tabula -> pdfplumber
        # 3a. Camelot lattice
        if camelot is not None:
            lattice_tables = self.camelot_lattice_extract(file_path)
            if lattice_tables:
                extracted_tables.extend(lattice_tables)
                extraction_method_used = "camelot_lattice"

        # Determine if we need to try stream mode
        def _best_accuracy(tables: List[ExtractedTable]) -> float:
            return max((t.accuracy_score for t in tables), default=0.0)

        if (not extracted_tables) or _best_accuracy(extracted_tables) < 0.8:
            if camelot is not None:
                stream_tables = self.camelot_stream_extract(file_path)
                if stream_tables:
                    extracted_tables.extend(stream_tables)
                    if not extraction_method_used:
                        extraction_method_used = "camelot_stream"

        # 3c. Tabula
        if (not extracted_tables) and tabula is not None:
            tabula_tables = self.tabula_extract(file_path)
            if tabula_tables:
                extracted_tables.extend(tabula_tables)
                extraction_method_used = "tabula"

        # 3d. pdfplumber
        if (not extracted_tables) and pdfplumber is not None:
            plumber_tables = self.pdfplumber_extract(file_path)
            if plumber_tables:
                extracted_tables.extend(plumber_tables)
                extraction_method_used = "pdfplumber"

        if not extracted_tables:
            error_message = "No tables could be extracted from the PDF."
            return PDFExtractionResult(
                filename=file_path,
                total_pages=total_pages,
                tables_found=0,
                extracted_tables=[],
                best_table=None,
                extraction_method_used=extraction_method_used or "none",
                overall_confidence="LOW",
                error_message=error_message,
                page_thumbnails=page_thumbnails,
            )

        # 4. Post-process each table
        processed_tables: List[ExtractedTable] = []
        for table in extracted_tables:
            df_clean = self.clean_dataframe(table.dataframe)
            df_headers, has_headers = self.detect_headers(df_clean)
            suggested_type = self.suggest_doc_type(df_headers)
            table.dataframe = df_headers
            table.has_headers = has_headers
            table.suggested_doc_type = suggested_type
            table.confidence = self.calculate_confidence(table)
            processed_tables.append(table)

        # 5. Merge multi-page tables
        merged_tables = self.merge_tables(processed_tables)

        # 6. Select best table
        best_table = self._select_best_table(merged_tables)

        # Overall confidence based on best table
        overall_confidence = best_table.confidence if best_table else "LOW"

        return PDFExtractionResult(
            filename=file_path,
            total_pages=total_pages,
            tables_found=len(merged_tables),
            extracted_tables=merged_tables,
            best_table=best_table,
            extraction_method_used=extraction_method_used or (best_table.extraction_method if best_table else "auto"),
            overall_confidence=overall_confidence,
            error_message=error_message,
            page_thumbnails=page_thumbnails,
        )

    # ------------------------------------------------------------------
    # Extraction backends
    # ------------------------------------------------------------------
    def camelot_lattice_extract(self, file_path: str) -> List[ExtractedTable]:
        if camelot is None:
            return []

        try:
            tables = camelot.read_pdf(
                file_path,
                flavor="lattice",
                pages="all",
                suppress_stdout=True,
            )
            extracted: List[ExtractedTable] = []
            for i, table in enumerate(tables):
                df = table.df.copy()
                warnings: List[str] = []
                try:
                    if getattr(table, "whitespace", 0) > 20:
                        warnings.append("High whitespace detected — table may be sparse")
                except Exception:
                    # Some versions of camelot may not expose whitespace; ignore
                    pass

                accuracy = getattr(table, "accuracy", 80.0)
                extracted.append(
                    ExtractedTable(
                        table_index=i,
                        page_number=getattr(table, "page", 1),
                        dataframe=df,
                        extraction_method="camelot_lattice",
                        accuracy_score=float(accuracy) / 100.0,
                        row_count=len(df),
                        col_count=len(df.columns),
                        has_headers=False,
                        suggested_doc_type="UNKNOWN",
                        confidence="",
                        warnings=warnings,
                    )
                )

            return extracted
        except Exception:
            return []

    def camelot_stream_extract(self, file_path: str) -> List[ExtractedTable]:
        if camelot is None:
            return []

        try:
            tables = camelot.read_pdf(
                file_path,
                flavor="stream",
                pages="all",
                suppress_stdout=True,
                edge_tol=500,
                row_tol=10,
            )
            extracted: List[ExtractedTable] = []
            for i, table in enumerate(tables):
                df = table.df.copy()
                accuracy = min(float(getattr(table, "accuracy", 75.0)) / 100.0, 0.75)
                extracted.append(
                    ExtractedTable(
                        table_index=i,
                        page_number=getattr(table, "page", 1),
                        dataframe=df,
                        extraction_method="camelot_stream",
                        accuracy_score=accuracy,
                        row_count=len(df),
                        col_count=len(df.columns),
                        has_headers=False,
                        suggested_doc_type="UNKNOWN",
                        confidence="",
                        warnings=[],
                    )
                )
            return extracted
        except Exception:
            return []

    def tabula_extract(self, file_path: str) -> List[ExtractedTable]:
        if tabula is None:
            return []

        try:
            dfs = tabula.read_pdf(
                file_path,
                pages="all",
                multiple_tables=True,
                guess=True,
                pandas_options={"header": None},
            )
            extracted: List[ExtractedTable] = []
            for i, df in enumerate(dfs):
                if df is None or df.empty or len(df.columns) < 2:
                    continue
                extracted.append(
                    ExtractedTable(
                        table_index=i,
                        page_number=i + 1,
                        dataframe=df,
                        extraction_method="tabula",
                        accuracy_score=0.65,
                        row_count=len(df),
                        col_count=len(df.columns),
                        has_headers=False,
                        suggested_doc_type="UNKNOWN",
                        confidence="",
                        warnings=[
                            "Extracted via tabula-py fallback — review column alignment carefully"
                        ],
                    )
                )
            return extracted
        except Exception:
            return []

    def pdfplumber_extract(self, file_path: str) -> List[ExtractedTable]:
        if pdfplumber is None:
            return []

        try:
            extracted: List[ExtractedTable] = []
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    table = page.extract_table()
                    if table is None or len(table) < 2:
                        continue

                    headers = table[0]
                    rows = table[1:]
                    headers = [
                        f"Column_{i}" if h is None else str(h) for i, h in enumerate(headers)
                    ]

                    df = pd.DataFrame(rows, columns=headers)

                    extracted.append(
                        ExtractedTable(
                            table_index=0,
                            page_number=page_num,
                            dataframe=df,
                            extraction_method="pdfplumber",
                            accuracy_score=0.55,
                            row_count=len(df),
                            col_count=len(df.columns),
                            has_headers=True,
                            suggested_doc_type="UNKNOWN",
                            confidence="",
                            warnings=[
                                "Extracted via pdfplumber — manual column review strongly recommended"
                            ],
                        )
                    )
            return extracted
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Cleaning and analysis helpers
    # ------------------------------------------------------------------
    def clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        # 1. Drop completely empty rows and columns
        df = df.copy()
        df.dropna(how="all", inplace=True)
        df.dropna(axis=1, how="all", inplace=True)

        if df.empty:
            return df.reset_index(drop=True)

        # 2. Strip whitespace from all string cells
        df = df.apply(
            lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x)
        )

        # 3. Replace empty strings with NaN
        df.replace("", np.nan, inplace=True)

        # 4. Remove rows where >80% of cells are NaN
        threshold = len(df.columns) * 0.8
        df = df.dropna(thresh=int(threshold))

        # 5. Reset index
        df.reset_index(drop=True, inplace=True)

        # 6. Normalise numeric columns (best-effort)
        for col in df.columns:
            series = df[col]
            try:
                cleaned = series.astype(str).str.replace(r"[$£€¥,]", "", regex=True)
                numeric = pd.to_numeric(cleaned, errors="coerce")
                if numeric.notna().sum() > 0:
                    df[col] = numeric
            except Exception:
                continue

        # 7. Normalise date-like columns
        date_keywords = ["date", "dt"]
        date_formats = [
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y-%m-%d",
            "%d-%b-%Y",
            "%B %d, %Y",
        ]

        for col in df.columns:
            col_lower = str(col).lower()
            if any(kw in col_lower for kw in date_keywords):
                for fmt in date_formats:
                    try:
                        parsed = pd.to_datetime(df[col], format=fmt, errors="coerce")
                        if parsed.notna().sum() > 0:
                            df[col] = parsed
                            break
                    except Exception:
                        continue

        return df

    def detect_headers(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
        if df.empty:
            return df, False

        first_row = df.iloc[0]
        non_numeric_fraction = sum(
            not str(v).replace(".", "").replace("-", "").isdigit() for v in first_row
        ) / len(df.columns)

        has_headers = False
        if non_numeric_fraction > 0.7:
            has_headers = True
            df = df.copy()
            df.columns = df.iloc[0].astype(str).str.strip()
            df = df.iloc[1:].reset_index(drop=True)

        # Clean column names
        clean_cols = []
        for c in df.columns:
            s = str(c).strip().lower().replace(" ", "_")
            # remove special chars except underscore and #
            s = "".join(ch for ch in s if ch.isalnum() or ch in {"_", "#"})
            clean_cols.append(s)
        df.columns = clean_cols

        return df, has_headers

    def suggest_doc_type(self, df: pd.DataFrame) -> str:
        # 1. Combine headers + first 5 rows
        headers_text = " ".join(df.columns.astype(str))
        body_text = df.head(5).to_string()
        search_text = f"{headers_text} {body_text}".lower()

        scores = {"PO": 0, "GRN": 0, "INV": 0}
        for doc_type, keywords in self.doc_type_keywords.items():
            for kw in keywords:
                if kw in search_text:
                    scores[doc_type] += 1

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        if best_score == 0:
            return "UNKNOWN"

        return best_type

    def calculate_confidence(self, table: ExtractedTable) -> str:
        score = table.accuracy_score
        confidence: str

        if score >= 0.90 and table.suggested_doc_type != "UNKNOWN":
            confidence = "HIGH"
        elif score >= 0.75 or table.suggested_doc_type != "UNKNOWN":
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        # Penalties
        if table.row_count < 3:
            confidence = self._lower_confidence(confidence)
        if table.col_count < 3:
            confidence = self._lower_confidence(confidence)
        if table.extraction_method == "pdfplumber" and confidence == "HIGH":
            confidence = "MEDIUM"

        return confidence

    @staticmethod
    def _lower_confidence(conf: str) -> str:
        if conf == "HIGH":
            return "MEDIUM"
        if conf == "MEDIUM":
            return "LOW"
        return conf

    def merge_tables(self, tables: List[ExtractedTable]) -> List[ExtractedTable]:
        if not tables:
            return []

        merged: List[ExtractedTable] = []
        current_group: List[ExtractedTable] = [tables[0]]

        def compatible(a: ExtractedTable, b: ExtractedTable) -> bool:
            if a.col_count != b.col_count:
                return False
            if list(a.dataframe.columns) == list(b.dataframe.columns):
                return True
            # If first row of b matches headers of a, treat as same table with duplicated header
            try:
                first_row = list(b.dataframe.iloc[0])
                header_row = list(a.dataframe.columns)
                return all(str(x).strip().lower() == str(y).strip().lower() for x, y in zip(first_row, header_row))
            except Exception:
                return False

        for prev, curr in zip(tables, tables[1:]):
            if compatible(prev, curr):
                current_group.append(curr)
            else:
                merged.append(self._merge_group(current_group))
                current_group = [curr]

        if current_group:
            merged.append(self._merge_group(current_group))

        return merged

    def _merge_group(self, group: List[ExtractedTable]) -> ExtractedTable:
        if len(group) == 1:
            return group[0]

        base = group[0]
        dfs = [base.dataframe]
        for t in group[1:]:
            df = t.dataframe
            # drop header-like first row if it matches columns
            if not df.empty:
                first_row = list(df.iloc[0])
                if all(
                    str(first_row[i]).strip().lower()
                    == str(base.dataframe.columns[i]).strip().lower()
                    for i in range(min(len(first_row), len(base.dataframe.columns)))
                ):
                    df = df.iloc[1:]
            dfs.append(df)

        merged_df = pd.concat(dfs, ignore_index=True)

        return ExtractedTable(
            table_index=base.table_index,
            page_number=base.page_number,
            dataframe=merged_df,
            extraction_method=base.extraction_method,
            accuracy_score=base.accuracy_score,
            row_count=len(merged_df),
            col_count=len(merged_df.columns),
            has_headers=base.has_headers,
            suggested_doc_type=base.suggested_doc_type,
            confidence=base.confidence,
            warnings=base.warnings,
        )

    def _select_best_table(self, tables: List[ExtractedTable]) -> Optional[ExtractedTable]:
        if not tables:
            return None

        def score_table(t: ExtractedTable) -> float:
            return (
                t.accuracy_score * 0.5
                + t.row_count * 0.01
                + t.col_count * 0.05
                + (0.3 if t.suggested_doc_type != "UNKNOWN" else 0.0)
            )

        return max(tables, key=score_table)

    # ------------------------------------------------------------------
    # Convenience for DataLoader integration
    # ------------------------------------------------------------------
    def pdf_to_dataframe(
        self, file_path: str
    ) -> Tuple[pd.DataFrame, str, float, List[str]]:
        """
        Convenience method to get a single best DataFrame and metadata.
        """
        result = self.extract(file_path)
        if result.best_table is None:
            raise ValueError(
                "No suitable table could be extracted from the PDF for downstream processing."
            )

        table = result.best_table
        return (
            table.dataframe,
            table.extraction_method,
            table.accuracy_score,
            table.warnings,
        )

