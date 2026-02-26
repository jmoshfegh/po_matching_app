from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from core.categorizer import Categorizer
from core.discrepancy import DiscrepancyEngine, ToleranceConfig


@dataclass
class MatcherConfig:
    fuzzy_threshold: int = 85
    tolerance: ToleranceConfig = field(default_factory=ToleranceConfig)


class ThreeWayMatcher:
    """
    Performs three-way matching between PO, GRN, and Invoice DataFrames.
    """

    def __init__(
        self,
        config: MatcherConfig | None = None,
        discrepancy_engine: DiscrepancyEngine | None = None,
        categorizer: Categorizer | None = None,
    ) -> None:
        self.config = config or MatcherConfig()
        self.discrepancy_engine = discrepancy_engine or DiscrepancyEngine(
            self.config.tolerance
        )
        self.categorizer = categorizer or Categorizer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def match(
        self,
        df_po: pd.DataFrame,
        df_grn: pd.DataFrame,
        df_inv: pd.DataFrame,
        match_params: Sequence[str],
    ) -> pd.DataFrame:
        """
        Performs PO ⟕ GRN ⟕ INV using match_params as composite keys.
        Supports fuzzy matching on string keys (notably po_number).
        """
        if not match_params:
            raise ValueError("match_params must contain at least one parameter")

        df_po = df_po.copy()
        df_grn = df_grn.copy()
        df_inv = df_inv.copy()

        # Prepare amount/quantity fields
        self._prepare_measure_columns(df_po, "po")
        self._prepare_measure_columns(df_grn, "grn")
        self._prepare_measure_columns(df_inv, "inv")

        # Apply fuzzy normalisation of string keys (especially po_number)
        df_po, df_inv, fuzzy_flags = self._apply_fuzzy_keys(df_po, df_inv, match_params)

        # Exact left joins on keys
        keys = list(match_params)
        po_grn = pd.merge(
            df_po,
            self._prepare_other(df_grn, "grn", keys),
            on=keys,
            how="left",
        )
        full = pd.merge(
            po_grn,
            self._prepare_other(df_inv, "inv", keys),
            on=keys,
            how="left",
        )

        # Presence flags
        full["has_po"] = True
        full["has_grn"] = self._detect_presence(full, prefix="grn_")
        full["has_invoice"] = self._detect_presence(full, prefix="inv_")

        # Attach fuzzy confidence (EXACT / FUZZY) based on invoice key mapping
        full["match_confidence"] = "EXACT"
        if fuzzy_flags is not None and "inv_po_number_fuzzy" in full.columns:
            mask = full["inv_po_number_fuzzy"].fillna(False)
            full.loc[mask, "match_confidence"] = "FUZZY"

        # Orphan GRNs / INVs (no PO key)
        orphans = self._build_orphans(df_po, df_grn, df_inv, keys)
        if not orphans.empty:
            full = pd.concat([full, orphans], ignore_index=True, sort=False)

        # Standard output columns for quantities / amounts
        full["po_quantity"] = full.get("po_quantity")
        full["grn_quantity"] = full.get("grn_quantity")
        full["inv_quantity"] = full.get("inv_quantity")

        full["po_amount"] = full.get("po_amount")
        full["grn_amount"] = full.get("grn_amount")
        full["inv_amount"] = full.get("inv_amount")

        # Variances (PO vs INV primarily)
        full["quantity_variance"] = (
            full["inv_quantity"].fillna(0) - full["po_quantity"].fillna(0)
        )
        full["amount_variance"] = (
            full["inv_amount"].fillna(0.0) - full["po_amount"].fillna(0.0)
        )

        # Discrepancy evaluation
        full = self.discrepancy_engine.evaluate_dataframe(full)
        full["discrepancy_flag"] = ~(
            full["amount_ok"].fillna(True) & full["quantity_ok"].fillna(True)
        )

        # Categorisation
        full = self.categorizer.categorize_dataframe(full)

        # Editable notes column
        if "editable_notes" not in full.columns:
            full["editable_notes"] = ""

        return full

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _prepare_measure_columns(df: pd.DataFrame, prefix: str) -> None:
        if "quantity" in df.columns and f"{prefix}_quantity" not in df.columns:
            df[f"{prefix}_quantity"] = df["quantity"]
        if "amount" in df.columns and f"{prefix}_amount" not in df.columns:
            df[f"{prefix}_amount"] = df["amount"]

    @staticmethod
    def _prepare_other(
        df: pd.DataFrame, prefix: str, keys: Iterable[str]
    ) -> pd.DataFrame:
        df = df.copy()
        rename_map: Dict[str, str] = {}
        for col in df.columns:
            if col in keys:
                continue
            if col.startswith(f"{prefix}_"):
                # Already prefixed
                continue
            if col in {"quantity", "amount"}:
                # Already handled by _prepare_measure_columns
                continue
            rename_map[col] = f"{prefix}_{col}"
        if rename_map:
            df = df.rename(columns=rename_map)
        return df

    @staticmethod
    def _detect_presence(df: pd.DataFrame, prefix: str) -> pd.Series:
        cols = [c for c in df.columns if c.startswith(prefix)]
        if not cols:
            return pd.Series(False, index=df.index)
        return df[cols].notna().any(axis=1)

    def _apply_fuzzy_keys(
        self,
        df_po: pd.DataFrame,
        df_inv: pd.DataFrame,
        match_params: Sequence[str],
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, bool] | None]:
        """
        For now we focus fuzzy matching on po_number between PO and INV.
        Adjust INV po_number values to their best PO counterpart when
        similarity passes the threshold.
        """
        if "po_number" not in match_params:
            return df_po, df_inv, None

        if "po_number" not in df_po.columns or "po_number" not in df_inv.columns:
            return df_po, df_inv, None

        po_keys = df_po["po_number"].dropna().astype(str).unique().tolist()
        if not po_keys:
            return df_po, df_inv, None

        fuzzy_flags: Dict[str, bool] = {}
        new_po_numbers: List[str] = []
        fuzzy_used_flags: List[bool] = []

        for val in df_inv["po_number"].astype(str).tolist():
            if not val:
                new_po_numbers.append(val)
                fuzzy_used_flags.append(False)
                continue

            best = process.extractOne(
                val, po_keys, scorer=fuzz.token_sort_ratio
            )
            if best and best[1] >= self.config.fuzzy_threshold:
                new_po_numbers.append(best[0])
                fuzzy_used_flags.append(True)
            else:
                new_po_numbers.append(val)
                fuzzy_used_flags.append(False)

        df_inv = df_inv.copy()
        df_inv["po_number"] = new_po_numbers
        df_inv["inv_po_number_fuzzy"] = fuzzy_used_flags
        return df_po, df_inv, fuzzy_flags

    def _build_orphans(
        self,
        df_po: pd.DataFrame,
        df_grn: pd.DataFrame,
        df_inv: pd.DataFrame,
        keys: Sequence[str],
    ) -> pd.DataFrame:
        po_key_set = {
            tuple(row.get(k) for k in keys) for _, row in df_po.iterrows()
        }

        def _key(row) -> Tuple:
            return tuple(row.get(k) for k in keys)

        rows: List[Dict] = []

        # Orphan GRNs
        for _, row in df_grn.iterrows():
            if _key(row) not in po_key_set:
                data: Dict = {}
                for k in keys:
                    data[k] = row.get(k)
                data["has_po"] = False
                data["has_grn"] = True
                data["has_invoice"] = False
                if "grn_quantity" in row.index:
                    data["grn_quantity"] = row["grn_quantity"]
                if "grn_amount" in row.index:
                    data["grn_amount"] = row["grn_amount"]
                rows.append(data)

        # Orphan INVs
        for _, row in df_inv.iterrows():
            if _key(row) not in po_key_set:
                data = {}
                for k in keys:
                    data[k] = row.get(k)
                data["has_po"] = False
                data["has_grn"] = False
                data["has_invoice"] = True
                if "inv_quantity" in row.index:
                    data["inv_quantity"] = row["inv_quantity"]
                if "inv_amount" in row.index:
                    data["inv_amount"] = row["inv_amount"]
                rows.append(data)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        if "editable_notes" not in df.columns:
            df["editable_notes"] = ""
        df["match_confidence"] = "EXACT"
        return df

