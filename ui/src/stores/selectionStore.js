import { create } from 'zustand';

export const useSelectionStore = create((set, get) => ({
  selected: new Set(),

  toggle: (id) =>
    set((s) => {
      const next = new Set(s.selected);
      next.has(id) ? next.delete(id) : next.add(id);
      return { selected: next };
    }),

  selectAll: (ids) => set({ selected: new Set(ids) }),
  clearSelection: () => set({ selected: new Set() }),

  isSelected: (id) => get().selected.has(id),
  count: () => get().selected.size,
  ids: () => [...get().selected],
}));
