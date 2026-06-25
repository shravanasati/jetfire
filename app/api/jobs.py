from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.logging import get_logger
from app.db.session import get_session
from app.repositories.job_repository import JobRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.job import (
    JobListResponse,
    JobResponse,
    JobStatusResponse,
    UploadResponse,
)
from app.schemas.result import JobResultResponse
from app.schemas.summary import SummaryResponse
from app.schemas.transaction import TransactionResponse
from app.utils.s3 import delete_object, upload_fileobj

router = APIRouter(tags=["jobs"])
logger = get_logger(__name__)


@router.post(
    "/jobs/upload",
    response_model=UploadResponse,
    status_code=201,
    summary="Upload a CSV file for processing",
)
async def upload_job(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400, detail="Only CSV files are accepted"
        )

    session = next(get_session())
    try:
        job_repo = JobRepository(session)
        job = job_repo.create(filename=file.filename)

        object_key = f"uploads/{job.id}.csv"
        content = await file.read()
        upload_fileobj(content, object_key)

        from app.workers.tasks import process_transactions

        process_transactions.delay(job.id, object_key)

        logger.info(
            "File uploaded to S3: %s, job_id=%s, key=%s",
            file.filename, job.id, object_key,
        )

        return UploadResponse(
            job_id=job.id,
            filename=file.filename,
            status=job.status,
        )
    except Exception:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail="Upload failed")
    finally:
        session.close()


@router.get(
    "/jobs/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Get job processing status",
)
def get_job_status(job_id: str) -> JobStatusResponse:
    session = next(get_session())
    try:
        job_repo = JobRepository(session)
        job = job_repo.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobStatusResponse.model_validate(job)
    finally:
        session.close()


@router.get(
    "/jobs/{job_id}/results",
    response_model=JobResultResponse,
    summary="Get job results including transactions and summary",
)
def get_job_results(job_id: str) -> JobResultResponse:
    session = next(get_session())
    try:
        job_repo = JobRepository(session)
        txn_repo = TransactionRepository(session)
        summary_repo = SummaryRepository(session)

        job = job_repo.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        transactions = txn_repo.get_by_job_id(job_id)
        summary = summary_repo.get_by_job_id(job_id)

        return JobResultResponse(
            job=JobResponse.model_validate(job),
            transactions=[
                TransactionResponse.model_validate(t)
                for t in transactions
            ],
            summary=(
                SummaryResponse.model_validate(summary)
                if summary
                else None
            ),
        )
    finally:
        session.close()


@router.get(
    "/jobs",
    response_model=JobListResponse,
    summary="List all jobs",
)
def list_jobs() -> JobListResponse:
    session = next(get_session())
    try:
        job_repo = JobRepository(session)
        jobs = job_repo.list_all()
        return JobListResponse(
            jobs=[JobResponse.model_validate(j) for j in jobs]
        )
    finally:
        session.close()
