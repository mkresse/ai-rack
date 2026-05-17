# ai-rack

Compact, self-hosted AI stack for home and small office use. One `docker compose up` gives you a full AI chat platform with multi-provider LLM access, per-user budgets, and usage tracking.

## Architecture

```
Browser :3000 → Open WebUI → LiteLLM :4000 → Anthropic / OpenAI / …
                    │              ↓
                    │         PostgreSQL :4432
                    │           (litellm db)
                    ↓
               PostgreSQL :4432         Mistral API
              (owui + vector dbs)    (TTS, voice cloning)
```

- **Open WebUI** — Chat frontend with multi-user support, stores users, chats, and settings in PostgreSQL (`owui` database). RAG embeddings stored in pgvector (`vector` database)
- **LiteLLM** — LLM proxy that unifies 100+ providers behind one OpenAI-compatible API. Handles model routing, spend tracking, and per-user budget enforcement. Stores config, models, and spend logs in PostgreSQL (`litellm` database)
- **PostgreSQL 16 (pgvector)** — Single instance with three databases (`owui`, `litellm`, `vector`) and separate users for each service. The `vector` database has the pgvector extension for RAG. An init script (`pg_init_databases` config) creates all databases and roles on first start

## Setup

1. Copy `.env.example` to `.env` and fill in the values:

   ```bash
   cp .env.example .env
   ```

2. Start the stack:

   ```bash
   docker compose up -d
   ```

Open WebUI is available at `http://localhost:3000`. Add models via the LiteLLM admin UI at `http://localhost:4000`.

### Environment variables

All secrets are kept in `.env` (git-ignored). See `.env.example` for the full list:

| Variable | Purpose |
|---|---|
| `LITELLM_MASTER_KEY` | Admin API key for LiteLLM (also used by Open WebUI to connect) |
| `LITELLM_SALT_KEY` | Encryption salt for LiteLLM stored credentials |
| `POSTGRES_PASS` | Password for the PostgreSQL superuser (`postgres`) |
| `OWUI_DB_PASS` | Password for the `owui_user` database role |
| `LITELLM_DB_PASS` | Password for the `litellm_user` database role |

If `.env` is missing, all variables fall back to insecure defaults defined in `docker-compose.yml` — fine for a quick local test, not for anything exposed to a network.

## Features

The following features are pre-configured in `docker-compose.yml` and work out of the box:

- **User spend tracking** — Per-user budget enforcement and spend logging via LiteLLM, with Open WebUI user identity forwarded through headers.
- **Multi-provider LLM access** — Anthropic models via wildcard routing (`anthropic/*`), with credentials managed through LiteLLM's credential system. Additional models stored in DB.
- **Web Search** — Google search via the DDGS library, enabled for all chats.
- **RAG** — pgvector-backed retrieval-augmented generation with hybrid BM25+vector search using `intfloat/multilingual-e5-small` embeddings (multilingual, including German).
- **Text-to-Speech** — Mistral Voxtral TTS (`voxtral-mini-tts-2603`) via the Mistral API. Users can override the admin default voice in their personal Open WebUI settings.

## User & budget management

User identity flows from Open WebUI to LiteLLM via headers. LiteLLM enforces per-user budgets (default: $10/week). The script `openwebui-tools/litellm_users.py` syncs users between both systems.
