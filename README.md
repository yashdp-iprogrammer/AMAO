# AMAO — Adaptive Multi-Agent Orchestration

A **config-driven** multi-agent AI backend that accepts natural language queries, intelligently distributes them across SQL, NoSQL, and RAG agents, and synthesises all results into a single coherent answer — powered by a LangGraph orchestration pipeline, served via FastAPI with a Streamlit frontend. The agent registry is extensible, allowing new agent types to be added as your requirements grow.

The key principle: **every client gets exactly the agents they need, nothing more.** Agent availability, database connections, LLM models, and vector store backends are all defined per-client in a single `config.yaml` file.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Agents](#agents)
- [Core Pipeline](#core-pipeline)
- [Vector Store & RAG](#vector-store--rag)
- [Database Layer](#database-layer)
- [API Reference](#api-reference)
- [Frontend](#frontend)
- [Roles & Access Control](#roles--access-control)
- [Client Configuration](#client-configuration)
- [Environment Setup](#environment-setup)
- [Getting Started](#getting-started)
- [Tech Stack](#tech-stack)

---

## Overview

AMAO accepts natural language queries and intelligently routes them across three agent types:

- **SQL Agent** — Generates and executes `SELECT` queries against relational databases (MySQL, PostgreSQL, SQLite, MariaDB, MSSQL)
- **NoSQL Agent** — Queries document databases (MongoDB)
- **RAG Agent** — Retrieves answers from uploaded PDFs and text files using vector similarity search

Each client organisation has its own isolated configuration: which agents are active, which databases they connect to, which LLM model they use, and which vector store backend holds their documents. Two clients can run entirely different agent combinations on the same deployment.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Streamlit Frontend                  │
│         (Login · Chat · Super Admin Dashboard)       │
└───────────────────────┬──────────────────────────────┘
                        │ HTTP (JWT Bearer)
                        ▼
┌──────────────────────────────────────────────────────┐
│                  FastAPI Backend                     │
│                  POST /chat                          │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│           GraphManager (per-client cache)            │
│   Reads config.yaml → builds Orchestrator once       │
│   Holds LLMFactory + VLLMRuntimeManager instances    │
│   Pre-warms target client graph on startup           │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│            Orchestrator  (LangGraph graph)           │
│                                                      │
│  router_node                                         │
│    └─► LLM decides which agents to run + sub-queries │
│                                                      │
│  agent nodes  (only enabled agents exist as nodes)   │
│    ├─► sql_agent   → async parallel SQL execution    │
│    ├─► nosql_agent → MongoDB query execution         │
│    └─► rag_agent   → vector similarity retrieval     │
│                                                      │
│  final_node                                          │
│    └─► LLM synthesises all results → final_response  │
└──────────────────────────────────────────────────────┘
```

---

## How It Works

1. **User sends a query** via the Streamlit chat or directly to `POST /chat`.
2. **JWT is validated** — user's `client_id` is extracted from the token.
3. **GraphManager** checks its cache. If no orchestrator exists for this client, it reads `config.yaml`, builds the agent graph, and caches it.
4. **Router node** — an LLM receives the user query and the list of available agents (from config) and returns a JSON execution plan: which agents to run and with what sub-query.
5. **Agent nodes execute sequentially** in the order specified by the plan. Each agent appends its results to the shared state (`sql_agent_results`, `rag_agent_results`, etc.).
6. **Final node** — another LLM call synthesises all agent results into a single coherent answer.
7. **Response** is returned as `{ "final_response": "..." }`.

If files are uploaded alongside the query, they are chunked and indexed into the client's vector store before the query is processed.

---

## Project Structure

```
.
├── app.py                          # Streamlit frontend (with SuperAdmin UI)
├── main.py                         # FastAPI app: routers, middleware, DB init, seeding
├── pyproject.toml                  # Dependencies (uv)
│
├── src/
│   ├── agents/
│   │   ├── base.py                 # Abstract BaseAgent (name, config, run())
│   │   ├── sql_agent.py            # SQL agent with schema cache + parallel execution
│   │   ├── nosql_agent.py          # NoSQL / MongoDB agent
│   │   └── rag_agent.py            # RAG agent with multi-intent decomposition
│   │
│   ├── api/routes/
│   │   ├── chat/__init__.py        # POST /chat — main query endpoint
│   │   ├── auth/__init__.py        # /login /register /refresh /logout /get-current-user
│   │   ├── clients/__init__.py     # Client CRUD + atomic config creation
│   │   ├── config/__init__.py      # Config management
│   │   ├── agents/__init__.py      # Agent management
│   │   ├── models/__init__.py      # LLM model management
│   │   ├── user/__init__.py        # User management
│   │   ├── feedback/__init__.py    # User feedback
│   │   └── logs/__init__.py        # Log access
│   │
│   ├── core/
│   │   ├── orchestrator.py         # LangGraph graph: router → agents → final
│   │   ├── graph_manager.py        # Per-client orchestrator cache (async-safe)
│   │   ├── agent_factory.py        # Instantiates agents from config
│   │   ├── llm_factory.py          # Creates LLM clients via provider registry
│   │   ├── llm_providers/          # One class per LLM provider
│   │   │   ├── base.py             # BaseProvider interface (create())
│   │   │   ├── registry.py         # Maps provider name → provider instance
│   │   │   ├── openai_provider.py  # ChatOpenAI wrapper
│   │   │   ├── groq_provider.py    # ChatGroq wrapper
│   │   │   ├── google_provider.py  # ChatGoogleGenerativeAI wrapper
│   │   │   └── self_hosted_provider.py  # vLLM via ChatOpenAI + dynamic base_url
│   │   ├── llm_factory_utils/      # vLLM runtime support
│   │   │   ├── port_allocator.py   # Assigns free ports to self-hosted models
│   │   │   └── runtime_manager.py  # Starts/stops vLLM processes
│   │   ├── registry.py             # Maps agent names → agent classes
│   │   └── state_manager.py        # AgentState TypedDict definition
│   │
│   ├── configs/                    # Per-client YAML files (one folder per client UUID)
│   │   └── client_id_<uuid>/
│   │       └── config.yaml
│   │
│   ├── Database/
│   │   ├── base_db.py              # Async SQLAlchemy engine + session wrapper
│   │   ├── connection_factory.py   # Registry-pattern factory for SQL + MongoDB
│   │   ├── connection_manager.py   # Per-client connection cache + RBAC enforcement
│   │   ├── models/                 # SQLModel ORM models (system DB tables)
│   │   └── schema_extractor/
│   │       ├── sql_extractor.py    # Introspects SQL DB schema for LLM context
│   │       └── nosql_extractor.py  # Introspects MongoDB collections
│   │
│   ├── prompts/
│   │   ├── router_prompt.py        # Builds JSON execution plan from query + agents
│   │   ├── sql_prompt.py           # Generates SELECT queries from schema + question
│   │   ├── nosql_prompt.py         # Generates MongoDB queries
│   │   ├── rag_prompt.py           # Decomposes query into semantic sub-intents
│   │   └── final_prompt.py         # Synthesises multi-agent results into one answer
│   │
│   ├── repositories/               # Data access layer (one per domain)
│   ├── schema/                     # Pydantic / SQLModel schemas
│   ├── security/
│   │   ├── o_auth.py               # JWT creation, validation, role enforcement
│   │   └── dependencies.py         # FastAPI OAuth2 scheme dependency
│   │   ├── services/               # Business logic layer
│   ├── settings/config.py          # Env-var config (DB URL, JWT, LLM, embeddings)
│   ├── tools/
│   │   ├── sql_search.py           # Executes SQL queries
│   │   ├── nosql_search.py         # Executes NoSQL queries
│   │   ├── rag_search.py           # Calls vector store retrieve()
│   │   └── nosql_executors/
│   │       └── mongo_executor.py   # MongoDB-specific execution
│   │
│   ├── utils/
│   │   ├── document_processor.py   # PDF/TXT chunker with parallel OCR fallback
│   │   ├── db_seeder.py            # Seeds initial roles, users, models on startup
│   │   ├── hash_util.py            # JWT / password hashing
│   │   └── logger.py               # Structured logging
│   │
│   ├── vector_db/
│   │   ├── base.py                 # BaseVectorStore (embedding loader, warmup, path helpers)
│   │   ├── faiss_store.py          # FAISS: incremental diff + dedup ingestion
│   │   ├── chroma_store.py         # ChromaDB local + cloud: mode-aware paths, global hash tracking
│   │   ├── pinecone_store.py       # Pinecone: namespace-scoped upsert + retrieval, incremental diff
│   │   └── vectordb_registry.py    # Resolves provider name → store instance
│   └── vector_stores/              # Persisted vector data (one folder per client UUID)
│       └── client_id_<uuid>/
│           ├── faiss/              # index.faiss, index.pkl, hashes/
│           ├── chroma_local/       # db/ (SQLite), global_hashes.json, hashes/
│           └── chroma_cloud/       # global_hashes.json, hashes/ (vectors stored remotely)
│           └── pinecone/           # global_hashes.json, hashes/ (vectors stored remotely)
│
├── logs/app.log
└── test/                           # Sample PDFs and test scripts
```

---

## Agents

### SQL Agent
- Extracts the full schema of all configured SQL connections (table names, column names, types) and injects it into the LLM prompt.
- Schema is cached in-memory per connection with a 10-minute TTL to avoid repeated introspection.
- LLM returns a JSON array of `{ sub_question, connection_alias, query }` objects — one per (sub-question, connection) pair.
- All queries are executed in **parallel** via `asyncio.gather`.
- Only `SELECT` queries are permitted — write operations are silently dropped.

### NoSQL Agent
- Introspects MongoDB collection structure via `nosql_extractor.py`.
- LLM generates the appropriate query for the target collection.
- Executed via `mongo_executor.py` using Motor (async MongoDB driver).

### RAG Agent
- On each query, the LLM first **decomposes the question** into atomic semantic sub-intents (e.g. "What is X?" + "How does Y work?").
- Each sub-query is run against the client's vector store independently.
- Results are aggregated and passed to the final node.
- Supports FAISS and ChromaDB backends (configured per client).

### Base Agent
All agents extend `BaseAgent`, which enforces a single interface:
```python
async def run(self, state: dict) -> dict
```
The `state` dict carries `user_query`, `client_id`, `user_id`, `connection_manager`, and accumulated results from prior agents.

---

## Core Pipeline

### Router Prompt Logic
The router receives the **exact list of enabled agents** for the client (not all possible agents). Its rules:
- Always include every available agent in the execution plan.
- Preserve the full original query per agent — never split or modify it.
- Append `user_id` / `client_id` context to SQL and NoSQL queries.
- Return a strictly valid JSON array — no markdown, no explanation.

Example plan for a client with all three agents enabled:
```json
[
  { "agent": "sql_agent",   "query": "How many users signed up last month? (user_id=..., client_id=...)" },
  { "agent": "nosql_agent", "query": "How many users signed up last month? (user_id=..., client_id=...)" },
  { "agent": "rag_agent",   "query": "How many users signed up last month?" }
]
```

### LangGraph Execution
The graph is built dynamically based on the enabled agent set. Conditional edges route through each agent in plan order, then to the `final` node. The graph is compiled once and cached per client in `GraphManager`.

### Final Node
Collects `sql_agent_results`, `nosql_agent_results`, and `rag_agent_results` from state, formats them as structured context, and calls the LLM to produce a single coherent answer. Returns `"No relevant data found."` if all results are empty.

---

## Vector Store & RAG

### Document Ingestion
Upload PDFs or `.txt` files via the chat endpoint. The `DocumentProcessor` handles ingestion in two stages.

**Stage 1 — File-level deduplication (OCR files only)**

Before any parsing begins, the entire file is SHA-256 hashed and checked against a per-client `file_hashes.json` store. If the hash already exists, the file is skipped immediately — no parsing, no OCR, no embedding. This short-circuit exists specifically for scanned/image-based PDFs: because OCR is expensive and its output cannot be chunk-diffed reliably, the whole-file hash is used as the dedup key. After a successful OCR ingestion the file hash is written to `file_hashes.json`. Native text PDFs do not use file-level hashing — they go straight to chunk-level diffing instead.

**Stage 2 — Parsing & chunking (PyMuPDF)**

For files that pass the file-level check (or all native-text PDFs):
- Blocks are sorted by vertical position per page.
- Headings are detected (short text, large vertical gap, no trailing period) and prepended to the paragraph that follows them.
- Reference sections (`References`, `Bibliography`, `Works Cited`, etc.) are detected and ingestion stops there — bibliography entries are never embedded.
- Copyright notices and standalone page numbers are filtered out.
- Each extracted chunk is SHA-256 hashed for chunk-level deduplication (see below).

**OCR Fallback**

On each page, the raw text is first evaluated by a scoring engine before deciding whether to use PyMuPDF's native extraction or fall back to OCR (pytesseract + pdf2image). The engine scores the page across four signals:

| Signal | Condition | Score |
|--------|-----------|-------|
| Text length | Fewer than 30 characters | +2 |
| Noise ratio | More than 30% non-alphanumeric characters | +1 |
| Word quality | Fewer than 50% valid alphabetic words | +1 |
| Avg word length | Average word shorter than 3 characters | +1 |

A score of 2 or above triggers OCR on that page. Pages that pass native extraction continue through the normal paragraph-building pipeline. This means scanned PDFs and mixed documents (some native, some image-based pages) are handled automatically without any manual configuration.

### Incremental Indexing & Deduplication

Every paragraph chunk is SHA-256 hashed before embedding. The hash serves as the vector ID in both FAISS and ChromaDB, enabling two distinct deduplication strategies depending on how the file arrives:

**Case 1 — Same filename re-uploaded**

The store compares the new hash set against the `.hashes` file saved from the previous ingestion of that document:
- Chunks present in the old file but absent in the new one are **deleted** from the index.
- Chunks present in the new file but absent in the old one are **added** as new embeddings.
- Chunks present in both are **skipped entirely** — no re-embedding, no duplication.
- If the sets are identical, the entire operation is a no-op: `"No changes detected"`.

This means uploading a document with minor edits only re-embeds the paragraphs that actually changed.

**Case 2 — Same content, different filename**

If no `.hashes` file exists for the incoming filename, the store checks the new chunk hashes directly against all existing vector IDs in the index:
- Chunks whose hashes already exist in the index are **skipped**.
- Only genuinely new chunks are embedded and added.

This prevents duplicate embeddings even when the same document (or overlapping content) is uploaded under a different name.

Both FAISS and ChromaDB implement identical diffing logic. After every successful ingestion the `.hashes` file is written (or overwritten) with the current `{ hash: text }` map for that document.

Pinecone implements the same two-case diffing strategy. Vectors are upserted into a per-client namespace so that multiple clients can share a single index without data leakage. Metadata (text, document) is stored alongside each vector so retrieval returns raw text without a separate lookup. The local global_hashes.json file plays the same dedup role as in the Chroma implementation — preventing re-embedding of chunks that already exist in the remote index under a different filename.

### Storage Layout
```
src/vector_stores/
└── client_id_<uuid>/
    ├── faiss/
    │   ├── index.faiss
    │   ├── index.pkl
    │   ├── file_hashes.json             # File-level: { file_sha256: document_name }
    │   └── hashes/
    │       └── <document_name>.hashes   # Chunk-level: { chunk_sha256: paragraph_text }
    └── chroma/
        ├── chroma.sqlite3
        ├── file_hashes.json
        └── hashes/
            └── <document_name>.hashes
```

---

## Database Layer

### System Database (MySQL)
Used internally by the platform to store users, clients, roles, agent configs, model configs, feedback, and logs. Managed by SQLModel + async SQLAlchemy. Initialised and seeded automatically on application startup via FastAPI's `lifespan` hook.

### Client Databases
Configured per-client in `config.yaml`. Connected on demand via `ConnectionManager`, which caches connections per `client_id` for the lifetime of the process.

Supported SQL databases:

| Database   | Async Driver         |
|------------|----------------------|
| MySQL      | `mysql+aiomysql`     |
| PostgreSQL | `postgresql+asyncpg` |
| MariaDB    | `mariadb+aiomysql`   |
| SQLite     | `sqlite+aiosqlite`   |
| MSSQL      | `mssql+aioodbc`      |

Supported NoSQL: **MongoDB** via Motor (async).

SQL connection pool settings: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, `pool_recycle=3600`.

---

## API Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/login` | JSON body login → returns `access_token` + `refresh_token` |
| `POST` | `/refresh` | Refresh access token |
| `DELETE` | `/logout` | Invalidate current token |
| `GET` | `/get-current-user` | Get authenticated user's profile |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | Submit a query, optionally upload files for RAG indexing |

Request: `multipart/form-data` with `query: str` and optional `files: List[UploadFile]`.
Response: `{ "final_response": "...", "sql_agent_results": [...], ... }`

### Clients *(SuperAdmin only)*
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/clients/add-client` | Register a new client organisation with config |
| `PUT` | `/clients/update-client/{client_id}` | Update client details & config |
| `DELETE` | `/clients/remove-client/{client_id}` | Soft-delete a client and disable all its users |
| `GET` | `/clients/list-clients` | Paginated client list |
| `GET` | `/clients/get-client/{client_id}` | Get a single client |
| `GET` | `/clients/connect/{client_id}` | Test client DB connections |

**Note:** Config creation is consolidated into the client lifecycle — config is automatically created or updated (`upsert`) whenever a client is registered or modified. The `config.yaml` file is the source of truth for all config reads; the database is kept in sync after every file write.

### Configs *(SuperAdmin only)*
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/configs/read-config-file/{client_id}` | Read a client's current config from the YAML file |
| `PUT` | `/configs/update-config-file/{client_id}` | Update a client's config file and sync to DB |

Additional route groups: `/user`, `/feedback`, `/logs`.

---

## Frontend

The Streamlit app (`app.py`) connects to the FastAPI backend at `http://localhost:8000`.

### Login
JWT-based login. Token is stored in `st.session_state` for the duration of the session.

### Assistant *(all roles)*
- Full chat interface with message history.
- **Upload & Index Knowledge** expander — drag-and-drop PDFs or `.txt` files and click **Build Index** to ingest them into the RAG vector store before querying. This expander is only shown if `rag_agent` is enabled for the client; otherwise a warning is displayed.

### Super Admin Dashboard *(SuperAdmin only)*

#### Clients Tab — Client Registration
Register a new client organisation with a fully dynamic configuration interface:

1. **Client Details** — Full Name, Email, Phone, Password
2. **Agent Selection** — Choose which agents to enable and configure for the client
3. **Provider Selection** — Choose the LLM provider (groq, openai, google, self_hosted) per agent; the model list filters automatically to show only models from that provider. An API key input appears for all providers except self_hosted.
4. **Per-Agent Configuration:**
   - **RAG Agent:** Configure `top_k` (number of results) and vector store backend (FAISS or ChromaDB)
   - **SQL Agent:** Add multiple SQL database connections with type, host, port, credentials, and database name
   - **NoSQL Agent:** Configure MongoDB connections
5. **Dynamic UI** — Add/remove agents and database connections on-the-fly
6. **Single Submit** — Register the client and automatically create its config file in one atomic operation

#### Configs Tab — Config Management
Edit existing client configurations without re-registering:

1. **Client Selection** — Choose a client from the dropdown
2. **View/Update** — Click to load the client's current configuration from the config file
3. **Editable UI** — Modify agent settings and database connections dynamically
4. **Update** — Writes changes to the config file first, then syncs to the database

**Error Handling:**
- Inline field-level validation with red captions beneath each invalid field
- Clear error messages for each field (required fields, invalid email/phone, temperature range, top_k range)

---

## Roles & Access Control

| Role | Permissions |
|------|-------------|
| `SuperAdmin` | Full access to all routes and all client data |
| `Admin` | Chat + access to own client's data only |
| `User` | Chat only, scoped to own client |

Enforcement happens at two levels:
- **Route level** via `auth_dependency.require_roles([...])` FastAPI dependency.
- **Connection level** — `ConnectionManager` blocks `Admin`/`User` from accessing any other client's databases at query time, regardless of what they pass.

Config reads via GET /configs/read-config-file/{client_id} now return sanitized output for the User role — api_key fields and database passwords are stripped before the response is returned. SuperAdmin and Admin receive the full config.

---

## Client Configuration

Each client has a `config.yaml` under `src/configs/client_id_<uuid>/`. This file is the **source of truth** — it is read directly for all config lookups, and the database is kept in sync after every write. Include only the agents the client requires — the orchestrator graph is built exclusively from agents with `enabled: true`.

```yaml
client_name: Acme Corp

allowed_agents:

  sql_agent:
    enabled: true
    model_name: llama-3.3-70b-versatile
    provider: <provider_name>            # groq | openai | google | self_hosted
    api_key: <provider-api-key>
    temperature: 0
    database:
      connection1:
        db_type: mysql          # mysql | postgres | sqlite | mssql | mariadb
        host: localhost
        port: 3306
        username: dbuser
        password: dbpass
        db_name: sales_db
      connection2:
        db_type: postgres
        host: pg-host
        port: 5432
        username: pguser
        password: pgpass
        db_name: analytics_db

  nosql_agent:
    enabled: true
    model_name: llama-3.3-70b-versatile
    provider: <provider_name>            # groq | openai | google | self_hosted
    api_key: <provider-api-key>
    temperature: 0
    database:
      connection1:
        db_type: mongodb
        host: localhost
        port: 27017
        username: admin
        password: admin123
        db_name: catalogue

  rag_agent:
    enabled: true
    model_name: llama-3.3-70b-versatile
    provider: <provider_name>            # groq | openai | google | self_hosted
    api_key: <provider-api-key>
    temperature: 0
    top_k: 3

    # FAISS (local, no extra config needed)
    vector_db:
      provider: faiss

    # Chroma local (no extra config needed)
    # vector_db:
    #   provider: chroma
    #   config:
    #     mode: local

    # Chroma cloud
    # vector_db:
    #   provider: chroma
    #   config:
    #     mode: cloud
    #     vectordb_api_key: <chroma-cloud-api-key>
    #     tenant_id: <tenant-id>
    #     database: <database-name>
    #     collection_name: <collection-name>

    # Pinecone
    # vector_db:
    #   provider: pinecone
    #   config:
    #     vectordb_api_key: <pinecone-api-key>
    #     index_name: <index-name>
```

**Key points:**
- `provider` field is explicit (no more string matching on model name)
- Flattened schema — no nested objects
- `config.yaml` is the source of truth; the DB reflects its contents

A client with only `sql_agent` and `rag_agent` (no `nosql_agent`) will have a two-node graph — the NoSQL node simply does not exist for that client.

---

## Environment Setup

Copy `.env.example` to `.env` and fill in your values:

```env
# System Database (MySQL)
MY_SQL_USER=
MY_SQL_PASSWORD=
MY_SQL_HOST=
MY_SQL_PORT=
MY_SQL_DB=

# JWT
HASH_SECRET_KEY=
HASH_ALGORITHM=HS256
TOKEN_EXPIRY_TIME=3600

# LLM API key (Groq or OpenAI)
LLM_API_KEY=

# HuggingFace embedding model name
EMBEDDING_MODEL=

# Vector store root directory
VECTOR_DB_PATH=src/vector_stores

# Optional: pre-warm a specific client's graph on startup
DEPLOYMENT_CLIENT_ID=<client_uuid>

# LangSmith Observability (optional)
LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=AMAO
```

LLM provider routing is now explicit:

Each model in the system database has a provider field: groq, openai, or self_hosted
self_hosted models are served via vLLM — the runtime is started automatically and a dynamic base_url is injected; no API key is required
Per-agent api_key is stored in the config file; for self_hosted no key is needed

---

## Getting Started

### Prerequisites
- Python 3.10+
- A running MySQL instance (system database)
- `uv` package manager (recommended) or `pip`

### Install

```bash
git clone https://github.com/yashdp-iprogrammer/AMAO.git
cd AMAO

# With uv
uv sync

# Or with pip
pip install -e .
```

### Run the Backend

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

On first startup the application will create all system DB tables and seed initial roles and data automatically.

### Run the Frontend

```bash
streamlit run app.py
```

### Onboard a Client

1. Log in as `SuperAdmin`.
2. Go to **Management → Clients** and fill in the client details.
3. Use the **Agent Selection** interface to choose agents and configure their settings dynamically.
4. Click **Register** — the client is created and their config file is automatically generated.
5. To update the config later, go to **Management → Configs**, select the client, load the current config, edit, and save.
6. Switch to **Assistant** mode and start querying.

### Index Documents for RAG

In the Assistant view, expand **Upload & Index Knowledge**, upload PDFs or `.txt` files, then click **Build Index**. Documents are chunked, deduplicated, embedded, and stored in the client's vector store automatically. This option is only available if `rag_agent` is enabled for your client.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend framework | FastAPI + Uvicorn |
| Agent orchestration | LangGraph |
| LLM providers | OpenAI (`gpt-*`), Groq (`llama-*`), Google(`gemini-*`) |
| Self-hosted LLM inference | vLLM (OpenAI-compatible server, dynamic port allocation) |
| Embeddings | HuggingFace Sentence Transformers |
| Vector stores | FAISS, ChromaDB |
| SQL databases | MySQL, PostgreSQL, SQLite, MariaDB, MSSQL (all async) |
| NoSQL databases | MongoDB (Motor — async) |
| System ORM | SQLModel + async SQLAlchemy |
| PDF processing | PyMuPDF + pytesseract + pdf2image (OCR fallback) |
| Auth | JWT (python-jose) + passlib (argon2) |
| Frontend | Streamlit |
| Package manager | uv |
| Logging | Structured file + console logger |
| Observability | LangSmith (tracing via @traceable + langsmith_trace) |