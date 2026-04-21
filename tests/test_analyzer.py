"""
Tests for the analysis engine using fixture data.
Validates metric calculations, anomaly detection, and recommendations.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

import config
from engine.analyzer import _build_reason_summary, _classify_problem
from engine.recommender import generate_sku_recommendation


# --- Reason summary tests ---

class TestReasonSummary:
    def test_empty_reasons(self):
        top, pct, counts = _build_reason_summary([])
        assert top is None
        assert pct == 0.0
        assert counts == {}

    def test_all_none(self):
        top, pct, counts = _build_reason_summary([None, None, None])
        assert top is None
        assert pct == 0.0

    def test_single_reason(self):
        reasons = ["TOO_SMALL"] * 10
        top, pct, counts = _build_reason_summary(reasons)
        assert top == "TOO_SMALL"
        assert pct == 1.0
        assert counts == {"TOO_SMALL": 10}

    def test_mixed_reasons(self):
        reasons = ["TOO_SMALL"] * 6 + ["EXPECTATION_MISMATCH"] * 3 + [None]
        top, pct, counts = _build_reason_summary(reasons)
        assert top == "TOO_SMALL"
        assert abs(pct - 0.6) < 0.01  # 6 out of 10 total items
        assert counts["TOO_SMALL"] == 6
        assert counts["EXPECTATION_MISMATCH"] == 3


# --- Problem classification tests ---

class TestClassifyProblem:
    def test_sizing_by_concentration(self):
        result = _classify_problem(
            top_reason="TOO_SMALL",
            reason_pct=0.5,
            reason_counts={"TOO_SMALL": 10, "OTHER": 5},
            size_concentration=2.0,
            anomaly_sizes=[{"size": "S", "return_rate": 0.6}],
            has_reason_data=True,
        )
        assert result == "SIZING"

    def test_quality_by_defect_share(self):
        result = _classify_problem(
            top_reason="DEFECTIVE_PRODUCT",
            reason_pct=0.5,
            reason_counts={"DEFECTIVE_PRODUCT": 10, "OTHER": 5},
            size_concentration=1.1,
            anomaly_sizes=[],
            has_reason_data=True,
        )
        assert result == "QUALITY"

    def test_listing_by_expectation_mismatch(self):
        result = _classify_problem(
            top_reason="EXPECTATION_MISMATCH",
            reason_pct=0.5,
            reason_counts={"EXPECTATION_MISMATCH": 10, "OTHER": 5},
            size_concentration=1.1,
            anomaly_sizes=[],
            has_reason_data=True,
        )
        assert result == "LISTING"

    def test_unknown_when_no_clear_signal(self):
        result = _classify_problem(
            top_reason="OTHER",
            reason_pct=0.2,
            reason_counts={"OTHER": 3, "TOO_SMALL": 2, "NO_LONGER_WANTED": 2},
            size_concentration=1.1,
            anomaly_sizes=[],
            has_reason_data=True,
        )
        assert result == "UNKNOWN"

    def test_unknown_when_no_reason_data(self):
        result = _classify_problem(
            top_reason=None,
            reason_pct=0,
            reason_counts={},
            size_concentration=1.1,
            anomaly_sizes=[],
            has_reason_data=False,
        )
        assert result == "UNKNOWN"


# --- Recommendation tests ---

class TestRecommendations:
    def _make_row(self, **overrides):
        base = {
            "sku_prefix": "TEST-001",
            "product_name": "Test Product",
            "return_rate": 0.30,
            "category_baseline": 0.18,
            "deviation": 0.12,
            "deviation_pct": 0.67,
            "total_sold": 100,
            "total_returned": 30,
            "problem_type": "UNKNOWN",
            "top_reason": None,
            "top_reason_pct": 0,
            "supplier_name": "TestSupplier",
            "anomaly_sizes": [],
            "has_reason_data": False,
            "channels": ["trendyol"],
        }
        base.update(overrides)
        return base

    def test_sizing_recommendation_mentions_spec_sheet(self):
        row = self._make_row(
            problem_type="SIZING",
            top_reason="TOO_SMALL",
            anomaly_sizes=[{"size": "S", "return_rate": 0.5, "sold": 30, "returned": 15}],
            has_reason_data=True,
        )
        rec = generate_sku_recommendation(row)
        assert "spec sheet" in rec.lower() or "sizing" in rec.lower()
        assert "runs small" in rec.lower()

    def test_quality_recommendation_mentions_supplier(self):
        row = self._make_row(
            problem_type="QUALITY",
            top_reason="DEFECTIVE_PRODUCT",
            top_reason_pct=0.5,
            has_reason_data=True,
        )
        rec = generate_sku_recommendation(row)
        assert "TestSupplier" in rec
        assert "defect" in rec.lower() or "inspect" in rec.lower()

    def test_no_reason_data_acknowledged(self):
        row = self._make_row(has_reason_data=False)
        rec = generate_sku_recommendation(row)
        assert "no return reason data" in rec.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
