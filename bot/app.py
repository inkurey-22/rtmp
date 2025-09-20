import os
import json
import dotenv
import secrets
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

dotenv.load_dotenv()

ADMIN_USER = os.getenv('ADMIN_USER')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
PUBLIC_HOST = os.getenv('PUBLIC_HOST')
SESSION_SECRET = os.getenv('SESSION_SECRET')

if not ADMIN_PASSWORD or not SESSION_SECRET or not ADMIN_USER or not PUBLIC_HOST:
    raise RuntimeError("ADMIN_USER, ADMIN_PASSWORD, SESSION_SECRET, and PUBLIC_HOST must be set in environment")
    exit(1)

# Simple key store on disk
KEYS_PATH = 'data/keys.json'
DATA_DIR = os.path.dirname(KEYS_PATH) or 'data'
try:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(KEYS_PATH):
        with open(KEYS_PATH, 'w') as f:
            json.dump({}, f)
except PermissionError as exc:
    raise RuntimeError(
        f"Permission denied creating '{KEYS_PATH}' or its parent directory. "
        "Fix permissions on the host, for example: `sudo chown -R $(id -u):$(id -g) bot/data` "
        "or run the container as a user that can write to that path."
    ) from exc


app = FastAPI()

# Static files (HTML/CSS/JS)
app.mount('/static', StaticFiles(directory='static'), name='static')

# Sessions for simple auth
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# Optional: allow same-origin JS; adjust if you serve UI elsewhere
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def require_auth(request: Request):
    if not request.session.get('user'):
        raise HTTPException(status_code=401, detail='Unauthorized')
    return True


@app.get('/')
async def root(request: Request):
    if request.session.get('user'):
        return RedirectResponse('/admin', status_code=302)
    return RedirectResponse('/login', status_code=302)


@app.get('/login')
async def login_page():
    return FileResponse('static/login.html')


@app.post('/api/login')
async def api_login(payload: Dict[str, str], request: Request):
    username = (payload or {}).get('username', '')
    password = (payload or {}).get('password', '')
    if username == ADMIN_USER and password == ADMIN_PASSWORD:
        request.session['user'] = username
        return {'ok': True}
    raise HTTPException(status_code=401, detail='Invalid credentials')


@app.post('/api/logout')
async def api_logout(request: Request):
    request.session.clear()
    return {'ok': True}


@app.get('/api/me')
async def api_me(request: Request):
    user = request.session.get('user')
    return {'authenticated': bool(user), 'user': user}


@app.get('/admin')
async def admin_page(request: Request):
    if not request.session.get('user'):
        return RedirectResponse('/login', status_code=302)
    return FileResponse('static/admin.html')


def _read_keys() -> Dict[str, str]:
    with open(KEYS_PATH, 'r') as f:
        return json.load(f)


def _write_keys(data: Dict[str, str]):
    with open(KEYS_PATH, 'w') as f:
        json.dump(data, f)


@app.get('/api/keys')
async def list_keys(auth: bool = Depends(require_auth)):
    return _read_keys()


@app.post('/api/keys')
async def upsert_key(payload: Dict[str, str], auth: bool = Depends(require_auth)):
    # Accept a required name and optional key. If key is missing/blank, auto-generate.
    name = (payload or {}).get('name')
    key = (payload or {}).get('key')
    if name:
        name = str(name).strip()
    if key is not None:
        key = str(key).strip()
    if not name:
        raise HTTPException(status_code=400, detail='name is required')

    data = _read_keys()

    generated = False
    if not key:
        # Generate a URL-safe stream key and ensure uniqueness against existing values
        existing_values = set(data.values())
        for _ in range(5):  # a few attempts to avoid rare collision
            candidate = secrets.token_urlsafe(32)  # ~43 chars base64url
            if candidate not in existing_values:
                key = candidate
                break
        else:
            # Extremely unlikely
            raise HTTPException(status_code=500, detail='failed to generate unique key')
        generated = True

    data[name] = key
    _write_keys(data)
    return {'ok': True, 'name': name, 'key': key, 'generated': generated}


@app.delete('/api/keys/{name}')
async def delete_key(name: str, auth: bool = Depends(require_auth)):
    data = _read_keys()
    if name in data:
        del data[name]
        _write_keys(data)
    return {'ok': True}


# (Active Streams feature removed)


# RTMP hooks (no auth)
@app.post('/on_publish')
async def on_publish(request: Request):
    form = await request.form()
    stream_key = form.get('name') or form.get('args') or ''
    data = _read_keys()
    if stream_key in data.values():
        return PlainTextResponse('OK')
    raise HTTPException(status_code=403, detail='Forbidden')


@app.post('/on_play')
async def on_play(request: Request):
    return PlainTextResponse('OK')


def _parse_rtmp_stat(xml_text: str) -> List[Dict]:
    """Parse nginx-rtmp stat XML into a list of active streams for the 'live' app.

    Returns a list of dicts with keys: stream (id), uptime (sec), clients (int),
    bytes_in, bytes_out, bw_in, bw_out, label (mapped from keys.json if possible).
    """
    try:
        tree = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    # Build reverse map from stream key -> friendly name
    keys = _read_keys()  # name -> key
    key_to_name = {v: k for k, v in keys.items()}

    streams: List[Dict] = []
    # Find all streams under application name 'live'
    for app in tree.findall('.//application'):
        name_el = app.find('name')
        if name_el is None or name_el.text != 'live':
            continue
        live_el = app.find('live')
        if live_el is None:
            continue
        for s in live_el.findall('stream'):
            sid = (s.findtext('name') or '').strip()
            if not sid:
                continue
            def _int(tag: str) -> int:
                try:
                    return int((s.findtext(tag) or '0').strip())
                except ValueError:
                    return 0
            streams.append({
                'stream': sid,
                'label': key_to_name.get(sid, sid),
                'uptime': _int('time'),
                'clients': _int('nclients') or _int('clients'),
                'bytes_in': _int('bytes_in'),
                'bytes_out': _int('bytes_out'),
                'bw_in': _int('bw_in'),
                'bw_out': _int('bw_out'),
            })
    return streams


@app.get('/api/feeds')
async def api_feeds(auth: bool = Depends(require_auth)):
    """Return current active streams from nginx-rtmp stat page."""
    # Inside Docker network the service name is 'rtmp' on port 80
    url = os.getenv('RTMP_STAT_URL', 'http://rtmp/stat')
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            xml_text = resp.read().decode('utf-8', errors='ignore')
    except Exception as exc:
        # Hide internal error, just return empty list with a hint
        return JSONResponse({'feeds': [], 'error': str(exc)}, status_code=200)

    streams = _parse_rtmp_stat(xml_text)
    return {'feeds': streams}


# Health
@app.get('/health')
async def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=True)
