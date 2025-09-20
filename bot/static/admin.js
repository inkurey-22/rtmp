async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error((await res.json().catch(()=>({detail:'Request failed'}))).detail || 'Request failed');
  return res.json();
}

async function loadKeys() {
  const list = document.getElementById('list');
  list.innerHTML = '';
  try {
    const data = await fetchJSON('/api/keys');
    const entries = Object.entries(data);
    if (entries.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'item';
      empty.textContent = 'No keys yet';
      list.appendChild(empty);
      return;
    }
    for (const [name, key] of entries) {
      const row = document.createElement('div');
      row.className = 'item';
      const nameEl = document.createElement('div');
      nameEl.className = 'name';
      nameEl.textContent = name;
      const keyEl = document.createElement('div');
      keyEl.className = 'key';
      keyEl.textContent = key;
      const actions = document.createElement('div');
      const del = document.createElement('button');
      del.className = 'btn danger';
      del.textContent = 'Delete';
      del.addEventListener('click', async () => {
        if (!confirm(`Delete key for ${name}?`)) return;
        await fetchJSON(`/api/keys/${encodeURIComponent(name)}`, { method: 'DELETE' });
        await loadKeys();
      });
      actions.appendChild(del);
      row.appendChild(nameEl);
      row.appendChild(keyEl);
      row.appendChild(actions);
      list.appendChild(row);
    }
  } catch (err) {
    const error = document.createElement('div');
    error.className = 'error';
    error.textContent = err.message;
    list.appendChild(error);
  }
}

async function loadFeeds() {
  const mount = document.getElementById('feeds');
  if (!mount) return;
  mount.innerHTML = '';
  try {
    const { feeds, error } = await fetchJSON('/api/feeds');
    if (error) {
      const errEl = document.createElement('div');
      errEl.className = 'error';
      errEl.textContent = `Unable to fetch feeds: ${error}`;
      mount.appendChild(errEl);
      return;
    }
    if (!feeds || feeds.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'item';
      empty.textContent = 'No active feeds';
      mount.appendChild(empty);
      return;
    }
    for (const f of feeds) {
      const row = document.createElement('div');
      row.className = 'item';
      const nameEl = document.createElement('div');
      nameEl.className = 'name';
      nameEl.textContent = f.label || f.stream;
      const details = document.createElement('div');
      details.className = 'key';
      const mins = Math.floor((f.uptime || 0) / 60);
      const secs = (f.uptime || 0) % 60;
      const duration = `${mins}m ${secs}s`;
      details.textContent = `Stream: ${f.stream} • Uptime: ${duration} • Viewers: ${f.clients || 0}`;
      const actions = document.createElement('div');
      const copyBtn = document.createElement('button');
      copyBtn.className = 'btn';
      copyBtn.textContent = 'Copy RTMP URL';
      copyBtn.addEventListener('click', async () => {
        const host = window.location.hostname || 'localhost';
        const url = `rtmp://${host}:1935/live/${encodeURIComponent(f.stream)}`;
        try {
          await navigator.clipboard.writeText(url);
          copyBtn.textContent = 'Copied!';
          setTimeout(()=> copyBtn.textContent = 'Copy RTMP URL', 1200);
        } catch {}
      });
      actions.appendChild(copyBtn);
      row.appendChild(nameEl);
      row.appendChild(details);
      row.appendChild(actions);
      mount.appendChild(row);
    }
  } catch (err) {
    const error = document.createElement('div');
    error.className = 'error';
    error.textContent = err.message;
    mount.appendChild(error);
  }
}

document.getElementById('create-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const formData = new FormData(form);
  const data = Object.fromEntries(formData.entries());
  // Trim values and allow empty key to trigger generation
  if (typeof data.name === 'string') data.name = data.name.trim();
  if (typeof data.key === 'string') data.key = data.key.trim();
  if (!data.name) {
    alert('Name is required');
    return;
  }
  const res = await fetchJSON('/api/keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  form.reset();
  // Show result with generated/returned key
  try {
    const resultEl = document.getElementById('create-result');
    if (resultEl) {
      resultEl.style.display = 'block';
      resultEl.innerHTML = '';
      const msg = document.createElement('div');
      msg.textContent = `Saved key for "${res.name}"` + (res.generated ? ' (auto-generated)' : '');
      const code = document.createElement('code');
      code.textContent = res.key;
      code.style.marginLeft = '8px';
      const copyBtn = document.createElement('button');
      copyBtn.className = 'btn';
      copyBtn.style.marginLeft = '8px';
      copyBtn.textContent = 'Copy';
      copyBtn.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(res.key);
          copyBtn.textContent = 'Copied!';
          setTimeout(()=> copyBtn.textContent = 'Copy', 1200);
        } catch {}
      });
      resultEl.appendChild(msg);
      resultEl.appendChild(code);
      resultEl.appendChild(copyBtn);
      // Auto-hide after a few seconds
      setTimeout(() => { resultEl.style.display = 'none'; }, 6000);
    }
  } catch {}
  await loadKeys();
});

document.getElementById('logout').addEventListener('click', async () => {
  await fetchJSON('/api/logout', { method: 'POST' });
  window.location.href = '/login';
});

window.addEventListener('DOMContentLoaded', async () => {
  const me = await fetch('/api/me').then(r=>r.json()).catch(()=>({authenticated:false}));
  if (!me.authenticated) {
    window.location.href = '/login';
    return;
  }
  await loadKeys();
  await loadFeeds();
  setInterval(loadFeeds, 5000);
});
