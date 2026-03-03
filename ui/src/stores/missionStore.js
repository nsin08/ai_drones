import { create } from 'zustand';

export const useMissionStore = create((set) => ({
  missionType: null,       // PATROL | PERIMETER | ESCORT
  missionState: 'IDLE',    // IDLE|PLANNING|PLANNED|ACTIVE|PAUSED|ABORTED|COMPLETED
  missionId: null,
  availableMissions: ['PATROL', 'PERIMETER', 'ESCORT'],
  missionConfig: {},
  droneCount: 0,
  homeBase: null,
  selectingHomeBase: false,

  // Planning state
  planWaypoints: [],       // [{lat,lon,alt_m}]
  planGeofence: [],        // [{lat,lon}]
  planAssetRoute: [],      // [{lat,lon}]
  planFormation: { shape: 'BOX', spacing_m: 30 },

  // Fetched mission history
  missions: [],            // [{mission_id, type, status, tasks, created_at, ...}]
  uploadedMissions: new Set(), // mission_ids that have been ACK'd by drones

  setMissionType: (t) => set({ missionType: t, missionState: 'PLANNING' }),
  setMissionState: (s) => set({ missionState: s }),
  setMissionId: (id) => set({ missionId: id }),
  setHomeBase: (hb) => set({ homeBase: hb }),
  setSelectingHomeBase: (v) => set({ selectingHomeBase: v }),
  setMissions: (m) => set({ missions: m }),
  addUploadedMission: (missionId) => set((state) => {
    const updated = new Set(state.uploadedMissions);
    updated.add(missionId);
    return { uploadedMissions: updated };
  }),
  isMissionUploaded: (missionId) => get().uploadedMissions.has(missionId),

  setMissionInfo: (data) =>
    set((prev) => ({
      missionType: data.mission_type ?? data.current_mission ?? prev.missionType,
      missionState: data.mission_state ?? prev.missionState,
      droneCount: data.drone_count ?? prev.droneCount,
      availableMissions: data.available_missions ?? prev.availableMissions,
      missionConfig: data.mission_config ?? prev.missionConfig,
    })),

  setPlanWaypoints: (w) => set({ planWaypoints: w }),
  addPlanWaypoint: (wp) => set((s) => ({ planWaypoints: [...s.planWaypoints, wp] })),
  removePlanWaypoint: (i) =>
    set((s) => ({ planWaypoints: s.planWaypoints.filter((_, idx) => idx !== i) })),

  setPlanGeofence: (g) => set({ planGeofence: g }),
  setPlanAssetRoute: (r) => set({ planAssetRoute: r }),
  setPlanFormation: (f) => set((s) => ({ planFormation: { ...s.planFormation, ...f } })),

  resetPlan: () =>
    set({
      missionState: 'IDLE',
      missionId: null,
      planWaypoints: [],
      planGeofence: [],
      planAssetRoute: [],
    }),
}));
