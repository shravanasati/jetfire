from sqlalchemy.orm import Session

from app.db.models.summary import JobSummary


class SummaryRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, summary: JobSummary) -> JobSummary:
        self.session.add(summary)
        self.session.commit()
        return summary

    def get_by_job_id(self, job_id: str) -> JobSummary | None:
        return (
            self.session.query(JobSummary)
            .filter(JobSummary.job_id == job_id)
            .first()
        )
