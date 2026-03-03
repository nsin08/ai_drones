import axios from 'axios';
import { getAccessToken } from '../auth/session.js';

const STATUS_PRIORITY = Object.freeze({
  ACTIVE: 0,
  PAUSED: 1,
  PLANNED: 2,
  PLANNING: 3,
  COMPLETED: 4,
  ABORTED: 5,
});

const api = axios.create({
  baseURL: '/api',
  timeout: 5000,
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers = {
      ...(config.headers || {}),
      Authorization: `Bearer ${token}`,
    };
  }
  return config;
});

function missionPriority(mission) {
  const base = STATUS_PRIORITY[mission?.status] ?? 99;
  const updatedAt = Date.parse(mission?.updated_at || mission?.created_at || '') || 0;
  return [base, -updatedAt];
}

function compareMissionPriority(left, right) {
  const [leftBase, leftTime] = missionPriority(left);
  const [rightBase, rightTime] = missionPriority(right);
  if (leftBase !== rightBase) return leftBase - rightBase;
  return leftTime - rightTime;
}

function uniqueAssignedDroneCount(tasks = []) {
  const ids = new Set();
  tasks.forEach((task) => {
    (task?.drone_ids || []).forEach((droneId) => ids.add(droneId));
  });
  return ids.size;
}

export function missionStoreSnapshotFromList(response) {
  const items = response?.items || [];
  if (!items.length) return null;

  const selected = [...items].sort(compareMissionPriority)[0];
  return {
    missionId: selected.mission_id,
    mission_type: selected.type,
    current_mission: selected.type,
    mission_state: selected.status,
    drone_count: uniqueAssignedDroneCount(selected.tasks),
    mission_config: selected.config || {},
  };
}

export async function login(credentials) {
  const { data } = await api.post('/auth/token', credentials);
  return data;
}

export async function readMe() {
  const { data } = await api.get('/auth/me');
  return data;
}

export async function readHealth() {
  const { data } = await api.get('/health');
  return data;
}

export async function listFleetHealth() {
  const { data } = await api.get('/fleet/health');
  return data;
}

export async function listMissions(params = {}) {
  const { data } = await api.get('/missions', { params });
  return data;
}

export async function readMission(missionId) {
  const { data } = await api.get(`/missions/${missionId}`);
  return data;
}

export async function createMission(payload) {
  return api.post('/missions', payload);
}

export async function transitionMission(missionId, action, payload = {}) {
  const { data } = await api.post(`/missions/${missionId}/${action}`, payload);
  return data;
}

export async function listCommands(params = {}) {
  const { data } = await api.get('/commands', { params });
  return data;
}

export default api;
