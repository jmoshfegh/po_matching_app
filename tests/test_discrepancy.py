from core.discrepancy import DiscrepancyEngine, ToleranceConfig


def test_within_tolerance_passes():
    cfg = ToleranceConfig(
        amount_tolerance_pct=2.0,
        amount_tolerance_abs=10.0,
        quantity_tolerance_pct=5.0,
        use_stricter=True,
    )
    engine = DiscrepancyEngine(cfg)

    result = engine.evaluate_row(po_amount=100.0, inv_amount=101.0, po_qty=100, grn_qty=102)

    assert result["amount_ok"] is True
    assert result["quantity_ok"] is True


def test_above_tolerance_fails():
    cfg = ToleranceConfig(
        amount_tolerance_pct=2.0,
        amount_tolerance_abs=5.0,
        quantity_tolerance_pct=1.0,
        use_stricter=True,
    )
    engine = DiscrepancyEngine(cfg)

    result = engine.evaluate_row(po_amount=100.0, inv_amount=120.0, po_qty=100, grn_qty=103)

    assert result["amount_ok"] is False
    assert result["quantity_ok"] is False


def test_discrepancy_message_format():
    cfg = ToleranceConfig(
        amount_tolerance_pct=2.0,
        amount_tolerance_abs=1.0,
        quantity_tolerance_pct=0.0,
        use_stricter=True,
    )
    engine = DiscrepancyEngine(cfg)

    result = engine.evaluate_row(po_amount=100.0, inv_amount=105.0, po_qty=100, grn_qty=110)
    msg = result["discrepancy_details"]

    assert "Invoice exceeds PO by $" in msg
    assert "%" in msg
    assert "tolerance" in msg


def test_stricter_rule_applied():
    # With higher pct but low abs and use_stricter=True, abs should dominate.
    cfg = ToleranceConfig(
        amount_tolerance_pct=10.0,
        amount_tolerance_abs=2.0,
        quantity_tolerance_pct=0.0,
        use_stricter=True,
    )
    engine = DiscrepancyEngine(cfg)

    # 5 difference, above abs limit 2, below pct limit (10% of 100)
    result = engine.evaluate_row(po_amount=100.0, inv_amount=105.0, po_qty=100, grn_qty=100)

    assert result["amount_ok"] is False

