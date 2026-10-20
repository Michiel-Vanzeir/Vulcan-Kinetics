import { useEffect, useState } from 'react';
import type { HealthResponse, Message } from '@/utils/messages';
import './style.css';

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [autoDetect, setAutoDetect] = useState(true);

  useEffect(() => {
    const message: Message = { type: 'WHOKNOWS_HEALTH' };
    browser.runtime.sendMessage(message).then(setHealth);
    browser.storage.local.get('autoDetect').then((v) => setAutoDetect(v.autoDetect !== false));
  }, []);

  const toggle = () => {
    const next = !autoDetect;
    setAutoDetect(next);
    browser.storage.local.set({ autoDetect: next });
  };

  return (
    <div className="popup">
      <header>
        <img className="logo" src="/whoknows-icon.png" alt="" />
        <div>
          <div className="wordmark">whoknows</div>
          <div className="tagline">Expertise finds you, not the other way around.</div>
        </div>
      </header>
      <main>
        <label className="row">
          <span>
            <b>Detect hesitation</b>
            <small>Flags pauses, rewrites and hedging</small>
          </span>
          <input type="checkbox" checked={autoDetect} onChange={toggle} />
        </label>
        <div className="status">
          <span className={`led ${health?.ok ? 'on' : health ? 'off' : ''}`} />
          {health ? (health.ok ? 'Connected to backend' : `Backend offline (${health.apiUrl})`) : 'Checking backend…'}
        </div>
      </main>
    </div>
  );
}
