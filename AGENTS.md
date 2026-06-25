# AGENTS.md — Jetfire

## Stack

- FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, Redis, Celery, Pandas
- LangChain (OpenAI-compatible) → Groq API for LLM inference
- boto3 → MinIO (S3-compatible) for file storage
- Docker Compose for local dev

## Project Structure

```
app/
├── api/           # Thin FastAPI routes
├── core/          # Config, logging, celery app
├── db/            # Session, Base, models/
├── repositories/  # Data access layer
├── schemas/       # Pydantic response models
├── services/      # Business logic
├── utils/         # S3 client
├── workers/       # Celery tasks
└── main.py
```

## Conventions

- Type hints everywhere, no `Any` unless unavoidable
- Services for business logic, repositories for persistence
- Routes are thin — validate input, call service, return response
- Docstrings on public functions
- <100 lines per function
- Dependency injection via constructor (`service: Service | None = None`)

## Key Patterns

- **Services** accept optional dependencies for testability
- **Repositories** wrap all DB queries, accept `Session` in constructor
- **Celery tasks** orchestrate but delegate to services
- **LLM failures** never fail the job — set `llm_failed=True` and continue
- **Bulk inserts** via `session.add_all()`, never one row at a time

## LLM / Groq

- Settings: `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_BASE_URL`
- Service: `app/services/llm_service.py` — LangChain `ChatOpenAI` with Groq base URL
- Retry 3× with exponential backoff on failures
- Responses parsed as JSON, markdown fences stripped before parsing
- No API key → graceful degradation (None returned, handled by caller)

## S3 / MinIO

- Settings: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`
- Utility: `app/utils/s3.py`
- API uploads to S3 → Celery task downloads to temp file → temp file cleaned up in `finally`
- Bucket auto-created on app startup via `ensure_bucket()`

## Error Handling

- Exceptions in workers → job marked `FAILED` with error message
- No stack traces exposed to API clients (500 → `{"detail": "An internal error occurred"}`)
- `service.process()` catches and re-raises; task `except` block catches and marks FAILED via `_fail_job()`

## Docker

- `docker compose up` starts everything
- Non-root `appuser` (UID 1000) runs both FastAPI and Celery
- Named volumes: `postgres_data`, `minio_data`

## Tests

- `pytest tests/` for cleaning and anomaly detection unit tests
- No external dependencies needed (no DB, no S3, no LLM)

## Config

- `app/core/config.py` extends `BaseSettings`, reads from `.env` / environment
- `.env.example` as template — `.env` is gitignored
