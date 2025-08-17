import os
import hmac
import hashlib
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from httpx import AsyncClient
from dotenv import load_dotenv
import discord
from discord.ext import commands

# app_commands may not exist if an older/alternative discord package is installed; handle gracefully
app_commands = getattr(discord, 'app_commands', None)

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
PUBLIC_HOST = os.getenv('PUBLIC_HOST', 'localhost')

# --- Simple auth store ---
# For demo, store stream keys in a json file under data/keys.json
KEYS_PATH = 'data/keys.json'
DATA_DIR = os.path.dirname(KEYS_PATH) or 'data'
try:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(KEYS_PATH):
        # create file with default empty mapping
        with open(KEYS_PATH, 'w') as f:
            json.dump({}, f)
except PermissionError as exc:
    # Provide an actionable error that helps the operator fix host permissions
    raise RuntimeError(
        f"Permission denied creating '{KEYS_PATH}' or its parent directory. "
        "Fix permissions on the host, for example: `sudo chown -R $(id -u):$(id -g) bot/data` "
        "or run the container as a user that can write to that path."
    ) from exc

app = FastAPI()

# Discord bot + slash command
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# Register a command to send POV: try slash command, fall back to prefix command if necessary


@bot.event
async def on_ready():
    print(f"Bot ready. Logged in as {bot.user}")

    # Sync app (slash) commands once and report which commands are present.
    # Guard with a flag so we don't print this repeatedly on reconnects.
    if app_commands is not None and not getattr(bot, '_commands_synced', False):
        try:
            # sync the command tree with Discord (this may create/update commands)
            await bot.tree.sync()
            # collect registered command names from the local tree
            command_names = [c.name for c in bot.tree.walk_commands()]
            if command_names:
                print(f"Synced {len(command_names)} app command(s): {', '.join(command_names)}")
            else:
                print("No app commands found to sync.")
        except Exception as e:
            print(f"Failed to sync app commands: {e}")
        finally:
            bot._commands_synced = True


class Pov(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # If app_commands is available, register as a slash command on the app command tree
    if app_commands is not None:
        @app_commands.command(name='send_pov', description='Register a POV stream key for a name')
        @app_commands.describe(name='Display name', key='RTMP stream key')
        async def send_pov(self, interaction: discord.Interaction, name: str, key: str):
            with open(KEYS_PATH, 'r') as f:
                data = json.load(f)
            data[name] = key
            with open(KEYS_PATH, 'w') as f:
                json.dump(data, f)
            await interaction.response.send_message(f"Saved POV '{name}' -> key", ephemeral=True)
    else:
        # Fallback: use a prefix command (!send_pov name key)
        @commands.command(name='send_pov')
        async def send_pov(self, ctx: commands.Context, name: str, key: str):
            with open(KEYS_PATH, 'r') as f:
                data = json.load(f)
            data[name] = key
            with open(KEYS_PATH, 'w') as f:
                json.dump(data, f)
            await ctx.send(f"Saved POV '{name}' -> key")


bot.add_cog(Pov(bot))

# If app_commands is available, also register a top-level slash command (server/guild/global)
if app_commands is not None:
    @bot.tree.command(name='send_pov')
    async def slash_send_pov(interaction: discord.Interaction, name: str, key: str):
        with open(KEYS_PATH, 'r') as f:
            data = json.load(f)
        data[name] = key
        with open(KEYS_PATH, 'w') as f:
            json.dump(data, f)

        await interaction.response.send_message(f"Saved POV '{name}' -> key", ephemeral=True)
else:
    # top-level text command already covered by the Cog fallback
    pass

# Run bot in background when FastAPI starts
@app.on_event('startup')
async def startup_event():
    # start discord bot in background
    async def _run_bot():
        await bot.start(DISCORD_TOKEN)

    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(_run_bot())

# RTMP on_publish hook: called by nginx when a publisher starts.
# We'll check the stream key and allow/deny.
@app.post('/on_publish')
async def on_publish(request: Request):
    form = await request.form()
    # nginx posts variables like name, args, etc.
    stream_key = form.get('name') or form.get('args')
    app_name = form.get('app')
    # simple validation: check key exists in our store
    with open(KEYS_PATH, 'r') as f:
        data = json.load(f)
    if stream_key in data.values():
        return PlainTextResponse('OK')
    # deny if not found
    raise HTTPException(status_code=403, detail='Forbidden')

@app.post('/on_play')
async def on_play(request: Request):
    return PlainTextResponse('OK')

# Minimal health route
@app.get('/')
async def index():
    return {'status': 'ok'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=True)
