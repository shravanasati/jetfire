from app.core.logging import get_logger
from app.db.models.summary import JobSummary

logger = get_logger(__name__)


class SummaryService:
    def build_summary(
        self,
        llm_summary: dict | None,
        total_spend_inr: float,
        total_spend_usd: float,
        anomaly_count: int,
        top_merchants: list[tuple[str, float]],
    ) -> JobSummary:
        top_merchants_dict = {
            merchant: round(amount, 2) for merchant, amount in top_merchants[:3]
        }

        if llm_summary:
            risk_level = llm_summary.get("risk_level", "low")
            narrative = llm_summary.get("narrative", "")
        else:
            risk_level = self._calculate_risk_level(
                anomaly_count, len(top_merchants)
            )
            narrative = self._generate_fallback_narrative(
                total_spend_inr, total_spend_usd, anomaly_count
            )

        summary = JobSummary(
            top_merchants=top_merchants_dict,
            total_spend_inr=round(total_spend_inr, 2),
            total_spend_usd=round(total_spend_usd, 2),
            anomaly_count=anomaly_count,
            narrative=narrative,
            risk_level=risk_level,
        )

        logger.info(
            "Summary generated: spend_inr=%.2f spend_usd=%.2f anomalies=%d risk=%s",
            total_spend_inr,
            total_spend_usd,
            anomaly_count,
            risk_level,
        )

        return summary

    def _calculate_risk_level(
        self, anomaly_count: int, total_merchants: int
    ) -> str:
        if anomaly_count > 10:
            return "high"
        if anomaly_count > 3:
            return "medium"
        return "low"

    def _generate_fallback_narrative(
        self, total_spend_inr: float, total_spend_usd: float, anomaly_count: int
    ) -> str:
        return (
            f"Processed transactions totalling INR {total_spend_inr:.2f} "
            f"and USD {total_spend_usd:.2f}. "
            f"Found {anomaly_count} anomalous transactions."
        )
