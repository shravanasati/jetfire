from datetime import datetime, timezone
from pathlib import Path

from app.core.celery import celery_app

app = celery_app
from app.core.logging import get_logger
from app.db.session import SessionFactory
from app.repositories.job_repository import JobRepository
from app.services.transaction_service import (
    TransactionProcessingService,
)
from app.utils.s3 import delete_object, download_to_temp

logger = get_logger(__name__)


def _fail_job(job_id: str, error_message: str) -> None:
    session = SessionFactory()
    try:
        repo = JobRepository(session)
        job = repo.get_by_id(job_id)
        if job and job.status not in ("COMPLETED", "FAILED"):
            repo.update_status(
                job_id,
                status="FAILED",
                error_message=error_message,
                completed_at=datetime.now(timezone.utc),
            )
    except Exception:
        logger.exception("Failed to mark job %s as FAILED", job_id)
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=1, acks_late=True)
def process_transactions(
    self, job_id: str, object_key: str
) -> dict[str, object]:
    logger.info(
        "Task received: job_id=%s, object_key=%s", job_id, object_key
    )

    filepath = None
    try:
        filepath = download_to_temp(object_key)
        service = TransactionProcessingService()
        service.process(job_id, filepath)
        return {"job_id": job_id, "status": "COMPLETED"}
    except Exception as exc:
        logger.exception(
            "Task failed for job_id=%s: %s", job_id, exc
        )
        _fail_job(job_id, f"Worker error: {exc}")
        raise
    finally:
        if filepath:
            Path(filepath).unlink(missing_ok=True)
        try:
            delete_object(object_key)
        except Exception:
            logger.warning("Failed to clean up S3 object: %s", object_key)
