/**
 * Native WebSocket client for the v4 backend (/ws endpoint).
 *
 * The v4 backend is a plain FastAPI WebSocket (NOT socket.io).
 * Message envelope: { "event": "<name>", ...payload }
 *
 * Reconnects with exponential backoff (1s → 2s → 4s → … capped at 30s).
 */
import { useFleetStore } from './stores/fleetStore';
import { useCommandStore } from './stores/commandStore';
import { useMissionStore } from './stores/missionStore';
import { useEventStore } from './stores/eventStore';
import { listCommands, listMissions, missionStoreSnapshotFromList } from './v4/lib/apiClient';

let ws = null;
let reconnectDelay = 1000;
const MAX_DELAY = 30000;
let reconnectTimer = null;

function wsUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/ws`;
}

async function onConnected() {
  console.log('[WS] connected');
  reconnectDelay = 1000; // reset backoff
  useEventStore.getState().addEvent({ type: 'SYSTEM', message: 'Connected to Mission Control' });
  const [missionResult, commandResult] = await Promise.allSettled([
    listMissions(),
    listCommands({ limit: 20 }),
  ]);

  if (missionResult.status === 'fulfilled') {
    const snapshot = missionStoreSnapshotFromList(missionResult.value);
    if (snapshot) {
      useMissionStore.getState().setMissionId(snapshot.missionId);
      useMissionStore.getState().setMissionInfo(snapshot);
    }
  } else {
    console.warn('[WS] mission bootstrap failed', missionResult.reason);
  }

  if (commandResult.status === 'fulfilled') {
    (commandResult.value?.items || []).forEach((command) => {
      useCommandStore.getState().upsertCommand({
        ...command,
        timestamp: (Date.parse(command.created_at) || Date.now()) / 1000,
      });
    });
  } else {
    console.warn('[WS] command bootstrap failed', commandResult.reason);
  }
}

function dispatch(event, data) {
  switch (event) {
    case 'telemetry_update':
      useFleetStore.getState().upsertDrone(data);
      break;
    case 'command_ack':
      useCommandStore.getState().upsertCommand({
        ...data,
        id: data.cmd_id,
        droneId: data.drone_id,
        ackAt: Date.now(),
        timestamp: Date.now() / 1000,
      });
      break;
    case 'command_status':
      useCommandStore.getState().upsertCommand({
        ...data,
        id: data.cmd_id,
        droneId: data.drone_id,
        timestamp: Date.now() / 1000,
      });
      break;
    case 'mission_changed':
    case 'mission_state':
      useMissionStore.getState().setMissionInfo(data);
      if (data.mission_state === 'ACTIVE') useFleetStore.getState().resetTrails();
      useEventStore.getState().addEvent({
        type: 'MISSION',
        message: `Mission -> ${data.mission_state || data.mission_type}`,
      });
      break;
    case 'drone_health':
      // merge health fields into existing drone entry
      if (data.drone_id) useFleetStore.getState().upsertDrone(data);
      break;
    case 'leader_election':
      useEventStore.getState().addEvent({
        type: 'LEADER',
        message: `Leader elected: ${data.leader_id} (${data.reason})`,
      });
      break;
    case 'command_requested':
      useCommandStore.getState().upsertCommand({
        ...data,
        id: data.cmd_id,
        command: data.command,
        droneId: data.drone_id,
        status: 'REQUESTED',
        sentAt: Date.now(),
        timestamp: Date.now() / 1000,
      });
      break;
    case 'event':
    case 'system_alert':
      useEventStore.getState().addEvent(data);
      break;
    default:
      console.debug('[WS] unhandled event:', event, data);
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  console.log(`[WS] reconnecting in ${reconnectDelay}ms`);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, reconnectDelay);
  reconnectDelay = Math.min(reconnectDelay * 2, MAX_DELAY);
}

function connect() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return;

  ws = new WebSocket(wsUrl());

  ws.addEventListener('open', () => onConnected());

  ws.addEventListener('message', (e) => {
    try {
      const msg = JSON.parse(e.data);
      const { event, ...payload } = msg;
      if (event) dispatch(event, payload);
    } catch (err) {
      console.warn('[WS] bad message', e.data, err);
    }
  });

  ws.addEventListener('close', () => {
    console.log('[WS] disconnected');
    useEventStore.getState().addEvent({ type: 'SYSTEM', message: 'Disconnected' });
    scheduleReconnect();
  });

  ws.addEventListener('error', (err) => {
    console.warn('[WS] error', err);
    ws.close();
  });

  return ws;
}

export function getSocket() {
  if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
    connect();
  }
  return ws;
}
