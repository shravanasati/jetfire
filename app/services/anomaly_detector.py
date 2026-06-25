from collections.abc import Callable

import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

AnomalyRule = Callable[[pd.DataFrame], pd.Series]

USD_MERCHANT_BLACKLIST = frozenset({"Swiggy", "Ola", "IRCTC", "Zomato", "Flipkart"})


def _rule_amount_vs_median(df: pd.DataFrame) -> pd.Series:
    account_medians = df.groupby("account_id")["amount"].transform("median")
    return df["amount"] > 3 * account_medians.abs()


def _rule_usd_merchant(df: pd.DataFrame) -> pd.Series:
    return (df["currency"] == "USD") & df["merchant"].isin(
        USD_MERCHANT_BLACKLIST
    )


RULES: list[tuple[AnomalyRule, str]] = [
    (_rule_amount_vs_median, "amount exceeds 3x account median"),
    (_rule_usd_merchant, "USD transaction with restricted merchant"),
]


class AnomalyDetector:
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        combined_reason: pd.Series = pd.Series([""] * len(df), index=df.index)

        for rule_fn, reason in RULES:
            try:
                triggered = rule_fn(df)
                combined_reason[triggered] = (
                    combined_reason[triggered].str.rstrip("; ")
                    + f"; {reason}"
                ).str.lstrip("; ")
            except Exception:
                logger.exception("Anomaly rule failed: %s", reason)

        df["is_anomaly"] = combined_reason != ""
        df["anomaly_reason"] = combined_reason.replace("", None)

        anomaly_count = df["is_anomaly"].sum()
        logger.info(
            "Anomaly detection complete: %d anomalies found", anomaly_count
        )

        return df
