from pathlib import Path

import pandas as pd

from core.loader import DataLoader, ALIAS_MAP


def _build_df(columns, rows=None):
    rows = rows or []
    return pd.DataFrame(rows, columns=columns)


def test_detect_po_file_by_headers(tmp_path):
    df = _build_df(["PO Number", "Vendor Name"])
    path = tmp_path / "po.xlsx"
    df.to_excel(path, index=False)

    loader = DataLoader()
    df_read = loader._read_any(Path(path))
    doc_type, ambiguous = loader._detect_document_type(df_read)

    assert doc_type == "PO"
    assert ambiguous is False


def test_detect_grn_file_by_headers(tmp_path):
    df = _build_df(["GRN Number", "Vendor Name"])
    path = tmp_path / "grn.xlsx"
    df.to_excel(path, index=False)

    loader = DataLoader()
    df_read = loader._read_any(Path(path))
    doc_type, ambiguous = loader._detect_document_type(df_read)

    assert doc_type == "GRN"
    assert ambiguous is False


def test_column_normalization():
    df = _build_df(
        ["PO Number", "Vendor", "Line Amount", "PO Date", "Quantity", "Unit Price"],
        [[
            "PO-1",
            "Vendor A",
            "100.00",
            "2024-01-01",
            "10",
            "10.00",
        ]],
    )
    loader = DataLoader()
    df_norm = loader._normalise_columns(df)

    assert "po_number" in df_norm.columns
    assert "vendor_name" in df_norm.columns
    assert "amount" in df_norm.columns
    assert "doc_date" in df_norm.columns
    assert "quantity" in df_norm.columns
    assert "unit_price" in df_norm.columns


def test_missing_required_column_raises_error():
    # Build a DF that will not map vendor_name
    df = _build_df(["PO Number"], [["PO-1"]])
    loader = DataLoader()
    df_norm = loader._normalise_columns(df)

    try:
        loader._validate_required(df_norm)
    except ValueError as exc:
        assert "vendor_name" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing required columns")

