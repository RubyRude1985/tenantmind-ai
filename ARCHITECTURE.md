# Architecture and production review

## Design goals

TenantMind is designed to demonstrate a credible early-stage AI SaaS architecture rather than only an LLM prompt wrapper. The primary concerns are tenant isolation, traceable answers, replaceable AI providers, and a clear path from local development to production.

## Request and trust boundaries

1. A user authenticates and receives a signed JWT containing user and workspace claims.
2. The browser sends the token to the FastAPI boundary.
3. The API verifies the signature and loads the user from the database.
4. Repository queries always filter using the verified workspace claim.
5. Uploaded content is converted to chunks and embeddings inside that workspace.
6. Retrieval can only search chunks belonging to the authenticated workspace.
7. Answers contain citations created from the exact retrieved chunks.

The API intentionally does not accept `workspace_id` from protected request bodies or headers.

## Ingestion pipeline

```text
Upload -> size/type validation -> text extraction -> page preservation
       -> whitespace normalization -> overlapping chunks
       -> embeddings -> tenant-scoped vector index -> ready document
```

The synchronous implementation keeps the demo easy to run. At production volume, extraction and embedding should move to an idempotent background worker using a queue. The document state should transition through `uploaded`, `processing`, `ready`, and `failed` states.

## Retrieval and grounding

Docker deployments use pgvector cosine distance. Local development uses the same 1,536-dimensional interface with deterministic normalized embeddings, avoiding API costs while keeping tests repeatable.

When an OpenAI key is present:

- ingestion uses `text-embedding-3-small`;
- retrieval returns the highest-scoring tenant-scoped chunks;
- the Responses API receives only those chunks;
- system instructions prohibit unsupported answers and require citations.

## Data model

- `Workspace`: tenant boundary
- `User`: identity belonging to one workspace
- `Document`: source metadata and ingestion status
- `DocumentChunk`: page-aware content plus vector embedding
- `AuditEvent`: user-attributed operational history

## Production risks and mitigations

| Risk | Current control | Production recommendation |
|---|---|---|
| Cross-tenant access | JWT-derived workspace filters | Add PostgreSQL row-level security and automated policy tests |
| Malicious upload | Type and size limits | Add malware scanning, object storage, and sandboxed extraction |
| Prompt injection in documents | Evidence-only instructions | Add content classification, instruction stripping, and evaluation suites |
| Expensive ingestion | Bounded file size | Queue jobs, deduplicate by content hash, batch embeddings |
| Token theft | Expiring signed JWT | Use managed OIDC, secure cookies, refresh-token rotation |
| Hallucination | Evidence threshold and citations | Add answerability classification and citation faithfulness evaluations |
| Operational failure | Health endpoint and audit events | Add structured logs, tracing, metrics, alerting, and dead-letter queues |

## Scaling path

1. Store original files in S3-compatible object storage.
2. Run extraction and embedding through background workers.
3. Add connection pooling and database migrations.
4. Add HNSW pgvector indexes after measuring corpus and query patterns.
5. Cache repeated retrieval queries per workspace.
6. Stream answers and record token/cost metrics.
7. Add automated RAG evaluations for recall, groundedness, and citation accuracy.

## Deliberate scope limits

The demo does not claim production certification. It omits billing, enterprise SSO, malware scanning, OCR for image-only PDFs, background queues, and cloud deployment. These are explicitly documented so the project demonstrates sound engineering judgment instead of hiding operational risks.
