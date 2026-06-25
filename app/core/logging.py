import json
import logging
import sys
import uuid
from contextvars import ContextVar
from logging import LogRecord

request_id_var: ContextVar[str] = ContextVar("request_id", default="N/A")


class StructuredFormatter(logging.Formatter):
    def format(self, record: LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    for logger_name in ("uvicorn", "uvicorn.access", "celery"):
        logging.getLogger(logger_name).handlers.clear()
        logging.getLogger(logger_name).addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
