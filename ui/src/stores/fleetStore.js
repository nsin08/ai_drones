import { create } from 'zustand';

/**
 * Fleet store - holds per-drone telemetry + inventory merged state.
 * Trail capped at 100 points per drone.
 */
export const useFleetStore = create((set, get) => ({
  drones: {}, // { [drone_id]: { ...telemetry, trail: [{lat,lon,alt}] } }

  upsertDrone: (data) => {
    const id = data.drone_id;
    if (!id) return;
    set((s) => {
      const prev = s.drones[id] || {};
      const trail = prev.trail ? [...prev.trail] : [];
      const position = data.position || {};
      const lat = data.latitude ?? data.lat ?? position.lat ?? prev.latitude;
      const lon = data.longitude ?? data.lon ?? position.lon ?? prev.longitude;
      const alt = data.altitude_m ?? data.altitude ?? position.alt_m ?? prev.altitude_m ?? prev.altitude;
      if (lat != null && lon != null) {
        const last = trail[trail.length - 1];
        const dLat = last ? Math.abs(lat - last.lat) : 1;
        const dLon = last ? Math.abs(lon - last.lon) : 1;
        const moved = (dLat + dLon) > 0.00002; // ~2m
        if (!last || moved) {
          trail.push({ lat, lon, alt });
        }
        if (trail.length > 100) trail.splice(0, trail.length - 100);
      }
      const battery_pct = data.battery_pct ?? data.battery ?? prev.battery_pct ?? prev.battery ?? 0;
      const last_seen = data.last_seen ?? data.timestamp ?? Date.now() / 1000;
      return {
        drones: {
          ...s.drones,
          [id]: {
            ...prev,
            ...data,
            battery_pct,
            battery: battery_pct,
            latitude: lat,
            longitude: lon,
            altitude_m: alt,
            trail,
            last_seen,
          },
        },
      };
    });
  },

  removeDrone: (id) =>
    set((s) => {
      const { [id]: _, ...rest } = s.drones;
      return { drones: rest };
    }),

  clearAll: () => set({ drones: {} }),
  resetTrails: () =>
    set((s) => ({
      drones: Object.fromEntries(
        Object.entries(s.drones).map(([id, d]) => [id, { ...d, trail: [] }]),
      ),
    })),

  /** Get sorted list */
  droneList: () => Object.values(get().drones).sort((a, b) => (a.drone_id > b.drone_id ? 1 : -1)),
}));
