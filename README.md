# TenantMind AI

TenantMind AI is a portfolio-grade, multi-tenant retrieval-augmented generation (RAG) workspace. Teams upload internal documents and receive evidence-grounded answers with page-aware citations, semantic similarity scores, and an auditable activity trail.

This is an independent demonstration project. It contains no client data or proprietary client code.

## Product capabilities

- JWT authentication with workspace identity embedded in every access token
- Tenant-scoped documents, vector chunks, retrieval queries, and audit events
- PDF, TXT, and Markdown ingestion with extraction, overlapping chunking, and embeddings
- PostgreSQL + pgvector semantic search in Docker
- SQLite and deterministic local embeddings for zero-cost development
- Optional OpenAI embeddings and grounded answer generation
- Page-aware citations and similarity scores
- Usage dashboard and workspace audit activity
- Typed FastAPI API with interactive OpenAPI documentation
- Responsive Next.js 16 dashboard
- Automated tests for authentication, retrieval, upload, and tenant isolation

## Architecture

```text
Browser / Next.js 16
        |
        | Bearer JWT + REST
        v
FastAPI application boundary
  |-- authentication and workspace claims
  |-- document extraction and chunking
  |-- embedding provider abstraction
  |-- tenant-scoped semantic retrieval
  |-- grounded answer generation
  |-- audit trail
        |
        +--> PostgreSQL metadata
        +--> pgvector embeddings
        +--> OpenAI API (optional)
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for decisions, threat boundaries, scaling considerations, and production recommendations.

## Run locally without API costs

The application works without an OpenAI key. It uses normalized deterministic embeddings and grounded extractive answers so the entire workflow can be evaluated locally.

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

API documentation: `http://localhost:8000/docs`

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Application: `http://localhost:3000`

Select **Enter live demo**, then load the sample knowledge or upload a PDF/TXT/Markdown file.

## Run the production-shaped stack

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Docker uses PostgreSQL 16 with the pgvector extension. Add `OPENAI_API_KEY` to `.env` to activate OpenAI embeddings and generated answers.

## Live deployment

The portfolio deployment uses three independently managed services:

- Vercel for the Next.js frontend (`frontend` project root)
- Render for the FastAPI Docker service (`render.yaml` blueprint)
- Neon for persistent PostgreSQL with the `vector` extension

Set `DATABASE_URL` on Render to the Neon pooled connection string and leave
`OPENAI_API_KEY` empty to use deterministic local embeddings. Set
`BACKEND_INTERNAL_URL` on Vercel to the public Render service URL. Secrets are
configured in the hosting dashboards and are never committed to this repository.

## Security model

Every protected request derives the workspace from a signed JWT. The API never accepts a client-provided workspace identifier. Every document, chunk, retrieval query, deletion, metric, and audit lookup is filtered by that authenticated workspace.

Passwords use salted PBKDF2-HMAC-SHA256 hashes. Production deployments should replace the demo JWT secret, use a managed identity provider, rotate signing keys, enforce rate limits, scan uploaded files, and place object storage behind short-lived signed URLs.

## Verification

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run build
npm audit --omit=dev
```

The test suite covers:

1. API health and versioning
2. Registration and JWT-protected access
3. Evidence retrieval with citations
4. Cross-workspace data isolation
5. File ingestion and dashboard metrics
6. Invalid-token rejection

## Portfolio talking points

- Designed one codebase for inexpensive local development and production pgvector retrieval.
- Kept authorization at the API boundary instead of trusting workspace IDs from the browser.
- Made LLM use optional and prevented unsupported answers when evidence is missing.
- Preserved citation metadata through extraction, chunking, retrieval, and response generation.
- Documented the next steps required for async ingestion, observability, and enterprise identity.
