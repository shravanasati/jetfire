import re
from datetime import datetime

import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

DATE_FORMATS = [
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%Y-%m-%d",
]

CURRENCY_SYMBOL_PATTERN = re.compile(r"^[£$€¥₹]")

MERCHANT_BLACKLIST = frozenset({"", "nan", None})


def _parse_date(date_str: str) -> str:
    date_str = str(date_str).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue
    logger.warning("Could not parse date: %s, using as-is", date_str)
    return date_str


def _clean_amount(value: object) -> float:
    cleaned = str(value).strip()
    cleaned = CURRENCY_SYMBOL_PATTERN.sub("", cleaned)
    return float(cleaned)


def _clean_currency(value: object) -> str:
    return str(value).strip().upper()


def _clean_status(value: object) -> str:
    return str(value).strip().upper()


def _clean_merchant(value: object) -> str:
    cleaned = str(value).strip()
    if cleaned in MERCHANT_BLACKLIST:
        return ""
    return cleaned


class CsvCleaner:
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Cleaning started: %d rows", len(df))

        df = df.copy()

        df = df.dropna(how="all")

        if "date" in df.columns:
            df["date"] = df["date"].apply(_parse_date)

        if "amount" in df.columns:
            df["amount"] = df["amount"].apply(_clean_amount)

        if "currency" in df.columns:
            df["currency"] = df["currency"].apply(_clean_currency)

        if "status" in df.columns:
            df["status"] = df["status"].apply(_clean_status)

        if "merchant" in df.columns:
            df["merchant"] = df["merchant"].apply(_clean_merchant)

        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].apply(
                    lambda x: str(x).strip() if pd.notna(x) else x
                )

        if "category" in df.columns:
            df["category"] = df["category"].fillna("Uncategorised")
            df["category"] = df["category"].replace("", "Uncategorised")

        if "txn_id" in df.columns:
            df["txn_id"] = df["txn_id"].fillna("")

        df = df.drop_duplicates()

        df = df.reset_index(drop=True)

        logger.info("Cleaning finished: %d rows after dedup", len(df))
        return df
