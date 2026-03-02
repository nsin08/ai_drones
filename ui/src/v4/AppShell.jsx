import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { getSocket } from '../socket';
import { V4_ENVIRONMENT, V4_NAV_ITEMS } from './constants';

const DEFAULT_SERVICE_STATUS = {
  mqtt: false,
  database: false,
  inventory: false,
  environment: V4_ENVIRONMENT,
};

function statusLabel(connected, label) {
  return `${label}: ${connected ? 'Connected' : 'Pending'}`;
}

export default function AppShell() {
  const [serviceStatus, setServiceStatus] = useState(DEFAULT_SERVICE_STATUS);

  useEffect(() => {
    const socket = getSocket();
    const handleServiceStatus = (payload) => {
      setServiceStatus((current) => ({ ...current, ...payload }));
    };

    socket.on('service_status', handleServiceStatus);
    return () => {
      socket.off('service_status', handleServiceStatus);
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
