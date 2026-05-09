# ai-rack

Compact, self-hosted AI stack for home and small office use. One `docker compose up` gives you a full AI chat platform with multi-provider LLM access, per-user budgets, and usage tracking.

## Architecture

```
Browser :3000 → Open WebUI → LiteLLM :4000 → OpenAI / Anthropic / Google / …
                                  ↓
                             PostgreSQL :4432
```

- **Open WebUI** — Chat frontend with multi-user support
- **LiteLLM** — LLM proxy that unifies 100+ providers behind one OpenAI-compatible API. Handles model routing, spend tracking, and per-user budget enforcement
- **PostgreSQL** — Stores config, users, and spend logs for both services

## Quick start

```bash
docker compose up -d
```

Open WebUI is available at `http://localhost:3000`. Add models via the LiteLLM admin UI at `http://localhost:4000` (master key: see compose file).

## User & budget management

User identity flows from Open WebUI to LiteLLM via headers. LiteLLM enforces per-user budgets (default: $10/week). The script `openwebui-tools/litellm_users.py` syncs users between both systems.
