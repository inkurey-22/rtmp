# RTMP + Discord POV helper

This repository provides a small demo stack so players can publish a "POV" stream (their camera/feed) to a private RTMP server and broadcasters can ingest those POVs into their main stream.

Stack components

- nginx-rtmp container (port 1935) — receives RTMP publish requests from players
- bot service (FastAPI + py-cord) — implements:
   - `/on_publish` HTTP callback for nginx to allow/deny publishers based on registered keys
   - `/send_pov name key` Discord slash command to register a name->key mapping

Quick start (summary)

1) Create `bot/.env` with your Discord bot token and optional PUBLIC_HOST.

```env
DISCORD_TOKEN=your_discord_bot_token_here
PUBLIC_HOST=localhost
```

2) From the repo root, build and run:

```bash
cd /home/curry/Workspace/Persos/rtmp
docker compose up --build
```

3) Register POV keys using the Discord slash command (see detailed Player section below). Then configure OBS to publish to `rtmp://HOST:1935/stream` with the registered stream key.

Deployment note — who runs the server

Only the broadcaster/host needs to run the Docker Compose stack (nginx-rtmp + bot). Players do not run any containers. They only need an RTMP-capable encoder (OBS, ffmpeg, hardware encoder) and the server address + stream key supplied by the broadcaster. The broadcaster's machine or cloud server must expose port 1935 (and the bot must be reachable by nginx for the `on_publish` callback).

Detailed workflow — two sides

Player side (how to send your POV to the server)

Checklist for a player:

- Get a stream key (registered via Discord `/send_pov` command)
- Configure OBS (or another RTMP encoder) to point at the server and use the stream key
- Start streaming from OBS

Step-by-step (player)

1. Get a stream key

- Ask the broadcaster (or an authorized operator) to provide a POV name and key. In this demo the broadcaster or any authorized person runs the Discord slash command in the server where the bot is present:

```
/send_pov alice_pov alice1234
```

- That command stores the mapping `alice_pov -> alice1234` in `bot/data/keys.json` (demo storage).

2. OBS configuration

