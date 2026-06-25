from pydantic import BaseModel, ConfigDict


class SummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    top_merchants: dict
    total_spend_inr: float
    total_spend_usd: float
    anomaly_count: int
    narrative: str | None = None
    risk_level: str
