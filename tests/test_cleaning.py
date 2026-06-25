import pandas as pd
import pytest

from app.services.csv_cleaner import CsvCleaner


@pytest.fixture
def cleaner() -> CsvCleaner:
    return CsvCleaner()


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "txn_id": ["TXN001", "TXN002", "TXN003", "TXN001"],
        "date": ["04-09-2024", "2024/02/05", "2024-07-15", "04-09-2024"],
        "merchant": [" Flipkart ", "Swiggy", "Amazon", " Flipkart "],
        "amount": [1000.0, "$2000.0", 3000.0, 1000.0],
        "currency": ["inr", "usd", "INR", "inr"],
        "status": ["success", "FAILED", "pending", "success"],
        "category": ["Shopping", "Food", None, "Shopping"],
        "account_id": ["ACC001", "ACC002", "ACC003", "ACC001"],
        "notes": ["", "", "", ""],
    })


class TestCsvCleaner:
    def test_normalizes_dates(self, cleaner: CsvCleaner, sample_df: pd.DataFrame) -> None:
        result = cleaner.clean(sample_df)
        assert result["date"].iloc[0] == "2024-09-04"
        assert result["date"].iloc[1] == "2024-02-05"
        assert result["date"].iloc[2] == "2024-07-15"

    def test_removes_currency_symbols(self, cleaner: CsvCleaner, sample_df: pd.DataFrame) -> None:
        result = cleaner.clean(sample_df)
        assert result["amount"].iloc[1] == 2000.0

    def test_normalizes_currency_casing(self, cleaner: CsvCleaner, sample_df: pd.DataFrame) -> None:
        result = cleaner.clean(sample_df)
        assert result["currency"].iloc[0] == "INR"
        assert result["currency"].iloc[1] == "USD"

    def test_normalizes_status_casing(self, cleaner: CsvCleaner, sample_df: pd.DataFrame) -> None:
        result = cleaner.clean(sample_df)
        assert result["status"].iloc[0] == "SUCCESS"

    def test_trims_whitespace(self, cleaner: CsvCleaner, sample_df: pd.DataFrame) -> None:
        result = cleaner.clean(sample_df)
        assert result["merchant"].iloc[0] == "Flipkart"

    def test_removes_duplicates(self, cleaner: CsvCleaner, sample_df: pd.DataFrame) -> None:
        result = cleaner.clean(sample_df)
        assert len(result) == 3

    def test_fills_missing_categories(self, cleaner: CsvCleaner, sample_df: pd.DataFrame) -> None:
        result = cleaner.clean(sample_df)
        assert result["category"].iloc[2] == "Uncategorised"
