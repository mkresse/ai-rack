# ai-rack

Compact, self-hosted AI stack for home and small office use. One `docker compose up` gives you a full AI chat platform with multi-provider LLM access, per-user budgets, and usage tracking.

## Contents

- [Architecture](#architecture)
- [Setup](#setup)
  - [Environment variables](#environment-variables)
- [Home-server deployment](#home-server-deployment)
  - [Overlay file](#overlay-file)
  - [TLS via DNS-01 delegation](#tls-via-dns-01-delegation)
  - [Deploy](#deploy)
- [Features](#features)
- [User & budget management](#user--budget-management)

## Architecture

```
Browser → Caddy :80/:443 → Open WebUI :3000 → LiteLLM :4000 → Anthropic / OpenAI / …
            (TLS proxy)         │                   ↓
                                │              PostgreSQL :4432
                                │                (litellm db)
                                ↓
                          PostgreSQL :4432          Mistral API
                         (owui + vector dbs)     (TTS, voice cloning)
```

- **Caddy** — Reverse proxy terminating TLS in front of Open WebUI. Locally it serves `https://localhost:8443` with a self-signed internal-CA cert; on a home server it obtains and renews Let's Encrypt certificates automatically via the DNS-01 challenge (Hetzner DNS). Not strictly required locally (Open WebUI is reachable directly on `:3000`), but included so the same proxy/TLS edge runs in dev as in production
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

Open WebUI is available at `http://localhost:3000` (or via Caddy at `https://localhost:8443`). Add models via the LiteLLM admin UI at `http://localhost:4000`.

### Environment variables

All secrets are kept in `.env` (git-ignored). See `.env.example` for the full list:

| Variable | Purpose |
|---|---|
| `LITELLM_MASTER_KEY` | Admin API key for LiteLLM (also used by Open WebUI to connect) |
| `LITELLM_SALT_KEY` | Encryption salt for LiteLLM stored credentials |
| `POSTGRES_PASS` | Password for the PostgreSQL superuser (`postgres`) |
| `OWUI_DB_PASS` | Password for the `owui_user` database role |
| `LITELLM_DB_PASS` | Password for the `litellm_user` database role |
| `FAL_AI_API_KEY` | fal.ai API key for image generation models |
| `CADDY_DOMAIN` | Public domain Caddy serves (e.g. `ai.example.com`) |
| `CADDY_ACME_DELEGATION_ZONE` | DNS zone where the ACME TXT record is written (see [TLS](#tls-via-dns-01-delegation)) |
| `HETZNER_API_TOKEN` | Hetzner DNS API token used by Caddy for the DNS-01 challenge |
| `CADDY_IP` | Caddy's LAN IP on the macvlan network (home-server overlay) |
| `CADDY_MACVLAN_PARENT` | Host NIC the macvlan attaches to, e.g. `eth0` (home-server overlay) |
| `CADDY_MACVLAN_SUBNET` | LAN subnet, e.g. `192.168.1.0/24` (home-server overlay) |
| `CADDY_MACVLAN_GATEWAY` | LAN gateway, e.g. `192.168.1.1` (home-server overlay) |

If `.env` is missing, all variables fall back to insecure defaults defined in `docker-compose.yml` — fine for a quick local test, not for anything exposed to a network.

## Home-server deployment

Two compose files:

- **`docker-compose.yml`** — the complete, self-contained stack, fully usable on its own.
  Caddy serves Open WebUI at `https://localhost:8443` with a self-signed cert from Caddy's
  internal CA (`tls internal`) — no public domain or DNS token needed.
- **`docker-compose.homeserver.yml`** — overlay with the bits that need a real host: a
  **macvlan** LAN IP for Caddy and **public TLS** (the `CADDY_DOMAIN` site with Let's
  Encrypt via Hetzner DNS-01). Caddy is reached on its own LAN IP at `:80`/`:443`, so it
  publishes no host ports. Replaces the localhost Caddyfile when layered on top.

### Overlay file

The overlay adds a **macvlan** network that gives Caddy its own IP on the physical LAN
(`CADDY_IP`), so it appears as a standalone host rather than a port on the Docker host.

- Requires a real NIC as parent (`CADDY_MACVLAN_PARENT`, e.g. `eth0` — check with `ip link`).
- Does **not** work on Docker Desktop / macOS (no L2 access to a physical NIC).
- macvlan caveat: the Docker host itself cannot reach the macvlan IP — other LAN clients can.
- Keep `CADDY_IP` **outside** the router's DHCP pool to avoid address collisions.

### TLS via DNS-01 delegation

Caddy obtains Let's Encrypt certificates using the DNS-01 challenge, which proves domain
ownership by writing a `_acme-challenge.<domain>` TXT record. To avoid giving Caddy API
access to the registrar of `CADDY_DOMAIN`, the challenge is **delegated** to a separate
zone:

- The public domain stays at its registrar untouched.
- A one-time static CNAME points the challenge name at a delegation zone hosted on a
  DNS-API-capable provider (Hetzner):

  ```
  _acme-challenge.<CADDY_DOMAIN>  CNAME  _acme-challenge.<CADDY_ACME_DELEGATION_ZONE>
  ```

- At renewal, Caddy writes the TXT record into the delegation zone via `HETZNER_API_TOKEN`,
  and the validator follows the CNAME. Only the delegation zone ever needs API credentials.

### Deploy

Deploy directly with both files:

```bash
docker compose -f docker-compose.yml -f docker-compose.homeserver.yml up -d
```

Or render a single, fully-interpolated compose file (handy as a single source to paste
into e.g. QNAP Container Station, which needs an all-in-one config):

```bash
docker compose -f docker-compose.yml -f docker-compose.homeserver.yml config > docker-compose.rendered.yml
```

> ⚠️ **The rendered file contains every secret in plaintext** — `HETZNER_API_TOKEN`,
> `ANTHROPIC_API_KEY`, DB passwords, etc. are all interpolated into it. Treat it like
> `.env`: never commit it, never paste it anywhere public.

## Features

The following features are pre-configured in `docker-compose.yml` and work out of the box:

- **User spend tracking** — Per-user budget enforcement and spend logging via LiteLLM, with Open WebUI user identity forwarded through headers.
- **Multi-provider LLM access** — Anthropic models via wildcard routing (`anthropic/*`), with credentials managed through LiteLLM's credential system. Additional models stored in DB.
- **Image generation** — fal.ai models (`fal_ai/fal-ai/flux/schnell`, `fal_ai/fal-ai/gemini-25-flash-image`) routed through LiteLLM. Open WebUI's OpenAI image engine points at LiteLLM, defaulting to flux/schnell at 1024×1024 (`FAL_AI_API_KEY` required). Note: LiteLLM only routes fal models it has an explicit transformation for (flux/schnell, gemini-25-flash-image/nano-banana, imagen4, recraft, flux-pro, bytedance/seedream, ideogram, stable-diffusion); other fal endpoints (e.g. flux-2) and **image editing** are not supported via the OpenAI image API.
- **Web Search** — Google search via the DDGS library, enabled for all chats.
- **RAG** — pgvector-backed retrieval-augmented generation with hybrid BM25+vector search using `intfloat/multilingual-e5-small` embeddings (multilingual, including German).
- **Text-to-Speech** — Mistral Voxtral TTS (`voxtral-mini-tts-2603`) via the Mistral API. Users can override the admin default voice in their personal Open WebUI settings.

## User & budget management

User identity flows from Open WebUI to LiteLLM via headers. LiteLLM enforces per-user budgets (default: $10/week). The script `openwebui-tools/litellm_users.py` syncs users between both systems.
