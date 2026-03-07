import { useEffect, useState, useCallback } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useMissionStore } from '../../stores/missionStore.js';
import { useFleetStore } from '../../stores/fleetStore.js';
import { useUIStore } from '../../stores/uiStore.js';
import { listMissions, transitionMission, readMission } from '../lib/apiClient.js';
import PageSection from '../components/PageSection.jsx';

const STATE_COLORS = Object.freeze({
  IDLE: '#64748b',
  PLANNING: '#60a5fa',
  PLANNED: '#a78bfa',
  ACTIVE: '#34d399',
  PAUSED: '#fbbf24',
  ABORTED: '#f87171',
  COMPLETED: '#94a3b8',
});

const TERMINAL_STATES = new Set(['COMPLETED', 'ABORTED']);

function resolveRole(operator) {
  // Auth-bypass produces username==='anonymous' — grant PILOT access
  if (!operator || operator.username === 'anonymous') return 'PILOT';
  return operator.role || 'PILOT';
}

function canWrite(role) {
  return role === 'ADMIN' || role === 'PILOT';
}

export default function MissionsPage() {
  const missions = useMissionStore((state) => state.missions);
  const setMissions = useMissionStore((state) => state.setMissions);
  const upsertMission = useMissionStore((state) => state.upsertMission);
  const uploadedMissions = useMissionStore((state) => state.uploadedMissions);
  const uploadResults = useMissionStore((state) => state.uploadResults);
  const missionId = useMissionStore((state) => state.missionId);
  const showConfirm = useUIStore((state) => state.showConfirm);
  const drones = useFleetStore((state) => state.drones);

  const [selectedId, setSelectedId] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const { operator } = useOutletContext() || {};
  const role = resolveRole(operator);
  const writeAllowed = canWrite(role);

  // Fetch missions on mount and periodically
  const refresh = useCallback(async () => {
    try {
      const response = await listMissions();
      setMissions(response.items || []);
    } catch (err) {
      console.error('Failed to fetch missions:', err);
    }
  }, [setMissions]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  // Auto-select the active mission
  useEffect(() => {
    if (!selectedId && missionId) setSelectedId(missionId);
  }, [selectedId, missionId]);

  const selected = missions.find((m) => m.mission_id === selectedId) || null;

  async function applyTransition(mid, action, body = {}) {
    setActionError(null);
    setActionLoading(true);
    try {
      const updated = await transitionMission(mid, action, body);
      upsertMission(updated);
      // Sync global missionStore state if this is the active mission
      const store = useMissionStore.getState();
      if (store.missionId === mid || mid === selectedId) {
        store.setMissionState(updated.status);
        store.setMissionInfo({
          mission_type: updated.type,
          mission_state: updated.status,
          drone_count: new Set(updated.tasks?.flatMap((t) => t.drone_ids || []) || []).size,
          mission_config: updated.config || {},
        });
      }
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message || 'Action failed';
      setActionError(`${action} failed: ${detail}`);
    } finally {
      setActionLoading(false);
    }
  }

  function handleAbort(mid) {
    showConfirm({
      title: 'Abort Mission',
      body: `Abort mission ${mid}? This cannot be undone.`,
      droneIds: [],
      onConfirm: () => applyTransition(mid, 'abort', { reason: 'Operator abort from Missions page' }),
    });
  }

  return (
    <section className="v4-page">
      <header className="v4-page__header">
        <div>
          <p className="v4-eyebrow">Missions</p>
          <h1 className="v4-page__title">Mission Control</h1>
          <p className="v4-page__lede">
            Plan, execute, and review missions. Select a mission to see details and available actions.
          </p>
        </div>
        <span className="v4-inline-badge">{missions.length} mission(s)</span>
      </header>

      {/* Error banner */}
      {actionError && (
        <div style={{
          padding: '10px 16px', borderRadius: '8px', marginBottom: '16px',
          background: '#fee2e2', color: '#b91c1c', border: '1px solid #fca5a5',
          fontSize: '13px', fontWeight: 500, display: 'flex', justifyContent: 'space-between',
        }}>
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}>×</button>
        </div>
      )}

      {/* Selected mission detail + actions */}
      {selected && (
        <PageSection title={`Mission ${selected.mission_id}`} eyebrow="Selected">
          <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            {/* Detail card */}
            <div style={{ flex: '1 1 300px', minWidth: '280px' }}>
              <div className="v4-metric-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))' }}>
                <div className="v4-metric">
                  <span className="v4-metric__label">Type</span>
                  <span className="v4-metric__value">{selected.type}</span>
                </div>
                <div className="v4-metric">
                  <span className="v4-metric__label">State</span>
                  <span className="v4-metric__value" style={{ color: STATE_COLORS[selected.status] || '#94a3b8' }}>
                    {selected.status}
                  </span>
                </div>
                <div className="v4-metric">
                  <span className="v4-metric__label">Drones</span>
                  <span className="v4-metric__value">
                    {new Set(selected.tasks?.flatMap((t) => t.drone_ids || []) || []).size}
                  </span>
                </div>
                <div className="v4-metric">
                  <span className="v4-metric__label">Waypoints</span>
                  <span className="v4-metric__value">
                    {selected.tasks?.reduce((s, t) => s + (t.waypoints?.length || 0), 0) || 0}
                  </span>
                </div>
                <div className="v4-metric">
                  <span className="v4-metric__label">Upload</span>
                  <span className="v4-metric__value">
                    {uploadResults[selected.mission_id]
                      ? (uploadResults[selected.mission_id].result === 'OK' ? '✓ Uploaded' : `✕ ${uploadResults[selected.mission_id].detail || 'Failed'}`)
                      : (uploadedMissions.has(selected.mission_id) ? '✓ ACK' : '— Pending')}
                  </span>
                </div>
                <div className="v4-metric">
                  <span className="v4-metric__label">Created</span>
                  <span className="v4-metric__value">{new Date(selected.created_at || '').toLocaleString()}</span>
                </div>
              </div>
            </div>

            {/* Action buttons */}
            {!TERMINAL_STATES.has(selected.status) && writeAllowed && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '140px' }}>
                {selected.status === 'PLANNING' && (
                  <button
                    className="v4-mission-bar__btn v4-mission-bar__btn--primary"
                    onClick={() => applyTransition(selected.mission_id, 'plan')}
                    disabled={actionLoading}
                    style={{ padding: '8px 20px', borderRadius: '6px', fontWeight: 600, fontSize: '13px' }}
                  >
                    Finalize Plan
                  </button>
                )}
                {selected.status === 'PLANNED' && (
                  <button
                    className="v4-mission-bar__btn v4-mission-bar__btn--primary"
                    onClick={() => applyTransition(selected.mission_id, 'start')}
                    disabled={actionLoading || (uploadResults[selected.mission_id]?.result === 'FAILED')}
                    style={{ padding: '8px 20px', borderRadius: '6px', fontWeight: 600, fontSize: '13px' }}
                    title={uploadResults[selected.mission_id]?.result === 'FAILED'
                      ? `Upload failed: ${uploadResults[selected.mission_id]?.detail}`
                      : !uploadedMissions.has(selected.mission_id) ? 'Waypoints will be uploaded to the flight controller on start' : ''}
                  >
                    Start Mission
                  </button>
                )}
                {selected.status === 'ACTIVE' && (
                  <button
                    className="v4-mission-bar__btn"
                    onClick={() => applyTransition(selected.mission_id, 'pause')}
                    disabled={actionLoading}
                    style={{ padding: '8px 20px', borderRadius: '6px', fontWeight: 600, fontSize: '13px' }}
                  >
                    Pause
                  </button>
                )}
                {selected.status === 'PAUSED' && (
                  <button
                    className="v4-mission-bar__btn v4-mission-bar__btn--primary"
                    onClick={() => applyTransition(selected.mission_id, 'resume')}
                    disabled={actionLoading}
                    style={{ padding: '8px 20px', borderRadius: '6px', fontWeight: 600, fontSize: '13px' }}
                  >
                    Resume
                  </button>
                )}
                {selected.status === 'ACTIVE' && (
                  <button
                    className="v4-mission-bar__btn v4-mission-bar__btn--primary"
                    onClick={() => applyTransition(selected.mission_id, 'complete')}
                    disabled={actionLoading}
                    style={{ padding: '8px 20px', borderRadius: '6px', fontWeight: 600, fontSize: '13px' }}
                  >
                    Complete
                  </button>
                )}
                {['PLANNING', 'PLANNED', 'ACTIVE', 'PAUSED'].includes(selected.status) && (
                  <button
                    className="v4-mission-bar__btn v4-mission-bar__btn--danger"
                    onClick={() => handleAbort(selected.mission_id)}
                    disabled={actionLoading}
                    style={{ padding: '8px 20px', borderRadius: '6px', fontWeight: 600, fontSize: '13px' }}
                  >
                    Abort
                  </button>
                )}
              </div>
            )}
            {!writeAllowed && !TERMINAL_STATES.has(selected.status) && (
              <p style={{ fontSize: '12px', color: '#9ca3af', fontStyle: 'italic' }}>
                Read-only — {role} role cannot modify missions.
              </p>
            )}
          </div>

          {/* Upload failure warning */}
          {uploadResults[selected.mission_id]?.result === 'FAILED' && (
            <div style={{
              marginTop: '12px', padding: '10px 16px', borderRadius: '8px',
              background: '#fee2e2', color: '#b91c1c', border: '1px solid #fca5a5',
              fontSize: '13px', fontWeight: 500,
            }}>
              ⚠ Waypoint upload failed: {uploadResults[selected.mission_id]?.detail || 'Unknown error'}.
              Mission start is blocked until the issue is resolved.
            </div>
          )}
        </PageSection>
      )}

      {/* Mission table */}
      <PageSection title="All Missions" eyebrow="History">
        {missions.length === 0 ? (
          <p className="v4-muted">No missions yet. Create one in the Mission Builder.</p>
        ) : (
          <div className="v4-table-wrapper">
            <table className="v4-table">
              <thead>
                <tr>
                  <th>Mission</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Drones</th>
                  <th>Waypoints</th>
                  <th>Upload</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {missions.map((mission) => {
                  const droneCount = new Set(
                    mission.tasks?.flatMap((t) => t.drone_ids || []) || []
                  ).size;
                  const wpCount = mission.tasks?.reduce(
                    (sum, t) => sum + (t.waypoints?.length || 0),
                    0
                  ) || 0;
                  const created = new Date(mission.created_at || '').toLocaleString();
                  const isSelected = selectedId === mission.mission_id;
                  const ackResult = uploadResults[mission.mission_id];
                  return (
                    <tr
                      key={mission.mission_id}
                      onClick={() => setSelectedId(mission.mission_id)}
                      style={{
                        cursor: 'pointer',
                        background: isSelected ? 'rgba(59, 130, 246, 0.15)' : undefined,
                        borderLeft: isSelected ? '3px solid #3b82f6' : '3px solid transparent',
                      }}
                    >
                      <td className="v4-table__cell--mono">{mission.mission_id}</td>
                      <td>{mission.type}</td>
                      <td>
                        <span
                          style={{
                            display: 'inline-block', padding: '2px 10px', borderRadius: '12px',
                            fontSize: '12px', fontWeight: 600,
                            background: STATE_COLORS[mission.status] || '#64748b',
                            color: '#fff',
                          }}
                        >
                          {mission.status}
                        </span>
                      </td>
                      <td>{droneCount}</td>
                      <td>{wpCount}</td>
                      <td style={{ fontSize: '12px' }}>
                        {ackResult
                          ? (ackResult.result === 'OK'
                            ? <span style={{ color: '#059669' }}>✓ OK</span>
                            : <span style={{ color: '#dc2626' }}>✕ Failed</span>)
                          : (uploadedMissions.has(mission.mission_id)
                            ? <span style={{ color: '#059669' }}>✓</span>
                            : <span style={{ color: '#9ca3af' }}>—</span>)}
                      </td>
                      <td>{created}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </PageSection>
    </section>
  );
}
