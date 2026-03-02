import { useMissionStore } from '../../stores/missionStore.js';
import PageSection from '../components/PageSection.jsx';

export default function MissionsPage() {
  const missionType = useMissionStore((state) => state.missionType);
  const missionState = useMissionStore((state) => state.missionState);
  const planWaypoints = useMissionStore((state) => state.planWaypoints);
  const planGeofence = useMissionStore((state) => state.planGeofence);
  const planFormation = useMissionStore((state) => state.planFormation);

  return (
    <section className="v4-page">
      <header className="v4-page__header">
        <div>
          <p className="v4-eyebrow">Missions</p>
          <h1 className="v4-page__title">Single Active Mission Planning</h1>
          <p className="v4-page__lede">
            The planner stays single-mission in W10 while the data model remains future-ready.
          </p>
        </div>
        <span className="v4-inline-badge">Execution stays single-mission</span>
      </header>

      <PageSection title="Active Mission Summary" eyebrow="Current State">
        <div className="v4-metric-grid">
          <div className="v4-metric">
            <span className="v4-metric__label">Mission</span>
            <span className="v4-metric__value">{missionType || 'Not selected'}</span>
          </div>
          <div className="v4-metric">
            <span className="v4-metric__label">State</span>
            <span className="v4-metric__value">{missionState}</span>
          </div>
          <div className="v4-metric">
            <span className="v4-metric__label">Waypoints</span>
            <span className="v4-metric__value">{planWaypoints.length}</span>
          </div>
          <div className="v4-metric">
            <span className="v4-metric__label">Geofence Points</span>
            <span className="v4-metric__value">{planGeofence.length}</span>
          </div>
        </div>
      </PageSection>

      <PageSection title="Mission Builder" eyebrow="Foundation Slice">
        <div className="v4-card-grid">
          <div className="v4-card">
            <h3 className="v4-card__title">Formation</h3>
            <p className="v4-card__meta">
              {planFormation.shape} with {planFormation.spacing_m}m spacing
            </p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">Waypoint Editing</h3>
            <p className="v4-card__meta">Map interactions remain the next functional extraction step.</p>
          </div>
          <div className="v4-card">
            <h3 className="v4-card__title">Templates</h3>
            <p className="v4-card__meta">Save/load hooks are reserved for the next sprint after persistence wiring.</p>
          </div>
        </div>
      </PageSection>

      <PageSection title="Mission History" eyebrow="Next Slice">
        <p className="v4-muted">
          History, validation, undo/redo, and template persistence are intentionally left as explicit follow-on work.
        </p>
      </PageSection>
    </section>
  );
}
