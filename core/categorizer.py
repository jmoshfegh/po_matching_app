from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd


FULL_MATCH = "FULL MATCH"
PARTIAL_MATCH = "PARTIAL MATCH"
UNMATCHED = "UNMATCHED"

COLOR_MAP: Dict[str, str] = {
    FULL_MATCH: "#28a745",
    PARTIAL_MATCH: "#fd7e14",
    UNMATCHED: "#dc3545",
}


@dataclass
class Categorizer:
    """
    Assigns human-readable match_status and subtypes for matched rows.
    """

    def classify_row(self, row: pd.Series) -> Dict[str, str]:
        has_po = bool(row.get("has_po", True))
        has_grn = bool(row.get("has_grn", False))
        has_invoice = bool(row.get("has_invoice", False))

        amount_ok = bool(row.get("amount_ok", True))
        quantity_ok = bool(row.get("quantity_ok", True))

        po_amount = row.get("po_amount")
        inv_amount = row.get("inv_amount")

        status = UNMATCHED
        subtype = ""

        # UNMATCHED logic for orphans
        if not has_po:
            return {
                "match_status": UNMATCHED,
                "match_subtype": "Orphan Document",
                "status_color": COLOR_MAP[UNMATCHED],
            }

        if has_po and has_grn and has_invoice:
            if amount_ok and quantity_ok:
                status = FULL_MATCH
                subtype = ""
            else:
                status = PARTIAL_MATCH
                if not quantity_ok and amount_ok:
                    subtype = "Quantity Discrepancy"
                elif not amount_ok and quantity_ok:
                    # Decide on over/under billed based on sign
                    if po_amount is not None and inv_amount is not None:
                        try:
                            if float(inv_amount) > float(po_amount):
                                subtype = "Over-billed"
                            elif float(inv_amount) < float(po_amount):
                                subtype = "Under-billed"
                            else:
                                subtype = "Amount Discrepancy"
                        except Exception:
                            subtype = "Amount Discrepancy"
                    else:
                        subtype = "Amount Discrepancy"
                else:
                    # Both off – prefer over/under if we can tell
                    if po_amount is not None and inv_amount is not None:
                        try:
                            if float(inv_amount) > float(po_amount):
                                subtype = "Over-billed"
                            elif float(inv_amount) < float(po_amount):
                                subtype = "Under-billed"
                            else:
                                subtype = "Amount & Quantity Discrepancy"
                        except Exception:
                            subtype = "Amount & Quantity Discrepancy"
                    else:
                        subtype = "Amount & Quantity Discrepancy"

        elif has_po and has_invoice and not has_grn:
            status = PARTIAL_MATCH
            subtype = "Missing GRN"
        elif has_po and has_grn and not has_invoice:
            status = PARTIAL_MATCH
            subtype = "Missing Invoice"
        else:
            status = UNMATCHED
            subtype = "Orphan PO"

        return {
            "match_status": status,
            "match_subtype": subtype,
            "status_color": COLOR_MAP[status],
        }

    def categorize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        results = df.apply(self.classify_row, axis=1)

        df["match_status"] = results.map(lambda r: r["match_status"])
        df["match_subtype"] = results.map(lambda r: r["match_subtype"])
        df["status_color"] = results.map(lambda r: r["status_color"])
        return df

