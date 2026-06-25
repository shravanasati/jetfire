import json
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0
BACKOFF_MULTIPLIER = 2.0

CLASSIFICATION_SYSTEM_PROMPT = """You are a transaction categorizer. Given a list of transactions with merchant names, assign each one a category from the following list:

- Food
- Transport
- Shopping
- Utilities
- Entertainment
- Travel
- Cash Withdrawal
- Uncategorised

Return ONLY valid JSON as a list of objects with keys "txn_id" and "category". No explanation, no markdown."""

CLASSIFICATION_USER_PROMPT = "Transactions:\n{transactions}"

SUMMARY_SYSTEM_PROMPT = """You are a financial analyst. Given the following transaction data from a CSV upload, generate a JSON summary with these exact keys:

- total_spend_by_currency: dict of currency code to total amount
- top_3_merchants: list of strings
- anomaly_count: integer
- narrative: a 2-3 sentence summary of the findings
- risk_level: one of "low", "medium", "high"

Return ONLY valid JSON. No explanation, no markdown."""

SUMMARY_USER_PROMPT = """Transactions processed: {transaction_count}

Data:
Total by currency: {totals_by_currency}
Top merchants: {top_merchants}
Anomalies: {anomalies}"""


class LlmService:
    def __init__(self) -> None:
        self._model: ChatOpenAI | None = None

    def _get_model(self) -> ChatOpenAI | None:
        if self._model is not None:
            return self._model
        if not settings.groq_api_key:
            return None
        self._model = ChatOpenAI(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            temperature=0.1,
        )
        return self._model

    def classify_categories(
        self, uncategorised_rows: list[dict]
    ) -> dict[str, str] | None:
        if not uncategorised_rows:
            return {}

        model = self._get_model()
        if model is None:
            logger.warning("No GROQ_API_KEY set; skipping classification")
            return None

        rows_text = "\n".join(
            f'- txn_id: {r["txn_id"] or "N/A"}, merchant: {r["merchant"]}'
            for r in uncategorised_rows
        )

        messages = [
            SystemMessage(content=CLASSIFICATION_SYSTEM_PROMPT),
            HumanMessage(
                content=CLASSIFICATION_USER_PROMPT.format(
                    transactions=rows_text
                )
            ),
        ]

        for attempt in range(MAX_RETRIES):
            try:
                response = model.invoke(messages)
                raw = response.content.strip()
                raw = _strip_markdown(raw)
                parsed = json.loads(raw)
                if not isinstance(parsed, list):
                    raise ValueError("Response is not a list")
                result: dict[str, str] = {}
                for item in parsed:
                    txn_id = item.get("txn_id", "")
                    category = item.get("category", "Uncategorised")
                    if txn_id:
                        result[txn_id] = category
                return result
            except Exception as e:
                logger.warning(
                    "LLM classification attempt %d failed: %s",
                    attempt + 1,
                    e,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(
                        INITIAL_BACKOFF * (BACKOFF_MULTIPLIER**attempt)
                    )

        return None

    def generate_summary(
        self,
        transaction_count: int,
        totals_by_currency: dict[str, float],
        top_merchants: list[tuple[str, float]],
        anomalies: int,
    ) -> dict | None:
        model = self._get_model()
        if model is None:
            return None

        merchants_str = ", ".join(
            f"{m}: {t:.2f}" for m, t in top_merchants
        )
        totals_str = json.dumps(totals_by_currency)

        messages = [
            SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
            HumanMessage(
                content=SUMMARY_USER_PROMPT.format(
                    transaction_count=transaction_count,
                    totals_by_currency=totals_str,
                    top_merchants=merchants_str,
                    anomalies=anomalies,
                )
            ),
        ]

        for attempt in range(MAX_RETRIES):
            try:
                response = model.invoke(messages)
                raw = response.content.strip()
                raw = _strip_markdown(raw)
                parsed = json.loads(raw)
                return parsed
            except Exception as e:
                logger.warning(
                    "LLM summary attempt %d failed: %s", attempt + 1, e
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(
                        INITIAL_BACKOFF * (BACKOFF_MULTIPLIER**attempt)
                    )

        return None


def _strip_markdown(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
