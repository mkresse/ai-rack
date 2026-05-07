# ai-at-home

Docker Compose setup for running AI services locally (stack name: `owui-stack`).

## Services

- **Open WebUI** — chat frontend, exposed on port 3000, connects to LiteLLM as its OpenAI-compatible backend
- **LiteLLM** — LLM proxy/gateway, exposed on port 4000, config inline in docker-compose, models stored in DB
- **PostgreSQL 16** — database for LiteLLM, exposed on port 4432

## User identity mapping

OWUI forwards user identity to LiteLLM via headers (requires `ENABLE_FORWARD_USER_INFO_HEADERS=true` in OWUI).
Two simultaneous mappings are configured in `docker-compose.yml` under `user_header_mappings`:

- `X-OpenWebUI-User-Id` → `internal_user` — maps to `LiteLLM_UserTable`. IDs must match between OWUI and LiteLLM; LiteLLM does **not** auto-create internal users from headers, so `litellm_users.py:sync_owui_users_to_litellm` keeps them in sync.
- `X-OpenWebUI-User-Email` → `customer` — maps to `LiteLLM_EndUserTable`. LiteLLM auto-creates end_user records, no sync needed.

The two paths don't conflict — they use separate DB tables and separate spend log fields (`user` vs `end_user`).

## Related source repositories

- **LiteLLM**: `/Users/martin/private/litellm`
- **Open WebUI (OWUI)**: `/Users/martin/private/openwebui`
