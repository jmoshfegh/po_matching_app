import pandas as pd

from core.categorizer import Categorizer, FULL_MATCH, PARTIAL_MATCH, UNMATCHED


def test_full_match_classification():
    df = pd.DataFrame(
        [
            {
                "has_po": True,
                "has_grn": True,
                "has_invoice": True,
                "amount_ok": True,
                "quantity_ok": True,
                "po_amount": 100.0,
                "inv_amount": 100.0,
            }
        ]
    )
    cat = Categorizer()
    out = cat.categorize_dataframe(df)

    assert out.loc[0, "match_status"] == FULL_MATCH
    assert out.loc[0, "match_subtype"] == ""


def test_partial_missing_grn():
    df = pd.DataFrame(
        [
            {
                "has_po": True,
                "has_grn": False,
                "has_invoice": True,
                "amount_ok": True,
                "quantity_ok": True,
            }
        ]
    )
    cat = Categorizer()
    out = cat.categorize_dataframe(df)

    assert out.loc[0, "match_status"] == PARTIAL_MATCH
    assert out.loc[0, "match_subtype"] == "Missing GRN"


def test_overbilled_classification():
    df = pd.DataFrame(
        [
            {
                "has_po": True,
                "has_grn": True,
                "has_invoice": True,
                "amount_ok": False,
                "quantity_ok": True,
                "po_amount": 100.0,
                "inv_amount": 120.0,
            }
        ]
    )
    cat = Categorizer()
    out = cat.categorize_dataframe(df)

    assert out.loc[0, "match_status"] == PARTIAL_MATCH
    assert out.loc[0, "match_subtype"] == "Over-billed"


def test_underbilled_classification():
    df = pd.DataFrame(
        [
            {
                "has_po": True,
                "has_grn": True,
                "has_invoice": True,
                "amount_ok": False,
                "quantity_ok": True,
                "po_amount": 100.0,
                "inv_amount": 80.0,
            }
        ]
    )
    cat = Categorizer()
    out = cat.categorize_dataframe(df)

    assert out.loc[0, "match_status"] == PARTIAL_MATCH
    assert out.loc[0, "match_subtype"] == "Under-billed"

