from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


PO_KEYWORDS = ["PO Number", "Purchase Order", "PO No", "PO_ID"]
GRN_KEYWORDS = ["GRN Number", "Receipt No", "Goods Receipt", "GRN_ID"]
INV_KEYWORDS = ["Invoice Number", "Invoice No", "INV_ID", "Bill Number"]


ALIAS_MAP: Dict[str, List[str]] = {
    "po_number": ["po number", "purchase order", "po no", "po_id", "po#", "po num"],
    "vendor_name": ["vendor", "vendor name", "supplier", "supplier name"],
    "amount": [
        "amount",
        "line amount",
        "total amount",
        "value",
        "net amount",
        "gross amount",
    ],
    "doc_date": [
        "date",
        "po date",
        "grn date",
        "invoice date",
        "doc date",
        "document date",
    ],
    "item_description": ["description", "item description", "product", "item"],
    "quantity": [
        "quantity",
        "qty",
        "quantity ordered",
        "quantity received",
        "quantity invoiced",
    ],
    "unit_price": ["unit price", "price", "unit cost"],
    "line_item": ["line item", "line", "line_no", "line number"],
}


REQUIRED_COLUMNS = ["po_number", "vendor_name"]


@dataclass
class LoadedDocuments:
    df_po: pd.DataFrame
    df_grn: pd.DataFrame
    df_inv: pd.DataFrame
    manual_type_assignment_required: bool = False


class DataLoader:
    """
    Responsible for reading PO / GRN / Invoice spreadsheets and returning
    normalised DataFrames for downstream matching.
    """

    def __init__(self, alias_map: Optional[Dict[str, List[str]]] = None) -> None:
        self.alias_map = alias_map or ALIAS_MAP

    def load_files(
        self,
        file_paths: Iterable[Path],
        explicit_types: Optional[Dict[Path, str]] = None,
    ) -> LoadedDocuments:
        """
        Parameters
        ----------
        file_paths:
            Iterable of paths (Excel or CSV).
        explicit_types:
            Optional mapping of Path -> one of {"PO", "GRN", "INV"}.
            Used when auto-detection is ambiguous (UI can collect from user).
        """
        explicit_types = explicit_types or {}

        po_frames: List[pd.DataFrame] = []
        grn_frames: List[pd.DataFrame] = []
        inv_frames: List[pd.DataFrame] = []

        manual_required = False

        for path in file_paths:
            df = self._read_any(path)
            doc_type, ambiguous = self._detect_document_type(df, explicit_types.get(path))
            if ambiguous:
                manual_required = True

            df_norm = self._normalise_columns(df)
            df_clean = self._clean_dataframe(df_norm)
            self._validate_required(df_clean)

            if doc_type == "PO":
                po_frames.append(df_clean)
            elif doc_type == "GRN":
                grn_frames.append(df_clean)
            elif doc_type == "INV":
                inv_frames.append(df_clean)
            else:
                raise ValueError(f"Unsupported document type for file {path}: {doc_type}")

        df_po = pd.concat(po_frames, ignore_index=True) if po_frames else pd.DataFrame()
        df_grn = pd.concat(grn_frames, ignore_index=True) if grn_frames else pd.DataFrame()
        df_inv = pd.concat(inv_frames, ignore_index=True) if inv_frames else pd.DataFrame()

        return LoadedDocuments(
            df_po=df_po,
            df_grn=df_grn,
            df_inv=df_inv,
            manual_type_assignment_required=manual_required,
        )

    # ------------------------------------------------------------------
    # File reading and detection helpers
    # ------------------------------------------------------------------
    def _read_any(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(path)
        if suffix == ".csv":
            return pd.read_csv(path)
        raise ValueError(f"Unsupported file type: {suffix}")

    def _detect_document_type(
        self, df: pd.DataFrame, explicit_type: Optional[str] = None
    ) -> Tuple[str, bool]:
        if explicit_type:
            return explicit_type, False

        cols = [str(c).strip() for c in df.columns]
        po_hits = self._count_keyword_hits(cols, PO_KEYWORDS)
        grn_hits = self._count_keyword_hits(cols, GRN_KEYWORDS)
        inv_hits = self._count_keyword_hits(cols, INV_KEYWORDS)

        hits = {"PO": po_hits, "GRN": grn_hits, "INV": inv_hits}
        best_type = max(hits, key=hits.get)
        best_score = hits[best_type]

        scores = sorted(hits.values(), reverse=True)
        ambiguous = len(scores) > 1 and scores[0] == scores[1] and best_score > 0

        if best_score == 0:
            # Completely unknown; UI must ask.
            return "UNKNOWN", True

        return best_type, ambiguous

    @staticmethod
    def _count_keyword_hits(columns: List[str], keywords: List[str]) -> int:
        cols_lower = [c.lower() for c in columns]
        return sum(1 for kw in keywords for c in cols_lower if kw.lower() in c)

    # ------------------------------------------------------------------
    # Normalisation, validation, cleaning
    # ------------------------------------------------------------------
    def _normalise_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        mapping: Dict[str, str] = {}
        lower_cols = {str(c).lower(): c for c in df.columns}

        for canonical, aliases in self.alias_map.items():
            for alias in aliases:
                if alias in lower_cols:
                    mapping[lower_cols[alias]] = canonical

        df = df.rename(columns=mapping)
        return df

    def _validate_required(self, df: pd.DataFrame) -> None:
        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns after normalisation: {missing}")

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Strip whitespace from string columns
        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].astype(str).str.strip()

        # Normalise numeric fields
        for col in ["amount", "quantity", "unit_price"]:
            if col in df.columns:
                df[col] = (
                    pd.to_numeric(
                        df[col]
                        .replace(r"[,\s]", "", regex=True)
                        .replace("", np.nan),
                        errors="coerce",
                    )
                )

        # Parse dates
        if "doc_date" in df.columns:
            df["doc_date"] = pd.to_datetime(df["doc_date"], errors="coerce")

        return df

