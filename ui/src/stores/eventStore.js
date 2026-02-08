import { create } from 'zustand';

export const useEventStore = create((set, get) => ({
  events: [], // [{ type, message, timestamp }]

  addEvent: (ev) =>
    set((s) => ({
      events: [
        { ...ev, timestamp: ev.timestamp || ev.ts || Date.now() / 1000 },
        ...s.events,
      ].slice(0, 200),
    })),

  clear: () => set({ events: [] }),
  list: () => get().events,
}));
