import pandas as pd
import pytest

from app.services.anomaly_detector import AnomalyDetector


@pytest.fixture
def detector() -> AnomalyDetector:
    return AnomalyDetector()


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "txn_id": ["TXN001", "TXN002", "TXN003", "TXN004"],
        "amount": [100.0, 500.0, 20.0, 30.0],
        "currency": ["INR", "USD", "INR", "USD"],
        "merchant": ["Flipkart", "Swiggy", "Amazon", "Amazon"],
        "account_id": ["ACC001", "ACC001", "ACC002", "ACC002"],
        "category": ["Shopping", "Food", "Shopping", "Shopping"],
        "date": ["2024-01-01"] * 4,
        "status": ["SUCCESS"] * 4,
    })


class TestAnomalyDetector:
    def test_rule_amount_vs_median(self, detector: AnomalyDetector, sample_df: pd.DataFrame) -> None:
        result = detector.detect(sample_df)
        acc1 = result[result["account_id"] == "ACC001"]
        acc1_anomalies = acc1[acc1["is_anomaly"]]
        assert len(acc1_anomalies) == 1
        assert acc1_anomalies.iloc[0]["txn_id"] == "TXN002"

    def test_rule_usd_merchant(self, detector: AnomalyDetector, sample_df: pd.DataFrame) -> None:
        result = detector.detect(sample_df)
        swiggy_row = result[result["merchant"] == "Swiggy"]
        assert swiggy_row.iloc[0]["is_anomaly"]
        assert "USD" in swiggy_row.iloc[0]["anomaly_reason"]

    def test_no_anomalies_for_normal(self, detector: AnomalyDetector) -> None:
        df = pd.DataFrame({
            "txn_id": ["TXN001"],
            "amount": [50.0],
            "currency": ["INR"],
            "merchant": ["Amazon"],
            "account_id": ["ACC001"],
            "category": ["Shopping"],
            "date": ["2024-01-01"],
            "status": ["SUCCESS"],
        })
        result = detector.detect(df)
        assert not result.iloc[0]["is_anomaly"]
