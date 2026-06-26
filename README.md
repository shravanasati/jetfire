# Jetfire

Transaction anomaly detection and classification service. Upload CSV transaction data and receive cleaned, anomaly-scored, and LLM-enriched results.

## Architecture

![architecture](./jetfire%20diagram.png)

### Components

- **FastAPI** — REST API for file upload, status polling, and result retrieval
- **PostgreSQL** — Primary data store for jobs, transactions, and summaries
- **Redis** — Celery message broker and result backend
- **Celery** — Async worker that executes the processing pipeline
- **Groq (LLaMA 3.3 70B)** — LLM for category classification and narrative summary via OpenAI-compatible API

### Processing Pipeline

```
Upload → Persist Job → Queue Task → Worker → Read CSV → Clean Data
→ Detect Anomalies → LLM Category Classification → LLM Summary
→ Persist Results → Mark Complete
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) A Groq API key for LLM features (get one at https://console.groq.com)

### Setup

```bash
# Clone the repository
git clone <repo-url> && cd jetfire

# (Optional) Add Groq API key
echo "GROQ_API_KEY=gsk_your_key_here" >> .env

# Start everything
docker compose up
```

The API will be available at `http://localhost:8000`.

### Verify

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/api/v1/jobs
# {"jobs":[]}
```

## API Reference

### Upload a CSV

```bash
curl -X POST http://localhost:8000/api/v1/jobs/upload \
  -F "file=@transactions.csv"
```

**Response** (201):
```json
{
  "job_id": "abc-123",
  "filename": "transactions.csv",
  "status": "PENDING",
  "message": "File uploaded successfully. Processing has been queued."
}
```

### Check Job Status

```bash
curl http://localhost:8000/api/v1/jobs/{job_id}/status
```

**Response** (200):
```json
{
  "id": "abc-123",
  "status": "COMPLETED",
  "row_count_raw": 95,
  "row_count_clean": 85,
  "created_at": "2026-06-25T...",
  "completed_at": "2026-06-25T..."
}
```

### Get Job Results

```bash
curl http://localhost:8000/api/v1/jobs/{job_id}/results
```

**Response** (200):
```json
{
  "job": { ... },
  "transactions": [ ... ],
  "summary": {
    "top_merchants": {"Amazon": 50000, "Flipkart": 45000},
    "total_spend_inr": 95000.0,
    "total_spend_usd": 5000.0,
    "anomaly_count": 3,
    "narrative": "...",
    "risk_level": "medium"
  }
}
```

### List All Jobs

```bash
curl http://localhost:8000/api/v1/jobs
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Design Decisions

### Why Celery + Redis instead of a message queue?

For the initial scope (single worker, moderate throughput), Celery with Redis provides the simplest operational model. The same Redis instance serves as both broker and result backend, eliminating infrastructure overhead. As scale demands grow, the architecture supports swapping in NATS JetStream or Kafka without changing application code.

### Why sync SQLAlchemy instead of async?

Celery does not natively support async execution. Using sync SQLAlchemy throughout avoids dual session management (async for FastAPI, sync for workers) and keeps the codebase uniform. FastAPI's sync endpoints handle this transparently via thread pool execution.

### Why bulk inserts?

Processing thousands of transactions row-by-row creates N+1 database round trips. Bulk inserts (`session.add_all()`) batch everything into a single commit, reducing write latency by orders of magnitude.

### Why Pandas for CSV processing?

Pandas provides vectorised operations (string normalization, groupby for medians, deduplication) that are faster and more concise than manual row iteration. The DataFrame is ephemeral — it exists only during the worker's lifetime and is garbage collected after persistence.

### Why "llm_failed" instead of failing the job?

LLM APIs can be unavailable, rate-limited, or return malformed responses. Setting `llm_failed=True` on affected rows ensures the job completes with partial results rather than failing entirely. The client can inspect `llm_failed` to understand data quality.

## Assumptions

1. **Date formats**: The cleaner handles DD-MM-YYYY, YYYY/MM/DD, and YYYY-MM-DD. Other formats are passed through with a warning.
2. **Currency**: Only INR and USD are explicitly tracked in the summary. Other currencies appear in `total_spend_by_currency` from the LLM.
3. **Duplicate detection**: Rows with identical values across all columns are considered duplicates. Duplicate `txn_id` values with different data are not removed.
4. **Missing data**: Rows with all-empty values are dropped. Missing categories become "Uncategorised". Missing transaction IDs become empty strings.
5. **LLM availability**: The service degrades gracefully when the Groq API is unavailable or not configured. Summary statistics are computed from the data directly, and the LLM only enriches with narrative.

## Scaling Considerations

See [SCALING.md](SCALING.md) for a detailed discussion of bottlenecks, trade-offs, and strategies for scaling to 100× the current load.
