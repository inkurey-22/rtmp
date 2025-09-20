# RTMP broadcasting server + Admin Web UI

This repository contains a minimal demo stack that lets players publish a personal "POV" RTMP stream to a private nginx-rtmp server while a broadcaster ingests those POVs into a main broadcast. The services run as Docker Compose containers so a single host (the broadcaster) can run the server and a small admin web UI (no Discord required).

## Tech stack

- nginx with nginx-rtmp module — RTMP server (nginx configuration at `nginx/nginx.conf`)
- Python FastAPI service (`bot/app.py`) — validates publishers and serves a minimal admin web UI
- Docker + Docker Compose — containerize and run the stack (`docker-compose.yml`)
- Optional tools for broadcasters: OBS, ffmpeg / ffplay

Files of interest

- `docker-compose.yml` — service definitions for `rtmp` (nginx) and `bot`
- `nginx/nginx.conf` — RTMP app, on_publish callback URL, and optional stat page
- `bot/app.py` — FastAPI app implementing `/on_publish` and the admin UI/API
- `bot/requirements.txt` — Python dependencies for the service
- `bot/data/keys.json` — demo key storage (created at runtime)
- `bot/static/` — HTML/CSS/JS for login and dashboard

## Quick start (host / broadcaster)

Prerequisites

- Docker and Docker Compose installed on the host

1. (Optional) Persist keys across restarts by mounting a host directory into the bot service. In `docker-compose.yml` add a volume for `bot` such as `./bot/data:/app/data:Z` (use `:Z` on SELinux hosts).

3. From the repo root, build and start the stack:

```bash
cd /home/curry/Workspace/Persos/rtmp
docker compose up --build -d
```

4. Confirm services are running:

```bash
docker compose ps
docker compose logs -f bot
docker compose logs -f rtmp
```

5. Open the admin UI to manage keys:

- Admin UI: http://localhost:8000
- Login with the credentials from `docker-compose.yml` env vars (`ADMIN_USER`, `ADMIN_PASSWORD`).
- Add, list, and delete stream keys from the dashboard.

## Player quick guide (publish a POV)

- Server (OBS/encoder): `rtmp://<host>:1935/live`
- Stream key: the key provided by the broadcaster
- Alternative encoders may accept the full URL: `rtmp://<host>:1935/live/<key>`
- Start streaming; nginx will call the bot's `/on_publish` endpoint to validate the key.

## Broadcaster: ingesting POVs

- Add a network media source in OBS using `rtmp://<host>:1935/live/<key>` (or use VLC/ffplay):

```bash
ffplay rtmp://<host>:1935/live/<key>
```

- Or forward the POV with ffmpeg into a local RTMP app for OBS to consume:

```bash
ffmpeg -i rtmp://<host>:1935/live/<key> -c copy -f flv rtmp://localhost:1936/stream/<local_key>
```

## Ports (defaults)

- RTMP publish/playback: 1935
- nginx status page (if enabled in `nginx.conf`): 8080
- Admin UI/API (internal): 8000

## Troubleshooting (quick)

- Publish rejected: check `docker compose logs -f bot` for `/on_publish` errors and confirm the key exists in `bot/data/keys.json`.

## Security notes

This is a demo. Recommendations before production use:

- Do not rely on `bot/data/keys.json` for production; use a proper database.
- Protect `/on_publish` with an HMAC or mutual secret so nginx callbacks can't be spoofed.
- Serve control endpoints over HTTPS and limit access by network or auth.
