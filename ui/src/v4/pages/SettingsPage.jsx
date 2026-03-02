import PageSection from '../components/PageSection.jsx';
import { V4_ENVIRONMENT, V4_SAFETY_DEFAULTS } from '../constants.js';

export default function SettingsPage() {
  return (
    <section className="v4-page">
      <header className="v4-page__header">
        <div>
          <p className="v4-eyebrow">Settings</p>
          <h1 className="v4-page__title">Deployment and Safety</h1>
          <p className="v4-page__lede">
            W10 keeps this page intentionally narrow: environment is read-only and safety values are normalized.
          </p>
        </div>
        <span className="v4-inline-badge">Environment {V4_ENVIRONMENT}</span>
      </header>

      <PageSection title="Deployment" eyebrow="Read Only">
        <div className="v4-card-grid">
          <div className="v4-card">
            <h3 className="v4-card__title">Environment</h3>
            <p className="v4-card__meta">{V4_ENVIRONMENT}</p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">MQTT</h3>
            <p className="v4-card__meta">Status will bind to the `service_status` stream.</p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">Database</h3>
            <p className="v4-card__meta">Persistence is scaffolded; live connectivity hooks are next.</p>
          </div>
        </div>
      </PageSection>

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
