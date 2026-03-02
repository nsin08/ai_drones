import { useDeferredValue } from 'react';
import { useFleetStore } from '../../stores/fleetStore.js';
import PageSection from '../components/PageSection.jsx';

function normalizeHealth(drone) {
  const status = (drone.health_status || '').toUpperCase();
  if (status === 'GREEN' || status === 'YELLOW' || status === 'RED') {
    return status;
  }
  const ageSeconds = Math.max(0, (Date.now() / 1000) - (drone.last_seen || 0));
  if (ageSeconds > 30) {
    return 'GREY';
  }
  if ((drone.battery_pct ?? 0) >= 70) {
    return 'GREEN';
  }
  if ((drone.battery_pct ?? 0) >= 30) {
    return 'YELLOW';
  }
  return 'RED';
}

export default function FleetPage() {
  const dronesById = useFleetStore((state) => state.drones);
  const deferredDrones = useDeferredValue(
    Object.values(dronesById).sort((left, right) => left.drone_id.localeCompare(right.drone_id)),
  );

  const summary = deferredDrones.reduce(
    (totals, drone) => {
      const health = normalizeHealth(drone);
      if (health === 'GREEN') totals.green += 1;
      else if (health === 'YELLOW') totals.yellow += 1;
      else if (health === 'RED') totals.red += 1;
      else totals.offline += 1;
      return totals;
    },
    { green: 0, yellow: 0, red: 0, offline: 0 },
  );

  return (
    <section className="v4-page">
      <header className="v4-page__header">
        <div>
          <p className="v4-eyebrow">Fleet</p>
          <h1 className="v4-page__title">Fleet Health</h1>
          <p className="v4-page__lede">
            Live readiness stays visible while health scoring and backend aggregation move behind the v4 API.
          </p>
        </div>
        <span className="v4-inline-badge">{deferredDrones.length} tracked drones</span>
      </header>

      <PageSection title="Fleet Summary" eyebrow="Health Bands">
        <div className="v4-metric-grid">
          <div className="v4-metric">
            <span className="v4-metric__label">Green</span>
            <span className="v4-metric__value">{summary.green}</span>
          </div>
          <div className="v4-metric">
            <span className="v4-metric__label">Yellow</span>
            <span className="v4-metric__value">{summary.yellow}</span>
          </div>
          <div className="v4-metric">
            <span className="v4-metric__label">Red</span>
            <span className="v4-metric__value">{summary.red}</span>
          </div>
          <div className="v4-metric">
            <span className="v4-metric__label">Offline</span>
            <span className="v4-metric__value">{summary.offline}</span>
          </div>
        </div>
      </PageSection>

      <PageSection title="Drone Readiness" eyebrow="Preflight Snapshot">
        <div className="v4-table-wrap">
          <table className="v4-table">
            <thead>
              <tr>
                <th>Drone</th>
                <th>Health</th>
                <th>Battery</th>
                <th>GPS</th>
                <th>Mode</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {deferredDrones.length === 0 && (
                <tr>
                  <td colSpan="6" className="v4-empty">No fleet telemetry loaded yet.</td>
                </tr>
              )}
              {deferredDrones.map((drone) => {
                const health = normalizeHealth(drone);
                const className = `v4-status v4-status--${health.toLowerCase()}`;

                return (
                  <tr key={drone.drone_id}>
                    <td>{drone.drone_id}</td>
                    <td className={className}>{health}</td>
                    <td>{Math.round(drone.battery_pct ?? 0)}%</td>
                    <td>{drone.gps_sats ?? '-'}</td>
                    <td>{drone.mode || 'UNKNOWN'}</td>
                    <td>{drone.source || 'UNSPECIFIED'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </PageSection>
    </section>
  );
}
