from sqlalchemy.orm import Session

from app.db.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, session: Session):
        self.session = session

    def bulk_insert(self, transactions: list[Transaction]) -> None:
        self.session.add_all(transactions)
        self.session.commit()

    def get_by_job_id(self, job_id: str) -> list[Transaction]:
        return (
            self.session.query(Transaction)
            .filter(Transaction.job_id == job_id)
            .all()
        )
