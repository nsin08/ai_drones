import { create } from 'zustand';

export const useMissionStore = create((set) => ({
  missionType: null,       // PATROL | PERIMETER | ESCORT
  missionState: 'IDLE',    // IDLE|PLANNING|PLANNED|ACTIVE|PAUSED|ABORTED|COMPLETED
  missionId: null,
  availableMissions: ['PATROL', 'PERIMETER', 'ESCORT'],
  missionConfig: {},
  droneCount: 0,

  // Planning state
  planWaypoints: [],       // [{lat,lon,alt_m}]
  planGeofence: [],        // [{lat,lon}]
  planAssetRoute: [],      // [{lat,lon}]
  planFormation: { shape: 'BOX', spacing_m: 30 },

  setMissionType: (t) => set({ missionType: t, missionState: 'PLANNING' }),
  setMissionState: (s) => set({ missionState: s }),
  setMissionId: (id) => set({ missionId: id }),

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
