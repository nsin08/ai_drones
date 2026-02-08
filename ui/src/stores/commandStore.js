import { create } from 'zustand';

export const useCommandStore = create((set, get) => ({
  commands: {}, // { [cmd_id]: { cmd_id, drone_id, command, result, late, timestamp, ... } }

  upsertCommand: (data) => {
    const id = data.cmd_id || data.id;
    if (!id) return;
    const normalized = {
      ...data,
      id,
      cmd_id: data.cmd_id || id,
      droneId: data.droneId ?? data.drone_id,
    };
    set((s) => ({
      commands: {
        ...s.commands,
        [id]: { ...(s.commands[id] || {}), ...normalized },
      },
    }));
  },

  removeCommand: (id) =>
    set((s) => {
      const { [id]: _, ...rest } = s.commands;
      return { commands: rest };
    }),

  clearOld: (maxAgeSec = 120) => {
    const now = Date.now() / 1000;
    set((s) => {
      const kept = {};
      Object.entries(s.commands).forEach(([k, v]) => {
        if (now - (v.timestamp || 0) < maxAgeSec) kept[k] = v;
      });
      return { commands: kept };
    });
  },

  /** Sorted newest-first */
  commandList: () =>
    Object.values(get().commands).sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0)),
}));
