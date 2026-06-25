from app.schemas.job import JobResponse
from app.schemas.summary import SummaryResponse
from app.schemas.transaction import TransactionResponse
from pydantic import BaseModel


class JobResultResponse(BaseModel):
    job: JobResponse
    transactions: list[TransactionResponse]
    summary: SummaryResponse | None = None