- Open OBS -> Settings -> Stream
   - Service: "Custom..."
   - Server: `rtmp://<host>:1935/stream`  (replace `<host>` with the public IP or hostname of the broadcaster's server; if local, `localhost`)
   - Stream Key: `alice1234` (the key you were given)

- Alternatively, some encoders accept a full URL: `rtmp://<host>:1935/stream/alice1234` — either works, but OBS separates server and key fields.

3. Start Streaming

- Click "Start Streaming" in OBS. OBS will attempt to connect and publish to nginx.
- nginx will call the bot service's `/on_publish` callback to verify the stream key; if the key exists the bot returns OK and nginx allows the publish.

4. Verify your stream (player):

- Use the broadcaster-provided viewer URL (they will tell you how they'll ingest it) or ask the broadcaster to confirm your POV appears in their monitoring tools.

Broadcaster side (launch server, receive POVs, put them into the stream feed)

Checklist for the broadcaster:

- Run the Docker Compose stack (nginx-rtmp + bot)
- Invite and run the Discord bot (ensure `DISCORD_TOKEN` is set)
- Manage POV keys via Discord `/send_pov` or an admin UI (not included)
- Ingest POV streams into your main broadcast (via OBS, ffmpeg, or a mixing server)

Step-by-step (broadcaster)

1. Prepare environment and start services

- Create `bot/.env` (same as players' instructions):

```env
DISCORD_TOKEN=your_discord_bot_token_here
PUBLIC_HOST=your.public.host.or.ip
```

docker compose up --build -d

- Start the stack (note: by default the bot stores keys inside the container):

```bash
cd /home/curry/Workspace/Persos/rtmp
docker compose up --build -d
```

Persistent storage (optional)

By default the bot will create `data/keys.json` inside the container filesystem. That means keys are ephemeral and will be lost if the container is removed. To persist keys across container restarts, mount a host directory as `/app/data` in the `bot` service in `docker-compose.yml`:

```yaml
services:
   bot:
      # ...
      volumes:
         - ./bot/data:/app/data:Z  # use :Z on SELinux systems to relabel

```

Use `:Z` on SELinux-enabled hosts so Docker relabels the volume with the correct SELinux context. If you prefer to manage labels yourself, use `chcon`/`restorecon` as described in Troubleshooting.

- Confirm services:

```bash
docker compose ps
docker compose logs -f bot   # view bot startup and Discord login
docker compose logs -f rtmp  # nginx-rtmp logs
```

2. Invite the Discord bot (one-time)

- From the Discord Developer Portal, create a bot with `applications.commands` and `bot` scopes and invite it to your server.
- Wait a few minutes for global slash commands to register. For faster testing you can register guild commands (local to one server) instead.

3. Register POV keys for players

- Use `/send_pov <name> <key>` in your Discord server to provision player keys. Example:

```
/send_pov bob_pov bob4321
```

- You can choose keys manually or generate them. Keys are stored in `bot/data/keys.json` in this demo.

4. Monitor incoming POVs

- Use the nginx status page to see active publishers:

   http://<host>:8080/stat

- Or check nginx logs and `docker compose logs rtmp`.

5. Ingest a POV into your main stream feed

There are several practical ways to pull a POV and include it in your broadcast. Pick one that fits your production setup.

Option A — Add as a media source in OBS (recommended, easiest)

- On the broadcaster's OBS instance (the one that sends the main stream to platforms like Twitch/YouTube):
   - Add a new "VLC Video Source" or "Media Source".
   - For a network input, use the RTMP address for the POV: `rtmp://<host>:1935/stream/<key>` (for VLC you may need to use an intermediary like RTSP or HLS; VLC supports RTMP in many builds).
   - Resize and position the source in your scene; switch scenes or toggle visibility when you want to show the POV.

Option B — Use ffmpeg to pull and present locally (stable, flexible)

- Run this on the broadcaster machine to open the POV in a local window (ffplay):

```bash
ffplay rtmp://<host>:1935/stream/<key>
```

- Or use ffmpeg to grab the POV and forward it into your main stream as an input. Example: if your main encoder accepts an RTMP input, you can re-publish the POV as a local stream or feed it into OBS via a virtual camera plugin.

Example: re-publish POV to localhost RTMP app (so OBS can add it as a local source):

```bash
ffmpeg -i rtmp://<host>:1935/stream/<key> -c copy -f flv rtmp://localhost:1936/stream/<local_key>
```

Then configure broadcaster OBS to add `rtmp://localhost:1936/stream/<local_key>` as a network source.

Option C — Multi-input mixing server (advanced)

- Use Nginx/HLS or a mixing server (SRT, Kurento, Janus, or custom ffmpeg pipelines) to ingest many POVs, transcode if needed, and present program feeds to the switcher. This scales better for many simultaneous POVs.

6. When to allow/deny publishers

- The demo bot's `/on_publish` handler allows publishes if the stream key exists in `data/keys.json`.
- In production, you should verify the Discord user, enforce per-user limits, and possibly require an HMAC/mutual secret between nginx and the bot so publishers can't spoof requests.

Examples and commands

## RTMP + Discord POV helper — short overview

This repo provides a minimal demo to let players publish a personal "POV" RTMP stream to a private RTMP server while a broadcaster ingests those POVs into a main program.

Components (what runs)

- nginx-rtmp — RTMP server (default app: /stream) listening on port 1935
- bot (FastAPI + py-cord) — simple control service that exposes:
   - a Discord slash command to register stream keys (/send_pov)
   - an HTTP endpoint used by nginx (`on_publish`) to validate stream keys before allowing publishers

## Technical explanation

- Players publish to nginx-rtmp using a stream key.
- nginx calls the bot's `/on_publish` callback to confirm the key is valid. If valid, nginx accepts the publish; otherwise it's rejected.
- The bot stores mappings (name -> key) in `bot/data/keys.json` in this demo. For production use a proper database and secure the endpoints.

Ports used (defaults)

- RTMP publish/playback: 1935
- nginx status (optional): 8080 (if enabled in config)
- Bot HTTP API: 8000 (internal to compose)

## Setup

Checklist

- [ ] Host/Broadcaster: prepare env, run Docker Compose, invite bot, register keys
- [ ] Player: obtain stream key and configure OBS/encoder

### Host / Broadcaster side (launch server, accept POVs)

1) Create `bot/.env` with your Discord token and public host (example):

```env
DISCORD_TOKEN=your_discord_bot_token_here
PUBLIC_HOST=your.public.host.or.ip
```

2) (Optional) Persist keys across restarts by mounting `./bot/data` into the bot service in `docker-compose.yml`:

```yaml
services:
   bot:
      # ...
      volumes:
         - ./bot/data:/app/data
```

3) From the repo root, build and run the stack:

```bash
cd /home/curry/Workspace/Persos/rtmp
docker compose up --build -d
```

4) Invite the Discord bot via the Developer Portal (scopes: applications.commands + bot) and wait for slash commands to register.

5) Register POV keys for players using the slash command in Discord:

```
/send_pov alice_pov alice1234
```

6) Monitor activity:

```bash
docker compose ps
docker compose logs -f bot
docker compose logs -f rtmp
```

How to ingest a POV into your broadcast

- Add the POV as a network media source in OBS using RTMP URL: `rtmp://<host>:1935/stream/<key>` (or VLC/ffplay)
- Or pull with ffmpeg and re-publish locally for OBS: `ffmpeg -i rtmp://<host>:1935/stream/<key> -c copy -f flv rtmp://localhost:1936/stream/<local_key>`

### Player side (stream your POV)

1) Get a stream key from the broadcaster (they register it with `/send_pov`).

2) In OBS (or other RTMP encoder) set:

- Service: Custom
- Server: `rtmp://<host>:1935/stream`
- Stream Key: `<your_key>`

Alternative: use the full URL `rtmp://<host>:1935/stream/<key>` if your encoder accepts it.

3) Start streaming. If publish is rejected, the bot's `/on_publish` check failed — ask the broadcaster to confirm the key and that the bot is running.

Minimal troubleshooting

- If OBS can't publish: check `docker compose logs bot` for `/on_publish` errors and confirm the key exists in `bot/data/keys.json`.
- If slash command isn't visible: allow time for registration or use guild-scoped commands while testing.

Security notes (short)

- Demo defaults to JSON file storage and an open slash command. For production: secure `/send_pov` (role checks), use HMAC for `on_publish`, serve control endpoints over HTTPS, and persist keys in a DB.
