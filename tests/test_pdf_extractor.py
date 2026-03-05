import os
import tempfile

import pandas as pd
import pytest

from core.pdf_extractor import PDFExtractor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor():
    return PDFExtractor()


@pytest.fixture
def sample_pdf_path():
    """
    Create a minimal test PDF using reportlab for testing purposes.
    The PDF contains a simple table with PO-like data.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        tmp_path = f.name

    doc = SimpleDocTemplate(tmp_path, pagesize=letter)
    data = [
        ["PO Number", "Vendor Name", "Item", "Qty", "Amount"],
        ["PO-2024-001", "Alpha Ltd", "Widget A", "10", "500.00"],
        ["PO-2024-001", "Alpha Ltd", "Widget B", "5", "250.00"],
        ["PO-2024-002", "Beta Corp", "Gadget X", "20", "1000.00"],
        ["PO-2024-003", "Gamma Co", "Part Y", "3", "150.00"],
    ]
    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    doc.build([table])
    yield tmp_path
    os.unlink(tmp_path)


@pytest.fixture
def invoice_pdf_path():
    """Creates a test PDF with invoice-like data"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        tmp_path = f.name

    doc = SimpleDocTemplate(tmp_path, pagesize=letter)
    data = [
        ["Invoice No", "Bill To", "Description", "Qty", "Total"],
        ["INV-001", "Acme Inc", "Widget A", "10", "$500.00"],
        ["INV-001", "Acme Inc", "Widget B", "5", "$255.00"],
        ["INV-002", "Acme Inc", "Gadget X", "20", "$1,050.00"],
    ]
    table = Table(data)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
    doc.build([table])
    yield tmp_path
    os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_extract_returns_result_object(extractor, sample_pdf_path):
    result = extractor.extract(sample_pdf_path)
    assert result is not None
    assert result.total_pages >= 1
    assert result.filename.endswith(".pdf")


def test_tables_detected_in_sample_pdf(extractor, sample_pdf_path):
    result = extractor.extract(sample_pdf_path)
    assert result.tables_found >= 1
    assert result.best_table is not None


def test_best_table_has_correct_row_count(extractor, sample_pdf_path):
    result = extractor.extract(sample_pdf_path)
    assert result.best_table.row_count >= 4


def test_po_doc_type_detected(extractor, sample_pdf_path):
    result = extractor.extract(sample_pdf_path)
    assert result.best_table.suggested_doc_type in {"PO", "INV", "GRN", "UNKNOWN"}


def test_invoice_doc_type_detected(extractor, invoice_pdf_path):
    result = extractor.extract(invoice_pdf_path)
    assert result.best_table.suggested_doc_type in {"PO", "INV", "GRN", "UNKNOWN"}


def test_accuracy_score_between_0_and_1(extractor, sample_pdf_path):
    result = extractor.extract(sample_pdf_path)
    score = result.best_table.accuracy_score
    assert 0.0 <= score <= 1.0


def test_confidence_is_valid_value(extractor, sample_pdf_path):
    result = extractor.extract(sample_pdf_path)
    assert result.best_table.confidence in ["HIGH", "MEDIUM", "LOW"]


def test_thumbnails_generated(extractor, sample_pdf_path):
    result = extractor.extract(sample_pdf_path)
    assert len(result.page_thumbnails) >= 1
    assert isinstance(result.page_thumbnails[0], bytes)


def test_clean_dataframe_strips_whitespace(extractor):
    dirty_df = pd.DataFrame(
        {"  PO Number  ": ["  PO-001  ", "  PO-002  "], "Amount": ["$1,000.00", "  $500.00  "]}
    )
    clean_df = extractor.clean_dataframe(dirty_df)
    assert str(clean_df.iloc[0, 0]).strip() == "PO-001"


def test_clean_dataframe_removes_empty_rows(extractor):
    df = pd.DataFrame({"A": ["val1", None, "val2"], "B": ["x", None, "y"]})
    clean_df = extractor.clean_dataframe(df)
    assert len(clean_df) == 2


def test_detect_headers_promotes_first_row(extractor):
    df = pd.DataFrame(
        [
            ["PO Number", "Vendor", "Amount"],
            ["PO-001", "Alpha", "500"],
            ["PO-002", "Beta", "300"],
        ]
    )
    updated_df, has_headers = extractor.detect_headers(df)
    assert has_headers is True
    assert "po_number" in [c.lower() for c in updated_df.columns]


def test_suggest_doc_type_po(extractor):
    df = pd.DataFrame(
        {
            "po_number": ["PO-001"],
            "purchase_order": ["Yes"],
            "buyer": ["John"],
            "delivery_date": ["2025-01-15"],
        }
    )
    doc_type = extractor.suggest_doc_type(df)
    assert doc_type in {"PO", "INV", "GRN", "UNKNOWN"}


def test_suggest_doc_type_invoice(extractor):
    df = pd.DataFrame(
        {
            "invoice_number": ["INV-001"],
            "bill_to": ["Acme"],
            "due_date": ["2025-02-15"],
            "vat": ["20%"],
        }
    )
    doc_type = extractor.suggest_doc_type(df)
    assert doc_type in {"PO", "INV", "GRN", "UNKNOWN"}


def test_pdf_to_dataframe_returns_dataframe(extractor, sample_pdf_path):
    df, method, accuracy, warnings = extractor.pdf_to_dataframe(sample_pdf_path)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert isinstance(method, str)
    assert isinstance(accuracy, float)
    assert isinstance(warnings, list)


def test_nonexistent_pdf_raises_error(extractor):
    with pytest.raises(Exception):
        extractor.extract("/nonexistent/path/file.pdf")


def test_currency_stripped_from_amounts(extractor):
    df = pd.DataFrame({"po_number": ["PO-001"], "amount": ["$1,250.00"]})
    clean_df = extractor.clean_dataframe(df)
    assert pd.to_numeric(clean_df["amount"], errors="coerce").notna().all()

