import { useFleetStore } from '../stores/fleetStore';
import { useMissionStore } from '../stores/missionStore';
import { useUIStore } from '../stores/uiStore';
import { pauseMission, resumeMission, abortMission } from '../api';
import { Activity, Wifi } from 'lucide-react';

const STATE_COLORS = {
  IDLE: '#64748b', PLANNING: '#60a5fa', PLANNED: '#a78bfa',
  ACTIVE: '#34d399', PAUSED: '#fbbf24', ABORTED: '#f87171', COMPLETED: '#94a3b8',
};

export default function TopBar() {
  const drones = useFleetStore((s) => s.drones);
  const { missionType, missionState } = useMissionStore();
  const showConfirm = useUIStore((s) => s.showConfirm);
  const count = Object.keys(drones).length;
  const active = Object.values(drones).filter((d) => d.status === 'ACTIVE').length;

  const handlePause = async () => {
    try {
      await pauseMission();
    } catch (e) {
      console.error('Pause failed', e);
    }
  };

  const handleResume = async () => {
    try {
      await resumeMission();
    } catch (e) {
      console.error('Resume failed', e);
    }
  };

  const handleAbort = () => {
    showConfirm({
      title: 'Abort Mission',
      body: 'Abort the current mission? All drones will be commanded to RETURN.',
      droneIds: [],
      onConfirm: async () => {
        try {
          await abortMission();
        } catch (e) {
          console.error('Abort failed', e);
        }
      },
    });
  };

  return (
    <div className="topbar">
      <span className="topbar__title">MISSION CONTROL v3</span>

      <span className="topbar__state" style={{ background: STATE_COLORS[missionState] || '#64748b', color: '#000' }}>
        {missionState}
      </span>

      {missionType && (
        <span className="topbar__stat">
          Mission: <b>{missionType}</b>
        </span>
      )}

      <span className="topbar__stat">
        <Activity size={12} style={{ verticalAlign: 'middle' }} />{' '}
        <b>{active}</b>/{count} drones
      </span>

      <span className="topbar__stat">
        <Wifi size={12} style={{ verticalAlign: 'middle' }} /> MQTT
      </span>

      <div className="topbar__actions">
        {missionState === 'ACTIVE' && (
          <>
            <button className="topbar__btn topbar__btn--pause" onClick={handlePause}>
              Pause
            </button>
            <button className="topbar__btn topbar__btn--abort" onClick={handleAbort}>
              Abort
            </button>
          </>
        )}
        {missionState === 'PAUSED' && (
          <button className="topbar__btn topbar__btn--pause" onClick={handleResume}>
            Resume
          </button>
        )}
      </div>
    </div>
  );
}
