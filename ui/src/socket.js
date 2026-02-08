import { io } from 'socket.io-client';
import { useFleetStore } from './stores/fleetStore';
import { useCommandStore } from './stores/commandStore';
import { useMissionStore } from './stores/missionStore';
import { useEventStore } from './stores/eventStore';
import { fetchInventory, fetchMissions, fetchSnapshot } from './api';

let socket = null;

export function getSocket() {
  if (!socket) {
    socket = io('/', {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });

    socket.on('connect', async () => {
      console.log('[WS] connected', socket.id);
      useEventStore.getState().addEvent({ type: 'SYSTEM', message: 'Connected to Mission Control' });
      // Reconnection strategy per API contract (section 4)
      try {
        const [inv, mis, snap] = await Promise.all([
          fetchInventory(),
          fetchMissions(),
          fetchSnapshot().catch(() => null),
        ]);
        const invList = inv?.items || inv?.drones || [];
        if (invList.length) {
          invList.forEach((d) => useFleetStore.getState().upsertDrone(d));
        }
        if (mis) useMissionStore.getState().setMissionInfo(mis);
        if (snap) {
          const snapList = snap.items || snap.drones || [];
          if (snapList.length) snapList.forEach((d) => useFleetStore.getState().upsertDrone(d));
          if (snap.commands) snap.commands.forEach((c) => useCommandStore.getState().upsertCommand(c));
          if (snap.events) snap.events.forEach((e) => useEventStore.getState().addEvent(e));
          if (snap.mission) useMissionStore.getState().setMissionInfo(snap.mission);
        }
      } catch (e) {
        console.warn('[WS] reconnect fetch failed', e);
      }
    });

    socket.on('disconnect', () => {
      console.log('[WS] disconnected');
      useEventStore.getState().addEvent({ type: 'SYSTEM', message: 'Disconnected' });
    });

    socket.on('telemetry_update', (data) => {
      useFleetStore.getState().upsertDrone(data);
    });

    socket.on('command_ack', (data) => {
      useCommandStore.getState().upsertCommand({
        ...data,
        id: data.cmd_id,
        droneId: data.drone_id,
        ackAt: Date.now(),
        timestamp: Date.now() / 1000,
      });
    });

    socket.on('mission_changed', (data) => {
      useMissionStore.getState().setMissionInfo(data);
      useEventStore.getState().addEvent({
        type: 'MISSION',
        message: `Mission -> ${data.mission_state || data.mission_type}`,
      });
    });

    socket.on('leader_election', (data) => {
      useEventStore.getState().addEvent({
        type: 'LEADER',
        message: `Leader elected: ${data.leader_id} (${data.reason})`,
      });
    });

    socket.on('command_requested', (data) => {
      useCommandStore.getState().upsertCommand({
        ...data,
        id: data.cmd_id,
        command: data.command,
        droneId: data.drone_id,
        status: 'REQUESTED',
        sentAt: Date.now(),
        timestamp: Date.now() / 1000,
      });
    });

    socket.on('event', (data) => {
      useEventStore.getState().addEvent(data);
    });
  }
  return socket;
}
