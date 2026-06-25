from datetime import date

from pydantic import BaseModel, ConfigDict


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    txn_id: str | None = None
    date: date
    merchant: str
    amount: float
    currency: str
    status: str
    category: str
    account_id: str
    is_anomaly: bool
    anomaly_reason: str | None = None
    llm_failed: bool = False
