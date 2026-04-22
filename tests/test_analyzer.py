"""
Tests for the analysis engine using fixture data.
Validates metric calculations, anomaly detection, and recommendations.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from engine.analyzer import _build_reason_summary
from engine.recommender import size_action, sku_summary


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


# --- Size action tests ---

class TestSizeAction:
    def test_not_flagged_returns_empty(self):
        result = size_action(0.30, 0.20, 0.5, 0.1, 0.1, 0.3, False, 100, 50, 20, 10)
        assert result == ""

    def test_flagged_low_reason_count(self):
        result = size_action(0.30, 0.20, 0.5, 0.1, 0.1, 0.3, True, 100, 50, 5, 10)
        assert "Not enough return reason data" in result

    def test_runs_small_detected(self):
        result = size_action(0.30, 0.20, 0.8, 0.0, 0.1, 0.1, True, 100, 50, 20, 10)
        assert "Runs small" in result

    def test_runs_large_detected(self):
        result = size_action(0.30, 0.20, 0.0, 0.8, 0.1, 0.1, True, 100, 50, 20, 10)
        assert "Runs large" in result

    def test_quality_issue_detected(self):
        result = size_action(0.30, 0.20, 0.0, 0.0, 0.50, 0.5, True, 100, 50, 20, 10)
        assert "Quality" in result


# --- SKU summary tests ---

class TestSkuSummary:
    def test_empty_flagged_returns_empty(self):
        sizes = [
            {"size": "S", "is_flagged": False, "pct_small": 0.5, "pct_large": 0.1, "pct_quality": 0, "stock": 50},
        ]
        result = sku_summary(sizes)
        assert result == ""

    def test_consistent_small_across_sizes(self):
        sizes = [
            {"size": "S", "is_flagged": True, "pct_small": 0.7, "pct_large": 0.0, "pct_quality": 0, "stock": 50},
            {"size": "M", "is_flagged": True, "pct_small": 0.8, "pct_large": 0.0, "pct_quality": 0, "stock": 60},
            {"size": "L", "is_flagged": True, "pct_small": 0.6, "pct_large": 0.0, "pct_quality": 0, "stock": 40},
        ]
        result = sku_summary(sizes)
        assert "small" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
