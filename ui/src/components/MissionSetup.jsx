import { useMissionStore } from '../stores/missionStore';
import { useSelectionStore } from '../stores/selectionStore';
import { useFleetStore } from '../stores/fleetStore';
import { MISSION_TYPES } from '../constants';
import { assignMission, planMission, startMission, resetMission } from '../api';

export default function MissionSetup() {
  const { missionType, missionState, planWaypoints, planGeofence, planAssetRoute, planFormation, homeBase, selectingHomeBase } = useMissionStore();
  const setType = useMissionStore((s) => s.setMissionType);
  const setId = useMissionStore((s) => s.setMissionId);
  const resetPlan = useMissionStore((s) => s.resetPlan);
  const setFormation = useMissionStore((s) => s.setPlanFormation);
  const setSelectingHomeBase = useMissionStore((s) => s.setSelectingHomeBase);
  const selectedIds = useSelectionStore((s) => s.ids);
  const drones = useFleetStore((s) => s.drones);

  const handlePlan = async () => {
    if (!missionType) return;
    const ids = selectedIds();
    if (!ids.length) return alert('Select drones first');

    // Step 1: assign drones + roles (preserve existing roles from roster)
    try {
      const roleMap = {};
      ids.forEach((id, i) => {
        const currentRole = drones[id]?.mission_role || drones[id]?.current_role;
        // Use existing role, or default to LEADER for first, WINGMAN for rest
        roleMap[id] = currentRole || (i === 0 ? 'LEADER' : 'WINGMAN');
      });
      const assignRes = await assignMission({ mission_type: missionType, drone_ids: ids, role_map: roleMap });
      if (assignRes.mission_id) setId(assignRes.mission_id);
    } catch (e) {
      alert('Assign failed: ' + (e.response?.data?.error || e.message));
      return;
    }

    // Step 2: plan mission
    const body = { mission_type: missionType };
    if (missionType === 'PATROL') {
      if (planWaypoints.length < 2) return alert('Add at least 2 waypoints on the map');
      body.waypoints = planWaypoints;
    } else if (missionType === 'PERIMETER') {
      if (planGeofence.length < 3) return alert('Draw a geofence polygon on the map');
      body.geofence = planGeofence;
    } else if (missionType === 'ESCORT') {
      if (planAssetRoute.length < 2) return alert('Draw an asset route on the map');
      body.asset_route = planAssetRoute;
      body.formation = planFormation;
    }

    try {
      await planMission(body);
    } catch (e) {
      alert('Plan failed: ' + (e.response?.data?.error || e.message));
    }
  };

  const handleStart = async () => {
    try {
      await startMission({});
    } catch (e) {
      alert('Start failed: ' + (e.response?.data?.error || e.message));
    }
  };

  const handleReset = async () => {
    try {
      await resetMission();
      resetPlan();
    } catch (e) {
      resetPlan(); // local reset anyway
    }
  };

  return (
    <div className="panel-section">
      <div className="panel-section__title">Mission Setup</div>

      <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
        Home Base: {homeBase?.lat?.toFixed(5)}, {homeBase?.lon?.toFixed(5)}
        <button
          style={{ marginLeft: 6, fontSize: '0.65rem', color: 'var(--accent-cyan)' }}
          onClick={() => setSelectingHomeBase(!selectingHomeBase)}
        >
          {selectingHomeBase ? 'Click map to set...' : 'Set Home Base'}
        </button>
      </div>

      <div className="mission-type-btns">
        {MISSION_TYPES.map((t) => (
          <button
            key={t}
            className={`mission-type-btn ${missionType === t ? 'mission-type-btn--active' : ''}`}
            onClick={() => setType(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {missionType === 'PATROL' && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
          Click map to add waypoints ({planWaypoints.length} added)
        </div>
      )}
      {missionType === 'PERIMETER' && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
          Click map to draw geofence polygon ({planGeofence.length} points)
        </div>
      )}
      {missionType === 'ESCORT' && (
        <>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
            Click map to draw asset route ({planAssetRoute.length} points)
          </div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 4 }}>
            <select value={planFormation.shape} onChange={(e) => setFormation({ shape: e.target.value })}
              style={{ flex: 1 }}>
              <option value="BOX">Box</option>
              <option value="LINE">Line</option>
              <option value="CIRCLE">Circle</option>
            </select>
            <input type="number" value={planFormation.spacing_m} min={5} max={200}
              style={{ width: 60 }}
              onChange={(e) => setFormation({ spacing_m: +e.target.value })} />
          </div>
        </>
      )}

      <div className="mission-actions">
        {missionState === 'PLANNING' && (
          <button className="mission-btn mission-btn--plan" onClick={handlePlan}>
            Plan
          </button>
        )}
        {missionState === 'PLANNED' && (
          <button className="mission-btn mission-btn--start" onClick={handleStart}>
            Start
          </button>
        )}
        {(missionState !== 'IDLE') && (
          <button className="mission-btn mission-btn--abort" onClick={handleReset}>
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
