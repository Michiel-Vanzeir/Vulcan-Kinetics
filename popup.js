/** Adapt the popup settings and health check for standalone browser testing. */
const API_URL = 'http://127.0.0.1:8000';
const autoDetect = document.querySelector('#auto-detect');
const storageError = document.querySelector('#storage-error');

try {
  autoDetect.checked = localStorage.getItem('autoDetect') !== 'false';
} catch {
  showStorageError();
}

autoDetect.addEventListener('change', () => {
  try {
    localStorage.setItem('autoDetect', String(autoDetect.checked));
  } catch {
    showStorageError();
  }
});

window.addEventListener('storage', event => {
  if (event.key === 'autoDetect') autoDetect.checked = event.newValue !== 'false';
  if (event.key === null) autoDetect.checked = true;
});

/** Explain when the browser prevents settings from surviving a reload. */
function showStorageError() {
  storageError.hidden = false;
  storageError.textContent = 'Browser storage is unavailable. This setting will not be saved.';
}

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
