/**
 * Role -> color mapping used across map markers, roster, and charts.
 */
export const ROLE_COLORS = {
  LEADER: '#22d3ee',
  WINGMAN: '#60a5fa',
  SCOUT: '#e879f9',
  POINT_MAN: '#fbbf24',
  RELAY: '#fb923c',
  GUARD: '#34d399',
  CARGO: '#94a3b8',
  UNKNOWN: '#64748b',
};

export const MODE_COLORS = {
  AUTO: '#34d399',
  HOLD: '#fbbf24',
  RTL: '#fb923c',
  LAND: '#f87171',
  UNKNOWN: '#64748b',
};

export const STATUS_COLORS = {
  ACTIVE: '#34d399',
  DISABLED: '#f87171',
  UNKNOWN: '#64748b',
};

export const CMD_STATUS_COLORS = {
  REQUESTED: '#60a5fa',
  SENT: '#60a5fa',
  ACKED: '#34d399',
  COMPLETED: '#34d399',
  COMPLETED_LATE: '#fbbf24',
  FAILED: '#f87171',
  TIMED_OUT: '#fb923c',
  TIMEOUT: '#fb923c',
};

export const ROLES = ['LEADER', 'POINT_MAN', 'WINGMAN', 'SCOUT', 'RELAY', 'GUARD', 'CARGO'];

export const MISSION_TYPES = ['PATROL', 'PERIMETER', 'ESCORT'];

export const COMMANDS_NEED_CONFIRM = ['DISABLE', 'LAND', 'RETURN', 'RTL', 'CLEAR_MISSION'];

export const TILE_URL =
  import.meta.env.VITE_MAP_TILE_URL ||
  'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';

/** Default map center (New Delhi area for demo) */
export const MAP_CENTER = [28.6139, 77.209];
export const MAP_ZOOM = 14;

export const ACK_TIMEOUT_SEC = 10;
