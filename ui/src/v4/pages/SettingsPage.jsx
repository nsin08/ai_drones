import { useOutletContext } from 'react-router-dom';
import PageSection from '../components/PageSection.jsx';
import { V4_ENVIRONMENT, V4_SAFETY_DEFAULTS } from '../constants.js';

function StatusDot({ connected }) {
  return (
    <span style={{
      display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%',
      background: connected ? '#34d399' : '#f87171', marginRight: '8px',
    }} />
  );
}

export default function SettingsPage() {
  const { serviceStatus = {}, operator = null } = useOutletContext() || {};

  return (
    <section className="v4-page">
      <header className="v4-page__header">
        <div>
          <p className="v4-eyebrow">Settings</p>
          <h1 className="v4-page__title">Deployment and Safety</h1>
          <p className="v4-page__lede">
            Live deployment health from the backend. Safety thresholds are pinned defaults.
          </p>
        </div>
        <span className="v4-inline-badge">Environment {V4_ENVIRONMENT}</span>
      </header>

      <PageSection title="Deployment Health" eyebrow="Live">
        <div className="v4-card-grid">
          <div className="v4-card">
            <h3 className="v4-card__title">Environment</h3>
            <p className="v4-card__meta">{serviceStatus.environment || V4_ENVIRONMENT}</p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">MQTT Broker</h3>
            <p className="v4-card__meta">
              <StatusDot connected={serviceStatus.mqtt} />
              {serviceStatus.mqtt ? 'Connected' : 'Disconnected'}
            </p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">Database</h3>
            <p className="v4-card__meta">
              <StatusDot connected={serviceStatus.database} />
              {serviceStatus.database ? 'Connected' : 'Disconnected'}
            </p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">Inventory Service</h3>
            <p className="v4-card__meta">
              <StatusDot connected={serviceStatus.inventory} />
              {serviceStatus.inventory ? 'Available' : 'Unavailable'}
            </p>
          </div>
        </div>
      </PageSection>

      {operator && (
        <PageSection title="Current Operator" eyebrow="Session">
          <div className="v4-card-grid">
            <div className="v4-card">
              <h3 className="v4-card__title">Username</h3>
              <p className="v4-card__meta">{operator.username || 'anonymous'}</p>
            </div>
            <div className="v4-card">
              <h3 className="v4-card__title">Role</h3>
              <p className="v4-card__meta">{operator.role || '—'}</p>
            </div>
            <div className="v4-card">
              <h3 className="v4-card__title">Operator ID</h3>
              <p className="v4-card__meta" style={{ fontSize: '12px' }}>{operator.operator_id || operator.id || '—'}</p>
            </div>
          </div>
        </PageSection>
      )}

      <PageSection title="Safety Thresholds" eyebrow="Pinned Defaults">
        <div className="v4-settings-grid">
          <div className="v4-card">
            <h3 className="v4-card__title">Battery arm minimum</h3>
            <p className="v4-card__meta">{V4_SAFETY_DEFAULTS.BATTERY_ARM_MIN_PCT}%</p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">GPS arm minimum</h3>
            <p className="v4-card__meta">{V4_SAFETY_DEFAULTS.GPS_ARM_MIN_SATS} satellites</p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">Stale timeout</h3>
            <p className="v4-card__meta">{V4_SAFETY_DEFAULTS.STALE_TIMEOUT_SEC}s</p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">Ack timeout</h3>
            <p className="v4-card__meta">{V4_SAFETY_DEFAULTS.COMMAND_ACK_TIMEOUT_SEC}s</p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">Max retries</h3>
            <p className="v4-card__meta">{V4_SAFETY_DEFAULTS.COMMAND_MAX_RETRIES}</p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">Retry backoff</h3>
            <p className="v4-card__meta">{V4_SAFETY_DEFAULTS.COMMAND_RETRY_BACKOFF_SEC.join('s, ')}s</p>
          </div>
        </div>
      </PageSection>
    </section>
  );
}
