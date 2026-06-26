# Scaling Jetfire to 100× Load

## Current Bottlenecks

### PostgreSQL Writes

The current architecture performs bulk inserts of transactions in a single commit within the Celery worker. At 100× load (thousands of jobs per minute), a single Postgres instance becomes a write bottleneck.

**Trade-off**: Write-ahead log (WAL) pressure, MVCC bloat from frequent large commits.

### Redis Queue

Celery with Redis broker has reliable but limited throughput. Redis is single-threaded for commands; at high task enqueue rates, it becomes a bottleneck.

### Polling Endpoints

`GET /jobs/{id}/status` and `GET /jobs/{id}/results` are client-polled. At scale, this creates unnecessary load when clients poll frequently. It also introduces latency — the client only learns about completion on the next poll cycle.

### Pandas Memory Usage

Pandas loads the entire CSV into memory. At 100×, a 500 MB CSV requires 2-5 GB of DataFrame memory (Pandas overhead). This limits how large a single file the worker can process.

### LLM Rate Limits

Groq API has rate limits (requests per minute, tokens per minute). Batching uncategorised rows into one request helps, but at scale, many concurrent jobs will hit rate limits, causing retries and degraded service.

## Scaling Strategies

### Horizontal FastAPI Scaling

**Approach**: Run multiple FastAPI replicas behind a load balancer (e.g., nginx, Cloudflare, or AWS ALB).

**Considerations**:
- FastAPI is stateless by design — no session affinity needed
- Each replica reads `.env` or environment variables
- Database connection pools must be sized per-replica (total connections = replicas × pool_size)
- Recommended: 3-5 replicas initially, then auto-scale based on CPU/memory

### Object Storage (Already Implemented)

Jetfire already uses MinIO (S3-compatible object storage) instead of local disk uploads.

```
Client → FastAPI → Upload to S3 → Job record with S3 URL
  Celery Worker → Download from S3 → Process → Delete from S3
```

This enables stateless FastAPI replicas and decoupled workers without shared filesystem requirements. The bucket is auto-created on startup via `ensure_bucket()`, and temp files are cleaned up in `finally` blocks within Celery tasks.

**Trade-off**: Adds latency for upload + download, but is necessary for horizontal scaling.

### Read Replicas

**Approach**: Direct read queries (`GET /jobs`, `GET /jobs/{id}/results`) to a read replica of PostgreSQL.

**Implementation**:
- Two connection strings: `DATABASE_URL` (read-write), `DATABASE_URL_READER` (read-only)
- Repositories accept an optional `read_session` parameter
- Write-heavy operations (job creation, transaction inserts) hit the primary

**Trade-off**: Eventual consistency — a job may show as PENDING for a few milliseconds after completion on the primary.

### Partitioning

**Approach**: Partition the `transactions` table by `job_id` (or by `created_at` month).

```sql
CREATE TABLE transactions (
  ...
) PARTITION BY RANGE (created_at);
```

**Benefit**: 
- Query pruning — fetching results for one job scans only one partition
- Older partitions can be archived or deleted without vacuum
- Bulk inserts are isolated to a single partition

### Worker Autoscaling

**Approach**: Use Celery's dynamic queue features or Kubernetes HPA based on queue depth.

**Implementation**:
- Monitor Redis list length for the Celery queue
- Scale workers up when queue depth > threshold
- Scale workers down when queue depth = 0 for N minutes
- Set a minimum of 1 worker, maximum based on DB connection limits

### NATS JetStream vs Kafka

**Current**: Redis as Celery broker.

**At 100× scale**, Redis has limitations:
- No persistence guarantees (losing Redis loses queued tasks)
- Single-threaded command processing
- Memory-bound queue depth

| Feature | NATS JetStream | Kafka |
|---------|---------------|-------|
| Throughput | ~10M msg/s | ~1M msg/s |
| Latency | ~1ms | ~10ms |
| Persistence | Configurable | Durable by default |
| Operational Complexity | Medium | High |
| Exactly-Once | Yes (with KV store) | Yes |
| Celery Support | Third-party transport | Third-party transport |

**Recommendation**: NATS JetStream for the 100× scale. It offers lower latency, simpler operations, and sufficient throughput. Kafka is warranted when downstream consumers need replay from arbitrary offsets or when integrating with Kafka-native ecosystems (e.g., Kafka Connect, Debezium).

### Streaming CSV Processing

**Current**: Pandas loads entire CSV into memory.

**Alternative**: Process CSV row-by-row using Python's `csv` module or streaming parser (e.g., `pandas.read_csv(chunksize=1000)`).

```
for chunk in pd.read_csv(file, chunksize=5000):
    clean_chunk = cleaner.clean(chunk)
    anomaly_chunk = detector.detect(clean_chunk)
    buffer.extend(anomaly_chunk.to_dict('records'))
    if len(buffer) >= 10000:
        bulk_insert(buffer)
        buffer.clear()
```

**Benefit**:
- Process files larger than available RAM
- Begin inserting to DB before the entire file is read
- Reduce peak memory usage by 10-100×

**Trade-off**:
- Cannot deduplicate across chunks (duplicate rows in different chunks won't be removed)
- Streaming anomaly detection requires window-based or incremental algorithms instead of groupwise medians

### LLM Caching

**Approach**: Cache LLM classification results for merchant → category mappings.

```
Cache Key: merchant_name
Cache Value: category
TTL: 24 hours
```

**Implementation**: Use Redis as a cache layer. Before calling the LLM, check if the merchant has a cached category. After LLM response, store the mapping.

**Benefit**: Reduces LLM API calls by 60-80% for repeated merchants across different jobs.

### Dedicated Inference Service

**Approach**: Extract LLM calls into a standalone inference microservice with its own queue and rate limiting.

```
Celery Worker → Internal Queue → Inference Service → Groq API
```

**Benefit**:
- Separate scaling of compute (workers) from inference (LLM)
- Implement request coalescing — batch requests from multiple jobs into fewer LLM calls
- Circuit breaker for API failures
- Local caching layer

**Trade-off**: Additional service to deploy and monitor. Recommended only when LLM calls are the primary bottleneck.

### Observability

**Current**: Structured JSON logs with request IDs.

**At 100× scale**, add:

- **Distributed tracing**: OpenTelemetry instrumentation across FastAPI → Celery → DB → LLM
  - Trace context propagates via Celery headers
  - Enables end-to-end latency breakdown
- **Metrics** (Prometheus):
  - `jobs_uploaded_total`, `jobs_completed_total`, `jobs_failed_total`
  - `processing_duration_seconds` (histogram)
  - `transactions_processed_total`
  - `llm_call_duration_seconds`, `llm_errors_total`
  - `celery_queue_depth`
  - `db_connection_pool_usage`
- **Dashboards**: Grafana dashboard showing pipeline throughput, error rates, and latency percentiles (p50, p95, p99)

### Idempotency

**Current**: Duplicate upload of the same file creates a new job each time.

**At 100× scale**, implement idempotency keys:

- Client sends `Idempotency-Key` header (e.g., MD5 of the file)
- Server checks if a job with that key exists
- Returns existing job_id instead of creating a duplicate

**Implementation**: Add `idempotency_key` column to `jobs` table with a unique constraint.

### Rate Limiting

**Approach**: Protect the API from abuse at scale.

- **Per-client**: Token bucket based on API key or IP
- **Per-endpoint**: Stricter limits on `POST /jobs/upload` than `GET /jobs`
- **LLM rate limiting**: Queue-based throttling to stay within Groq API limits

**Implementation**: FastAPI middleware using `slowapi` or a Redis-based sliding window counter.
