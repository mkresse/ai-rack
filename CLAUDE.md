# ai-at-home

Docker Compose setup for a self-hosted AI chat stack (Compose project `ai-rack`): Open WebUI → LiteLLM gateway → Postgres, fronted by a Caddy TLS reverse proxy. Intended for deployment on a QNAP NAS. The compose files are the source of truth for ports, images, and settings — read them directly; this file only covers what isn't obvious from them.

`docker-compose.homeserver.yml` is an overlay (merge with `-f docker-compose.yml -f docker-compose.homeserver.yml`) that adapts the stack for LAN deployment, mainly giving Caddy its own macvlan LAN IP and a production Hetzner DNS-01 Caddyfile. See [[project_caddy-hetzner-dns]].

## User identity mapping

OWUI forwards user identity to LiteLLM via headers (requires `ENABLE_FORWARD_USER_INFO_HEADERS=true` in OWUI).
Two simultaneous mappings are configured in `docker-compose.yml` under `user_header_mappings`:

- `X-OpenWebUI-User-Id` → `internal_user` — maps to `LiteLLM_UserTable`. IDs must match between OWUI and LiteLLM; LiteLLM does **not** auto-create internal users from headers, so `litellm_users.py:sync_owui_users_to_litellm` keeps them in sync.
- `X-OpenWebUI-User-Email` → `customer` — maps to `LiteLLM_EndUserTable`. LiteLLM auto-creates end_user records, no sync needed.

The two paths don't conflict — they use separate DB tables and separate spend log fields (`user` vs `end_user`).

## Related source repositories

- **LiteLLM**: `~/private/litellm`
- **Open WebUI (OWUI)**: `~/private/openwebui`
