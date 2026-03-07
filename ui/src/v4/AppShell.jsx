import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { V4_ENVIRONMENT, V4_NAV_ITEMS } from './constants';
import { getSocket } from '../socket';
import { clearStoredSession } from './auth/session.js';
import { readHealth, readMe } from './lib/apiClient.js';

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

function statusClass(connected) {
  return connected
    ? 'v4-status-pill v4-status-pill--connected'
    : 'v4-status-pill v4-status-pill--pending';
}

async function fetchServiceStatus() {
  const data = await readHealth();
  return {
    mqtt: data.mqtt_connected ?? false,
    inventory: data.inventory_available ?? false,
    // If the API responds the DB is reachable (backend requires DB on every request)
    database: true,
  };
}

export default function AppShell() {
  const navigate = useNavigate();
  const [serviceStatus, setServiceStatus] = useState(DEFAULT_SERVICE_STATUS);
  const [operator, setOperator] = useState(null);

  // Establish native WebSocket connection for real-time telemetry and events
  useEffect(() => { getSocket(); }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadOperator() {
      try {
        const identity = await readMe();
        if (!cancelled) setOperator(identity);
      } catch {
        if (!cancelled) setOperator(null);
      }
    }

    loadOperator();
    return () => {
      cancelled = true;
    };
  }, []);

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

  function handleLogout() {
    clearStoredSession();
    setOperator(null);
    navigate('/login', { replace: true });
  }

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
          <span className={statusClass(serviceStatus.mqtt)}>{statusLabel(serviceStatus.mqtt, 'MQTT')}</span>
          <span className={statusClass(serviceStatus.database)}>{statusLabel(serviceStatus.database, 'DB')}</span>
          <span className={statusClass(serviceStatus.inventory)}>{statusLabel(serviceStatus.inventory, 'Inventory')}</span>
          {operator && (
            <span className="v4-inline-badge">
              {operator.username === 'anonymous' ? 'Auth Bypass' : `${operator.username} (${operator.role})`}
            </span>
          )}
          {operator && operator.username !== 'anonymous' && (
            <button type="button" className="v4-topbar__logout" onClick={handleLogout}>
              Logout
            </button>
          )}
        </div>
      </header>

      <main className="v4-shell__content">
        <Outlet context={{ serviceStatus, operator }} />
      </main>
    </div>
  );
}
