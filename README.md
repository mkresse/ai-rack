# ai-rack

Compact, self-hosted AI stack for home and small office use. One `docker compose up` gives you a full AI chat platform with multi-provider LLM access, per-user budgets, and usage tracking.

## Architecture

```
Browser :3000 → Open WebUI → LiteLLM :4000 → OpenAI / Anthropic / Google / …
                    ↓              ↓
                 PostgreSQL :4432 (owui + litellm databases)
```

- **Open WebUI** — Chat frontend with multi-user support, stores users, chats, and settings in PostgreSQL (`owui` database)
- **LiteLLM** — LLM proxy that unifies 100+ providers behind one OpenAI-compatible API. Handles model routing, spend tracking, and per-user budget enforcement. Stores config, models, and spend logs in PostgreSQL (`litellm` database)
- **PostgreSQL 16** — Single instance with separate databases and users for each service. An init script (`pg_init_databases` config) creates both databases and roles on first start

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

## User & budget management

User identity flows from Open WebUI to LiteLLM via headers. LiteLLM enforces per-user budgets (default: $10/week). The script `openwebui-tools/litellm_users.py` syncs users between both systems.
