import random
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Union

import numpy as np
import pandas as pd


VENDORS = [
    "Alpha Supplies Ltd",
    "Beta Corp",
    "Gamma Trading",
    "Delta Electronics",
    "Epsilon Goods",
    "Zeta Importers",
    "Eta Manufacturing",
    "Theta Distributors",
]


@dataclass
class Item:
    item_code: str
    item_description: str
    standard_unit_price: float


class DatasetGenerator:
    """
    Generates synthetic PO, GRN, and Invoice datasets for testing.
    """

    def __init__(self, random_seed: int = 42) -> None:
        self.random_seed = random_seed
        random.seed(random_seed)
        np.random.seed(random_seed)
        self.items = self._generate_items()

    def _generate_items(self) -> List[Item]:
        items: List[Item] = []
        for i in range(1, 16):
            code = f"ITEM-{i:03d}"
            desc = f"Product Line {i:03d}"
            base_price = round(random.uniform(10.0, 500.0), 2)
            items.append(Item(code, desc, base_price))
        return items

    def _choose_items_for_po(self) -> List[Item]:
        count = random.randint(1, 5)
        return random.sample(self.items, count)

    def generate(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        po_rows = []
        grn_rows = []
        inv_rows = []

        start_date = datetime(2024, 1, 1)

        for idx in range(1, 51):
            po_number = f"PO-2024-{idx:04d}"
            vendor = random.choice(VENDORS)
            po_date = start_date + timedelta(days=random.randint(0, 90))
            items_for_po = self._choose_items_for_po()

            for line_idx, item in enumerate(items_for_po, start=1):
                qty = random.randint(1, 100)
                unit_price = round(
                    item.standard_unit_price * random.uniform(0.95, 1.05), 2
                )
                amount = round(qty * unit_price, 2)

                po_rows.append(
                    {
                        "PO Number": po_number,
                        "Vendor Name": vendor,
                        "PO Date": po_date,
                        "Line Item": line_idx,
                        "Item Code": item.item_code,
                        "Item Description": item.item_description,
                        "Quantity": qty,
                        "Unit Price": unit_price,
                        "Line Amount": amount,
                    }
                )

                # GRN generation (80% of POs have GRN)
                if random.random() < 0.8:
                    grn_qty = int(
                        round(
                            qty
                            * random.choice(
                                [1.0, random.uniform(0.9, 1.1)]
                            )
                        )
                    )
                    grn_date = po_date + timedelta(days=random.randint(0, 14))

                    grn_rows.append(
                        {
                            "GRN Number": f"GRN-{idx:04d}",
                            "PO Number": po_number,
                            "Vendor Name": vendor,
                            "GRN Date": grn_date,
                            "Line Item": line_idx,
                            "Item Code": item.item_code,
                            "Item Description": item.item_description,
                            "Quantity Received": grn_qty,
                        }
                    )

                # Invoice generation (85% of POs have INV)
                if random.random() < 0.85:
                    inv_style = random.choice(["with_dash", "without_dash"])
                    if inv_style == "with_dash":
                        inv_po_number = po_number
                    else:
                        inv_po_number = po_number.replace("-", "")

                    base_amount = amount
                    r = random.random()
                    if r < 0.6:
                        inv_amount = base_amount
                    elif r < 0.8:
                        inv_amount = base_amount * random.uniform(0.98, 1.02)
                    elif r < 0.9:
                        inv_amount = base_amount * random.uniform(1.03, 1.15)
                    else:
                        inv_amount = base_amount * random.uniform(0.90, 0.97)

                    inv_amount = round(inv_amount, 2)

                    inv_rows.append(
                        {
                            "Invoice Number": f"INV-{idx:04d}",
                            "PO Number": inv_po_number,
                            "Vendor Name": vendor,
                            "Invoice Date": po_date
                            + timedelta(days=random.randint(5, 30)),
                            "Line Item": line_idx,
                            "Item Code": item.item_code,
                            "Item Description": item.item_description,
                            "Quantity Invoiced": qty,
                            "Line Amount": inv_amount,
                        }
                    )

        # Orphan invoices
        for j in range(1, 6):
            item = random.choice(self.items)
            qty = random.randint(1, 50)
            unit_price = item.standard_unit_price
            amount = round(qty * unit_price, 2)
            vendor = random.choice(VENDORS)
            inv_rows.append(
                {
                    "Invoice Number": f"ORPHAN-INV-{j:03d}",
                    "PO Number": f"PO-ORPHAN-{j:03d}",
                    "Vendor Name": vendor,
                    "Invoice Date": start_date + timedelta(days=random.randint(0, 120)),
                    "Line Item": 1,
                    "Item Code": item.item_code,
                    "Item Description": item.item_description,
                    "Quantity Invoiced": qty,
                    "Line Amount": amount,
                }
            )

        # Duplicate invoice numbers
        if inv_rows:
            for k in range(2):
                base_row = random.choice(inv_rows)
                dup = base_row.copy()
                dup["Invoice Number"] = base_row["Invoice Number"]
                inv_rows.append(dup)

        def _add_noise_vendor(v: str) -> str:
            v = v.strip()
            if random.random() < 0.5:
                v = v.upper()
            elif random.random() < 0.5:
                v = v.lower()
            if random.random() < 0.3:
                v = " " + v
            if random.random() < 0.3:
                v = v + " "
            return v

        for row in po_rows:
            row["Vendor Name"] = _add_noise_vendor(row["Vendor Name"])
        for row in grn_rows:
            row["Vendor Name"] = _add_noise_vendor(row["Vendor Name"])
        for row in inv_rows:
            row["Vendor Name"] = _add_noise_vendor(row["Vendor Name"])

        df_po = pd.DataFrame(po_rows)
        df_grn = pd.DataFrame(grn_rows)
        df_inv = pd.DataFrame(inv_rows)

        return df_po, df_grn, df_inv

    def save_to_excel(self, base_path: Union[str, Path, None] = None) -> None:
        df_po, df_grn, df_inv = self.generate()

        if base_path is None:
            base_path = Path(__file__).resolve().parent
        else:
            base_path = Path(base_path)
        base_path.mkdir(parents=True, exist_ok=True)

        po_path = base_path / "sample_po.xlsx"
        grn_path = base_path / "sample_grn.xlsx"
        inv_path = base_path / "sample_invoice.xlsx"

        df_po.to_excel(po_path, index=False)
        df_grn.to_excel(grn_path, index=False)
        df_inv.to_excel(inv_path, index=False)


if __name__ == "__main__":
    gen = DatasetGenerator()
    gen.save_to_excel()
