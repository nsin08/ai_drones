export const V4_ENVIRONMENT = (import.meta.env.VITE_V4_ENVIRONMENT || 'SIM').toUpperCase();

export const V4_SAFETY_DEFAULTS = Object.freeze({
  BATTERY_ARM_MIN_PCT: 10,
  GPS_ARM_MIN_SATS: 4,
  STALE_TIMEOUT_SEC: 30,
  COMMAND_ACK_TIMEOUT_SEC: 5,
  COMMAND_MAX_RETRIES: 3,
  COMMAND_RETRY_BACKOFF_SEC: [1, 2, 4],
});

export const V4_NAV_ITEMS = Object.freeze([
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/missions', label: 'Missions' },
  { to: '/fleet', label: 'Fleet' },
  { to: '/commands', label: 'Commands' },
  { to: '/settings', label: 'Settings' },
]);
