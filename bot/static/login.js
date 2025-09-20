const form = document.getElementById('login-form');
const errorEl = document.getElementById('login-error');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  errorEl.hidden = true;
  const formData = new FormData(form);
  const body = Object.fromEntries(formData.entries());
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) {
      const j = await res.json().catch(()=>({detail:'Login failed'}));
      throw new Error(j.detail || 'Login failed');
    }
    window.location.href = '/admin';
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  }
});
