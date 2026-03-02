import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { V4_ENVIRONMENT, V4_NAV_ITEMS } from './constants';

const DEFAULT_SERVICE_STATUS = {
  mqtt: false,
  database: false,
  inventory: false,
  environment: V4_ENVIRONMENT,
};

const POLL_INTERVAL_MS = 5000;

function statusLabel(connected, label) {
  return `${label}: ${connected ? 'Connected' : 'Pending'}`;
}

async function fetchServiceStatus() {
  const res = await fetch('/api/health');
  if (!res.ok) throw new Error('health check failed');
  const data = await res.json();
  return {
    mqtt: data.mqtt_connected ?? false,
    inventory: data.inventory_available ?? false,
    // If the API responds the DB is reachable (backend requires DB on every request)
    database: true,
  };
}

export default function AppShell() {
  const [serviceStatus, setServiceStatus] = useState(DEFAULT_SERVICE_STATUS);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const status = await fetchServiceStatus();
        if (!cancelled) setServiceStatus((prev) => ({ ...prev, ...status }));
      } catch {
        if (!cancelled) setServiceStatus((prev) => ({ ...prev, database: false }));
      }
    }

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="v4-shell">
      <header className="v4-topbar">
        <div className="v4-topbar__brand">
          <span className="v4-topbar__eyebrow">Mission Control</span>
          <span className="v4-topbar__title">v4 Foundation</span>
        </div>

        <nav className="v4-topbar__nav" aria-label="Primary">
          {V4_NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive ? 'v4-topbar__link v4-topbar__link--active' : 'v4-topbar__link'
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="v4-topbar__status">
          <span className="v4-badge">Env {serviceStatus.environment}</span>
          <span className="v4-status-pill">{statusLabel(serviceStatus.mqtt, 'MQTT')}</span>
          <span className="v4-status-pill">{statusLabel(serviceStatus.database, 'DB')}</span>
          <span className="v4-status-pill">{statusLabel(serviceStatus.inventory, 'Inventory')}</span>
        </div>
      </header>

      <main className="v4-shell__content">
        <Outlet />
      </main>
    </div>
  );
}
