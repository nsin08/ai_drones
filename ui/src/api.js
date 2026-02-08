import axios from 'axios';

const api = axios.create({ baseURL: '/api', timeout: 5000 });

/* -- Inventory -- */
export const fetchInventory = (params = {}) =>
  api.get('/inventory', { params }).then((r) => r.data);

export const fetchDrone = (id) =>
  api.get(`/inventory/${id}`).then((r) => r.data);

/* -- Missions -- */
export const fetchMissions = () => api.get('/missions').then((r) => r.data);

/* -- Home Base -- */
export const fetchHomeBase = () =>
  api.get('/home_base').then((r) => r.data);

export const setHomeBase = (body) =>
  api.post('/home_base', body).then((r) => r.data);

export const assignMission = (body) =>
  api.post('/mission/assign', body).then((r) => r.data);

export const planMission = (body) =>
  api.post('/mission/plan', body).then((r) => r.data);

export const startMission = (body) =>
  api.post('/mission/start', body).then((r) => r.data);

export const pauseMission = () =>
  api.post('/mission/pause').then((r) => r.data);

export const resumeMission = () =>
  api.post('/mission/resume').then((r) => r.data);

export const abortMission = () =>
  api.post('/mission/abort').then((r) => r.data);

export const resetMission = () =>
  api.post('/mission/reset').then((r) => r.data);

export const reassignLeader = (body) =>
  api.post('/mission/reassign_leader', body).then((r) => r.data);

/* -- Commands (single) -- */
export const sendCommand = (cmd, body) =>
  api.post(`/command/${cmd}`, body).then((r) => r.data);

/* -- Commands (bulk) -- */
export const sendBulkCommand = (cmd, body) =>
  api.post(`/command/bulk/${cmd}`, body).then((r) => r.data);

/* -- State snapshot (reconnect) -- */
export const fetchSnapshot = () =>
  api.get('/state/snapshot').then((r) => r.data);

export default api;
