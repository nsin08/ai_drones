import { useSelectionStore } from '../stores/selectionStore';
import { useUIStore } from '../stores/uiStore';
import { useCommandStore } from '../stores/commandStore';
import { useMissionStore } from '../stores/missionStore';
import { sendCommand, sendBulkCommand, reassignLeader } from '../api';
import { COMMANDS_NEED_CONFIRM, ROLES } from '../constants';
import { useFleetStore } from '../stores/fleetStore';
import { useState } from 'react';

export default function QuickActions() {
  const selected = useSelectionStore((s) => s.selected);
  const showConfirm = useUIStore((s) => s.showConfirm);
  const missionState = useMissionStore((s) => s.missionState);
  const drones = useFleetStore((s) => s.drones);
  const [applyAll, setApplyAll] = useState(false);
  const [newLeader, setNewLeader] = useState('');

  const dispatch = (cmd, extra = {}) => {
    const allIds = Object.values(drones).map((d) => d.drone_id);
    const ids = applyAll ? allIds : [...selected];
    if (!ids.length) return alert('Select drones first');

    const isBulk = ids.length > 1;
    const needsConfirm = COMMANDS_NEED_CONFIRM.includes(cmd) || isBulk;

    const doSend = async () => {
      try {
        if (isBulk) {
          await sendBulkCommand(cmd.toLowerCase(), { drone_ids: ids, ...extra });
        } else {
          await sendCommand(cmd.toLowerCase(), { drone_id: ids[0], ...extra });
        }
      } catch (e) {
        console.error(`${cmd} failed`, e);
      }
    };

    if (needsConfirm) {
      const effect = ['DISABLE', 'LAND'].includes(cmd) ? 'will disable/land the drones' :
        cmd === 'RETURN' ? 'will return drones to base' : 'will apply command';
      showConfirm({
        title: `Confirm ${cmd}`,
        body: `Send ${cmd} to ${ids.length} drone${ids.length > 1 ? 's' : ''}? This ${effect}.`,
        droneIds: ids,
        onConfirm: doSend,
      });
    } else {
      doSend();
    }
  };

  const handleReassign = async () => {
    if (!newLeader) return;
    try {
      await reassignLeader({
        mission_id: useMissionStore.getState().missionId || 'M001',
        new_leader_id: newLeader,
      });
      useMissionStore.getState().setMissionState('ACTIVE');
      setNewLeader('');
    } catch (e) {
      alert('Reassign failed: ' + (e.response?.data?.error || e.message));
    }
  };

  return (
    <div className="panel-section">
      <div className="panel-section__title">Quick Actions</div>
      <div className="qa-target">
        <span>Target:</span>
        <button
          className={`qa-target-btn ${!applyAll ? 'qa-target-btn--active' : ''}`}
          onClick={() => setApplyAll(false)}
        >
          Selected ({selected.size})
        </button>
        <button
          className={`qa-target-btn ${applyAll ? 'qa-target-btn--active' : ''}`}
          onClick={() => setApplyAll(true)}
        >
          Swarm ({Object.values(drones).length})
        </button>
      </div>
      <div className="quick-actions">
        <button className="qa-btn qa-btn--hold" onClick={() => dispatch('HOLD')}>HOLD</button>
        <button className="qa-btn qa-btn--return" onClick={() => dispatch('RETURN')}>RETURN</button>
        <button className="qa-btn qa-btn--disable" onClick={() => dispatch('DISABLE')}>DISABLE</button>
        <button className="qa-btn qa-btn--enable" onClick={() => dispatch('ENABLE')}>ENABLE</button>
        <button className="qa-btn qa-btn--arm" onClick={() => dispatch('ARM')}>ARM</button>
        <button className="qa-btn qa-btn--enable" onClick={() => dispatch('RESUME')}>RESUME</button>
      </div>

      {/* Leader reassign (shown when PAUSED) */}
      {missionState === 'PAUSED' && (
        <div style={{ marginTop: 10, padding: 8, background: 'rgba(251,191,36,0.1)', borderRadius: 6, border: '1px solid var(--accent-amber)' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--accent-amber)', marginBottom: 6 }}>
            Mission Paused - Reassign Leader
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <select value={newLeader} onChange={(e) => setNewLeader(e.target.value)} style={{ flex: 1 }}>
              <option value="">Select drone...</option>
              {Object.values(drones)
                .filter((d) => d.status === 'ACTIVE' && d.mode !== 'HOLD' && d.mode !== 'RTL')
                .map((d) => <option key={d.drone_id} value={d.drone_id}>{d.drone_id}</option>)}
            </select>
            <button className="qa-btn qa-btn--arm" onClick={handleReassign}>Assign</button>
          </div>
        </div>
      )}
    </div>
  );
}
