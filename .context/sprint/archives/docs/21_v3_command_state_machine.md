# V3 Command State Machine

**Last Updated:** February 7, 2026  
**Scope:** Defines command lifecycle states, timeouts, and retries for Mission Control.

---

## 1) State Definitions

```
REQUESTED -> SENT -> ACKED -> COMPLETED
             |        |
             |        +-> FAILED
             |
             +-> TIMED_OUT
```

**REQUESTED**
- UI action accepted.
- Command object created with `cmd_id` (and `cmd_group_id` for bulk).

**SENT**
- Command published to MQTT `fleet/{drone_id}/command`.

**ACKED**
- ACK received on `fleet/system/command_ack`.
- ACK contains `result`: SUCCESS or FAILED.

**COMPLETED**
- SUCCESS acked and reflected in UI state (mode/role/mission updated).

**FAILED**
- ACK with result FAILED (or error from backend).

**TIMED_OUT**
- No ACK within `ACK_TIMEOUT_SEC`.

---

## 2) Ownership

**Backend owns timeouts and retries.**  
UI shows pending status but defers to backend status updates.

---

## 3) Timeout Policy

- Default `ACK_TIMEOUT_SEC`: 10 seconds
- Configurable via env in Mission Control backend
- On timeout:
  - Mark command as `TIMED_OUT`
  - Emit Socket.IO event `command_ack` with `result=TIMEOUT`

**Late ACK handling**
- If an ACK arrives after timeout:
  - Backend emits `command_ack` with `result=SUCCESS` or `FAILED` and `late=true`.
  - UI shows the command as **COMPLETED_LATE** (or FAILED_LATE) and keeps a warning badge.

---

## 4) Retry Policy

- No automatic retry (demo safety).
- Operator can click "Retry" to reissue the command.
- Bulk retries reuse the same `cmd_group_id` and new `cmd_id` per drone.
