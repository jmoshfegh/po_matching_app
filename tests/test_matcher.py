import pandas as pd

from core.matcher import ThreeWayMatcher, MatcherConfig
from core.discrepancy import ToleranceConfig


def _build_basic_matcher():
    cfg = MatcherConfig(
        fuzzy_threshold=85,
        tolerance=ToleranceConfig(
            amount_tolerance_pct=2.0,
            amount_tolerance_abs=10.0,
            quantity_tolerance_pct=5.0,
            use_stricter=True,
        ),
    )
    return ThreeWayMatcher(cfg)


def test_exact_three_way_match():
    po = pd.DataFrame(
        [
            {
                "po_number": "PO-1",
                "vendor_name": "Vendor A",
                "line_item": 1,
                "quantity": 10,
                "amount": 100.0,
            }
        ]
    )
    grn = pd.DataFrame(
        [
            {
                "po_number": "PO-1",
                "vendor_name": "Vendor A",
                "line_item": 1,
                "quantity": 10,
            }
        ]
    )
    inv = pd.DataFrame(
        [
            {
                "po_number": "PO-1",
                "vendor_name": "Vendor A",
                "line_item": 1,
                "quantity": 10,
                "amount": 100.0,
            }
        ]
    )

    matcher = _build_basic_matcher()
    out = matcher.match(po, grn, inv, match_params=["po_number", "vendor_name", "line_item"])

    assert len(out) == 1
    assert out.loc[0, "match_status"] == "FULL MATCH"


def test_fuzzy_match_po_number_variant():
    po = pd.DataFrame(
        [
            {
                "po_number": "PO-2024-0001",
                "vendor_name": "Vendor A",
                "line_item": 1,
                "quantity": 5,
                "amount": 50.0,
            }
        ]
    )
    grn = pd.DataFrame(columns=["po_number", "vendor_name", "line_item", "quantity"])
    inv = pd.DataFrame(
        [
            {
                "po_number": "PO2024-0001",  # missing dash
                "vendor_name": "Vendor A",
                "line_item": 1,
                "quantity": 5,
                "amount": 50.0,
            }
        ]
    )

    matcher = _build_basic_matcher()
    out = matcher.match(po, grn, inv, match_params=["po_number", "vendor_name", "line_item"])

    assert len(out) == 1
    # Cast to bool to avoid identity issues with numpy.bool_
    assert bool(out.loc[0, "has_invoice"]) is True
    assert out.loc[0, "match_confidence"] == "FUZZY"


def test_missing_grn_creates_partial():
    po = pd.DataFrame(
        [
            {
                "po_number": "PO-2",
                "vendor_name": "Vendor A",
                "line_item": 1,
                "quantity": 10,
                "amount": 100.0,
            }
        ]
    )
    grn = pd.DataFrame(columns=["po_number", "vendor_name", "line_item", "quantity"])
    inv = pd.DataFrame(
        [
            {
                "po_number": "PO-2",
                "vendor_name": "Vendor A",
                "line_item": 1,
                "quantity": 10,
                "amount": 100.0,
            }
        ]
    )

    matcher = _build_basic_matcher()
    out = matcher.match(po, grn, inv, match_params=["po_number", "vendor_name", "line_item"])

    assert len(out) == 1
    assert out.loc[0, "match_status"] == "PARTIAL MATCH"
    assert out.loc[0, "match_subtype"] == "Missing GRN"


def test_orphan_invoice_unmatched():
    po = pd.DataFrame(
        [
            {
                "po_number": "PO-3",
                "vendor_name": "Vendor A",
                "line_item": 1,
                "quantity": 10,
                "amount": 100.0,
            }
        ]
    )
    grn = pd.DataFrame(columns=["po_number", "vendor_name", "line_item", "quantity"])
    inv = pd.DataFrame(
        [
            {
                "po_number": "PO-ORPHAN",
                "vendor_name": "Vendor B",
                "line_item": 1,
                "quantity": 5,
                "amount": 50.0,
            }
        ]
    )

    matcher = _build_basic_matcher()
    out = matcher.match(po, grn, inv, match_params=["po_number", "vendor_name", "line_item"])

    # One row for anchored PO, one row for orphan invoice
    assert len(out) == 2
    orphan_rows = out[out["has_po"] == False]  # noqa: E712
    assert len(orphan_rows) == 1
    assert orphan_rows.iloc[0]["match_status"] == "UNMATCHED"

