from sqlalchemy.orm import Session

from app.db.models.job import Job


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, filename: str) -> Job:
        job = Job(filename=filename)
        self.session.add(job)
        self.session.commit()
        return job

    def get_by_id(self, job_id: str) -> Job | None:
        return self.session.query(Job).filter(Job.id == job_id).first()

    def list_all(self) -> list[Job]:
        return (
            self.session.query(Job)
            .order_by(Job.created_at.desc())
            .all()
        )

    def update_status(
        self,
        job_id: str,
        status: str,
        row_count_raw: int | None = None,
        row_count_clean: int | None = None,
        completed_at: object | None = None,
        error_message: str | None = None,
    ) -> Job | None:
        job = self.get_by_id(job_id)
        if not job:
            return None
        job.status = status
        if row_count_raw is not None:
            job.row_count_raw = row_count_raw
        if row_count_clean is not None:
            job.row_count_clean = row_count_clean
        if completed_at is not None:
            job.completed_at = completed_at
        if error_message is not None:
            job.error_message = error_message
        self.session.commit()
        return job
