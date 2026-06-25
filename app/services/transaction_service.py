import pandas as pd

from app.core.logging import get_logger
from app.db.models.transaction import Transaction
from app.db.session import SessionFactory
from app.repositories.job_repository import JobRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.anomaly_detector import AnomalyDetector
from app.services.csv_cleaner import CsvCleaner
from app.services.llm_service import LlmService
from app.services.summary_service import SummaryService

logger = get_logger(__name__)

REQUIRED_COLUMNS = {
    "date",
    "merchant",
    "amount",
    "currency",
    "status",
}


class TransactionProcessingService:
    def __init__(
        self,
        csv_cleaner: CsvCleaner | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        llm_service: LlmService | None = None,
        summary_service: SummaryService | None = None,
    ) -> None:
        self.csv_cleaner = csv_cleaner or CsvCleaner()
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.llm_service = llm_service or LlmService()
        self.summary_service = summary_service or SummaryService()

    def process(self, job_id: str, filepath: str) -> None:
        session = SessionFactory()
        try:
            job_repo = JobRepository(session)
            txn_repo = TransactionRepository(session)
            summary_repo = SummaryRepository(session)

            logger.info("Job started", extra={"job_id": job_id})

            job_repo.update_status(job_id, status="PROCESSING")

            logger.info("Reading CSV: %s", filepath)
            df = pd.read_csv(filepath)
            raw_count = len(df)

            missing_cols = REQUIRED_COLUMNS - set(df.columns)
            if missing_cols:
                error_msg = f"Missing required columns: {missing_cols}"
                logger.error(error_msg)
                job_repo.update_status(
                    job_id,
                    status="FAILED",
                    row_count_raw=raw_count,
                    error_message=error_msg,
                )
                return

            df = self.csv_cleaner.clean(df)
            clean_count = len(df)

            logger.info("Cleaning finished: %d rows", clean_count)

            df = self.anomaly_detector.detect(df)

            df["llm_failed"] = False

            uncategorised = df[df["category"] == "Uncategorised"]
            if not uncategorised.empty:
                logger.info(
                    "LLM classification started for %d rows",
                    len(uncategorised),
                )
                rows_for_llm = uncategorised[
                    ["txn_id", "merchant"]
                ].to_dict("records")
                category_map = self.llm_service.classify_categories(
                    rows_for_llm
                )

                if category_map is None:
                    logger.warning(
                        "LLM classification failed after all retries"
                    )
                    df.loc[
                        df["category"] == "Uncategorised", "llm_failed"
                    ] = True
                else:
                    for idx, row in df[
                        df["category"] == "Uncategorised"
                    ].iterrows():
                        txn_id = row.get("txn_id", "")
                        if txn_id in category_map:
                            df.at[idx, "category"] = category_map[txn_id]
                            df.at[idx, "llm_failed"] = False
                        else:
                            df.at[idx, "llm_failed"] = True
                    successful = sum(
                        1
                        for txn_id in category_map
                        if txn_id
                        and txn_id
                        in df[df["category"] != "Uncategorised"][
                            "txn_id"
                        ].values
                    )
                    logger.info(
                        "LLM classification finished: %d categorized",
                        successful,
                    )
            else:
                df["llm_failed"] = False

            logger.info("Summary generation started")

            totals = df.groupby("currency")["amount"].sum().to_dict()
            merchant_totals = (
                df.groupby("merchant")["amount"].sum()
                .sort_values(ascending=False)
                .head(10)
            )
            top_merchants = list(merchant_totals.items())
            anomaly_count = int(df["is_anomaly"].sum())

            llm_summary = self.llm_service.generate_summary(
                transaction_count=clean_count,
                totals_by_currency=totals,
                top_merchants=top_merchants,
                anomalies=anomaly_count,
            )

            summary = self.summary_service.build_summary(
                llm_summary=llm_summary,
                total_spend_inr=totals.get("INR", 0),
                total_spend_usd=totals.get("USD", 0),
                anomaly_count=anomaly_count,
                top_merchants=top_merchants,
            )
            summary.job_id = job_id

            transactions = [
                Transaction(
                    job_id=job_id,
                    txn_id=row.get("txn_id") or "",
                    date=str(row["date"]),
                    merchant=str(row["merchant"]),
                    amount=float(row["amount"]),
                    currency=str(row["currency"]),
                    status=str(row["status"]),
                    category=str(row["category"]),
                    account_id=str(row["account_id"]),
                    is_anomaly=bool(row["is_anomaly"]),
                    anomaly_reason=(
                        str(row["anomaly_reason"])
                        if pd.notna(row.get("anomaly_reason"))
                        else None
                    ),
                    llm_failed=bool(row.get("llm_failed", False)),
                )
                for _, row in df.iterrows()
            ]

            txn_repo.bulk_insert(transactions)
            summary_repo.create(summary)

            from datetime import datetime, timezone

            job_repo.update_status(
                job_id,
                status="COMPLETED",
                row_count_raw=raw_count,
                row_count_clean=clean_count,
                completed_at=datetime.now(timezone.utc),
            )

            logger.info("Job completed", extra={"job_id": job_id})

        except Exception:
            logger.exception("Job failed: %s", job_id)
            try:
                job_repo.update_status(
                    job_id, status="FAILED", error_message="Internal processing error"
                )
            except Exception:
                logger.exception(
                    "Failed to update job status to FAILED"
                )
            raise
        finally:
            session.close()
