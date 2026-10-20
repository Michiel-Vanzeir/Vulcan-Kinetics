/** Adapt the popup settings and health check for standalone browser testing. */
const API_URL = 'http://127.0.0.1:8000';
const autoDetect = document.querySelector('#auto-detect');
const storageError = document.querySelector('#storage-error');

let savingSetting = false;

/** Keep the compact popup and account Settings view on the same server-owned preference. */
async function syncHesitationPreference() {
  if (savingSetting) return;
  try {
    const response = await fetch('/ui-api/state', { signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error('UI server unavailable.');
    const state = await response.json();
    if (!savingSetting) autoDetect.checked = state.account.autoDetect;
    storageError.hidden = true;
  } catch (error) {
    storageError.hidden = false;
    storageError.textContent = `Cannot load the setting: ${error.message}`;
  }
}

autoDetect.addEventListener('change', async () => {
  savingSetting = true;
  autoDetect.disabled = true;
  try {
    const response = await fetch('/ui-api/preferences', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ autoDetect: autoDetect.checked }),
      signal: AbortSignal.timeout(5000),
    });
    const state = await response.json();
    if (!response.ok) throw new Error(state.error || 'Could not save the setting.');
    autoDetect.checked = state.account.autoDetect;
    storageError.hidden = true;
  } catch (error) {
    autoDetect.checked = !autoDetect.checked;
    storageError.hidden = false;
    storageError.textContent = error.message;
  } finally {
    savingSetting = false;
    autoDetect.disabled = false;
  }
});
syncHesitationPreference();
setInterval(syncHesitationPreference, 2000);

/** Render the same connected, offline and pending states as the reference popup. */
function renderConnection(state) {
  document.querySelector('.led').className = `led ${state === 'connected' ? 'on' : 'off'}`;
  document.querySelector('#connection-status').textContent = state === 'connected'
    ? 'Connected to backend'
    : `Backend offline (${API_URL})`;
}

/** Check the local backend, or hold a selected visual test state. */
async function checkConnection() {
  const scenario = new URLSearchParams(location.search).get('status') || 'live';
  if (scenario === 'checking') return;
  if (scenario === 'connected' || scenario === 'offline') {
    // HACK: Explicit preview scenarios allow UI testing without a running backend.
    renderConnection(scenario);
    return;
  }
  try {
    const response = await fetch('/preview-health', { signal: AbortSignal.timeout(4000) });
    renderConnection(response.ok ? 'connected' : 'offline');
  } catch {
    renderConnection('offline');
  }
}

checkConnection();
