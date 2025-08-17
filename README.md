# RTMP broadcasting server + Discord bot

This repository contains a minimal demo stack that lets players publish a personal "POV" RTMP stream to a private nginx-rtmp server while a broadcaster ingests those POVs into a main broadcast. The services run as Docker Compose containers so a single host (the broadcaster) can run the server and the Discord control bot.

## Tech stack

- nginx with nginx-rtmp module — RTMP server (nginx configuration at `nginx/nginx.conf`)
- Python FastAPI service (`bot/app.py`) — validates publishers and exposes a Discord slash command
- py-cord — Discord library used by the bot (see `bot/requirements.txt`)
- Docker + Docker Compose — containerize and run the stack (`docker-compose.yml`)
- Optional tools for broadcasters: OBS, ffmpeg / ffplay

Files of interest

- `docker-compose.yml` — service definitions for `rtmp` (nginx) and `bot`
- `nginx/nginx.conf` — RTMP app, on_publish callback URL, and optional stat page
- `bot/app.py` — FastAPI bot that implements `/on_publish` and the `/send_pov` slash command
- `bot/requirements.txt` — Python dependencies for the bot
- `bot/data/keys.json` — demo key storage (created at runtime)

## Quick start (host / broadcaster)

Prerequisites

- Docker and Docker Compose installed on the host
- A Discord bot token (create a bot in the Discord Developer Portal and invite it with `applications.commands` and `bot` scopes)

1. Create `bot/.env` with at minimum:

```env
DISCORD_TOKEN=your_discord_bot_token_here
PUBLIC_HOST=your.public.host.or.ip   # optional; used for callbacks/URLs
```

2. (Optional) Persist keys across restarts by mounting a host directory into the bot service. In `docker-compose.yml` add a volume for `bot` such as `./bot/data:/app/data:Z` (use `:Z` on SELinux hosts).

3. From the repo root, build and start the stack:

```bash
cd /home/curry/Workspace/Persos/rtmp
docker compose up --build -d
```

4. Confirm services are running and the bot logged into Discord:

```bash
docker compose ps
docker compose logs -f bot
docker compose logs -f rtmp
```

5. Register a player key in your Discord server (broadcaster or operator):

```
/send_pov <name> <key>
```

The demo bot stores mappings in `bot/data/keys.json`.

## Player quick guide (publish a POV)

- Server (OBS/encoder): `rtmp://<host>:1935/stream`
- Stream key: the key provided by the broadcaster
- Alternative encoders may accept the full URL: `rtmp://<host>:1935/stream/<key>`
- Start streaming; nginx will call the bot's `/on_publish` endpoint to validate the key.

## Broadcaster: ingesting POVs

- Add a network media source in OBS using `rtmp://<host>:1935/stream/<key>` (or use VLC/ffplay):

```bash
ffplay rtmp://<host>:1935/stream/<key>
```

- Or forward the POV with ffmpeg into a local RTMP app for OBS to consume:

```bash
ffmpeg -i rtmp://<host>:1935/stream/<key> -c copy -f flv rtmp://localhost:1936/stream/<local_key>
```

## Ports (defaults)

- RTMP publish/playback: 1935
- nginx status page (if enabled in `nginx.conf`): 8080
- Bot HTTP API (internal): 8000

## Troubleshooting (quick)

- Publish rejected: check `docker compose logs -f bot` for `/on_publish` errors and confirm the key exists in `bot/data/keys.json`.
- Slash command not visible: global slash commands may take minutes to register; for testing use guild-scoped commands. A fallback prefix command is also present : `!send_pov <name> <key>`

## Security notes

This is a demo. Recommendations before production use:

- Do not rely on `bot/data/keys.json` for production; use a proper database.
- Secure the bot's `/send_pov` command (role checks or admin-only).
- Protect `/on_publish` with an HMAC or mutual secret so nginx callbacks can't be spoofed.
- Serve control endpoints over HTTPS and limit access by network or auth.
