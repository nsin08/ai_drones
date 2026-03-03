import { useFleetStore } from '../../stores/fleetStore.js';
import { useMissionStore } from '../../stores/missionStore.js';
import { useUIStore } from '../../stores/uiStore.js';
import { missionStoreSnapshotFromList, transitionMission } from '../lib/apiClient.js';

const STATE_COLORS = Object.freeze({
  IDLE: '#64748b',
  PLANNING: '#60a5fa',
  PLANNED: '#a78bfa',
  ACTIVE: '#34d399',
  PAUSED: '#fbbf24',
  ABORTED: '#f87171',
  COMPLETED: '#94a3b8',
});

function assignedDroneCount(tasks = []) {
  const ids = new Set();
  tasks.forEach((task) => {
    (task?.drone_ids || []).forEach((droneId) => ids.add(droneId));
  });
  return ids.size;
}

export default function MissionBar() {
  const drones = useFleetStore((state) => state.drones);
  const missionId = useMissionStore((state) => state.missionId);
  const missionType = useMissionStore((state) => state.missionType);
  const missionState = useMissionStore((state) => state.missionState);
  const showConfirm = useUIStore((state) => state.showConfirm);

  const totalDrones = Object.keys(drones).length;
  const activeDrones = Object.values(drones).filter((drone) => drone.status === 'ACTIVE').length;

  async function applyTransition(action, body = {}) {
    if (!missionId) return;
    try {
      const mission = await transitionMission(missionId, action, body);
      const snapshot = missionStoreSnapshotFromList({ items: [mission] });
      if (snapshot) {
        useMissionStore.getState().setMissionId(snapshot.missionId);
        useMissionStore.getState().setMissionInfo(snapshot);
      } else {
        useMissionStore.getState().setMissionState(mission.status);
        useMissionStore.getState().setMissionId(mission.mission_id);
        useMissionStore.getState().setMissionInfo({
          mission_type: mission.type,
          current_mission: mission.type,
          mission_state: mission.status,
          mission_config: mission.config || {},
          drone_count: assignedDroneCount(mission.tasks),
        });
      }
    } catch (error) {
      console.error(`Mission ${action} failed`, error);
    }
  }

  function handleAbort() {
    if (!missionId) return;
    showConfirm({
      title: 'Abort Mission',
      body: 'Abort the current mission? The assigned drone will be commanded to return.',
      droneIds: [],
      onConfirm: async () => {
        await applyTransition('abort', { reason: 'Operator abort from dashboard' });
      },
    });
  }

  return (
    <div className="v4-mission-bar">
      <div className="v4-mission-bar__group">
        <span
          className="v4-mission-bar__state"
          style={{ background: STATE_COLORS[missionState] || STATE_COLORS.IDLE }}
        >
          {missionState}
        </span>
        <span className="v4-inline-badge">
          Mission: {missionType || 'Not selected'}
        </span>
        <span className="v4-inline-badge">
          Drones: {activeDrones}/{totalDrones}
        </span>
        {missionId && (
          <span className="v4-inline-badge">
            ID: {missionId}
          </span>
        )}
      </div>

      <div className="v4-mission-bar__actions">
        {missionState === 'PLANNED' && (
          <button
            type="button"
            className="v4-mission-bar__btn v4-mission-bar__btn--primary"
            onClick={() => applyTransition('start')}
            disabled={!missionId}
          >
            Start
          </button>
        )}
        {missionState === 'ACTIVE' && (
          <button
            type="button"
            className="v4-mission-bar__btn"
            onClick={() => applyTransition('pause')}
            disabled={!missionId}
          >
            Pause
          </button>
        )}
        {missionState === 'PAUSED' && (
          <button
            type="button"
            className="v4-mission-bar__btn"
            onClick={() => applyTransition('resume')}
            disabled={!missionId}
          >
            Resume
          </button>
        )}
        {['PLANNED', 'ACTIVE', 'PAUSED'].includes(missionState) && (
          <button
            type="button"
            className="v4-mission-bar__btn v4-mission-bar__btn--danger"
            onClick={handleAbort}
            disabled={!missionId}
          >
            Abort
          </button>
        )}
      </div>
    </div>
  );
}
