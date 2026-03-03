const SESSION_STORAGE_KEY = 'mc_v4_session';
const LEGACY_TOKEN_KEYS = Object.freeze(['mc_v4_access_token', 'mc_v4_token']);

function listStores() {
  if (typeof window === 'undefined') return [];
  return [window.localStorage, window.sessionStorage];
}

function readStorageValue(storage, key) {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function removeStorageValue(storage, key) {
  try {
    storage.removeItem(key);
  } catch {
    // Ignore storage failures and proceed with the best-effort cleanup.
  }
}

function writeStorageValue(storage, key, value) {
  try {
    storage.setItem(key, value);
  } catch {
    // Ignore storage failures; the UI still functions for the current tab.
  }
}

function sanitizeSession(session = {}) {
  return {
    accessToken: session.accessToken || null,
    operatorId: session.operatorId || null,
    username: session.username || null,
    role: session.role || null,
    allowedDrones: Array.isArray(session.allowedDrones) ? session.allowedDrones : [],
  };
}

function detectStorage() {
  const stores = listStores();
  if (stores.length === 0) return null;

  const localValue = readStorageValue(stores[0], SESSION_STORAGE_KEY);
  if (localValue) return stores[0];

  const sessionValue = readStorageValue(stores[1], SESSION_STORAGE_KEY);
  if (sessionValue) return stores[1];

  return stores[0];
}

export function readStoredSession() {
  const stores = listStores();
  for (const storage of stores) {
    const raw = readStorageValue(storage, SESSION_STORAGE_KEY);
    if (!raw) continue;
    try {
      return sanitizeSession(JSON.parse(raw));
    } catch {
      removeStorageValue(storage, SESSION_STORAGE_KEY);
    }
  }

  for (const storage of stores) {
    for (const key of LEGACY_TOKEN_KEYS) {
      const token = readStorageValue(storage, key);
      if (token) return sanitizeSession({ accessToken: token });
    }
  }

  return null;
}

export function writeStoredSession(session, target = 'local') {
  const stores = listStores();
  if (stores.length === 0) return null;

  const value = sanitizeSession(session);
  const storage = target === 'session' ? stores[1] : stores[0];
  const otherStorage = target === 'session' ? stores[0] : stores[1];

  writeStorageValue(storage, SESSION_STORAGE_KEY, JSON.stringify(value));
  removeStorageValue(otherStorage, SESSION_STORAGE_KEY);

  LEGACY_TOKEN_KEYS.forEach((key) => {
    if (value.accessToken) {
      writeStorageValue(storage, key, value.accessToken);
    } else {
      removeStorageValue(storage, key);
    }
    removeStorageValue(otherStorage, key);
  });

  return value;
}

export function mergeStoredSession(partial) {
  const existing = readStoredSession() || {};
  if (typeof window === 'undefined') return sanitizeSession({ ...existing, ...partial });
  const storage = detectStorage() === window.sessionStorage ? 'session' : 'local';
  return writeStoredSession({ ...existing, ...partial }, storage);
}

export function clearStoredSession() {
  listStores().forEach((storage) => {
    removeStorageValue(storage, SESSION_STORAGE_KEY);
    LEGACY_TOKEN_KEYS.forEach((key) => removeStorageValue(storage, key));
  });
}

export function getAccessToken() {
  return readStoredSession()?.accessToken || null;
}
