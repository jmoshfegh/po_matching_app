from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


@dataclass
class ToleranceConfig:
    amount_tolerance_pct: float = 2.0
    amount_tolerance_abs: float = 10.0
    quantity_tolerance_pct: float = 0.0
    use_stricter: bool = True


class DiscrepancyEngine:
    """
    Evaluates amount and quantity discrepancies using configured tolerances.
    """

    def __init__(self, config: ToleranceConfig | Dict):
        if isinstance(config, dict):
            self.config = ToleranceConfig(**config)
        else:
            self.config = config

    def evaluate_row(
        self,
        po_amount: float,
        inv_amount: float,
        po_qty: float,
        grn_qty: float,
    ) -> Dict[str, object]:
        amount_ok, amount_detail = self._check_amount(po_amount, inv_amount)
        quantity_ok, qty_detail = self._check_quantity(po_qty, grn_qty)

        details = ", ".join(
            [d for d in [amount_detail, qty_detail] if d]
        ) or "Within tolerance"

        return {
            "amount_ok": amount_ok,
            "quantity_ok": quantity_ok,
            "discrepancy_details": details,
        }

    # ------------------------------------------------------------------
    # Amount logic
    # ------------------------------------------------------------------
    def _check_amount(self, po_amount: float, inv_amount: float) -> Tuple[bool, str]:
        cfg = self.config
        po_amount = float(po_amount or 0.0)
        inv_amount = float(inv_amount or 0.0)

        diff = inv_amount - po_amount
        abs_diff = abs(diff)
        pct_diff = abs_diff / po_amount * 100 if po_amount else 0.0

        abs_limit = cfg.amount_tolerance_abs
        pct_limit = cfg.amount_tolerance_pct

        if cfg.use_stricter:
            allowed = min(abs_limit, po_amount * pct_limit / 100 if po_amount else abs_limit)
        else:
            allowed = max(abs_limit, po_amount * pct_limit / 100 if po_amount else abs_limit)

        ok = abs_diff <= allowed + 1e-9

        direction = "equals"
        if diff > 0:
            direction = "exceeds"
        elif diff < 0:
            direction = "is below"

        if not po_amount and not inv_amount:
            return True, ""

        msg = (
            f"Invoice {direction} PO by ${abs_diff:0.2f} "
            f"({pct_diff:0.1f}%) — "
            f"{'within' if ok else 'above'} {pct_limit:0.1f}% tolerance"
        )
        return ok, msg

    # ------------------------------------------------------------------
    # Quantity logic
    # ------------------------------------------------------------------
    def _check_quantity(self, po_qty: float, grn_qty: float) -> Tuple[bool, str]:
        cfg = self.config
        po_qty = float(po_qty or 0.0)
        grn_qty = float(grn_qty or 0.0)

        diff = grn_qty - po_qty
        abs_diff = abs(diff)

        if po_qty:
            pct_diff = abs_diff / po_qty * 100
        else:
            pct_diff = 0.0

        limit = cfg.quantity_tolerance_pct

        ok = pct_diff <= limit + 1e-9

        if not po_qty and not grn_qty:
            return True, ""

        direction = "exceeds" if diff > 0 else "is below" if diff < 0 else "equals"

        msg = (
            f"GRN quantity {direction} PO by {abs_diff:0.2f} "
            f"({pct_diff:0.1f}%) — "
            f"{'within' if ok else 'above'} {limit:0.1f}% tolerance"
        )
        return ok, msg

    # ------------------------------------------------------------------
    # DataFrame-level helper
    # ------------------------------------------------------------------
    def evaluate_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Given a DataFrame with the standardised columns:
        po_amount, inv_amount, po_quantity, grn_quantity
        returns a copy with amount_ok, quantity_ok, discrepancy_details.
        """
        df = df.copy()
        results = df.apply(
            lambda row: self.evaluate_row(
                row.get("po_amount", np.nan),
                row.get("inv_amount", np.nan),
                row.get("po_quantity", np.nan),
                row.get("grn_quantity", np.nan),
            ),
            axis=1,
        )

        df["amount_ok"] = results.map(lambda r: r["amount_ok"])
        df["quantity_ok"] = results.map(lambda r: r["quantity_ok"])
        df["discrepancy_details"] = results.map(lambda r: r["discrepancy_details"])
        return df

