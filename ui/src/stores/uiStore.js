import { create } from 'zustand';

export const useUIStore = create((set) => ({
  confirmDialog: null, // { title, body, droneIds, onConfirm }
  showConfirm: (dialog) => set({ confirmDialog: dialog }),
  hideConfirm: () => set({ confirmDialog: null }),

  filters: { role: '', status: '', search: '' },
  setFilter: (key, val) =>
    set((s) => ({ filters: { ...s.filters, [key]: val } })),

  bottomTab: 'timeline', // 'altitude' | 'battery' | 'timeline'
  setBottomTab: (t) => set({ bottomTab: t }),
}));
