from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    status: str
    row_count_raw: int
    row_count_clean: int
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    row_count_raw: int
    row_count_clean: int
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class JobListResponse(BaseModel):
    jobs: list[JobResponse]


class UploadResponse(BaseModel):
    job_id: str
    filename: str
    status: str = "PENDING"
    message: str = "File uploaded successfully. Processing has been queued."
