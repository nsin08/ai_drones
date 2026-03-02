# POC-2 Quickstart

`poc2` is the real-hardware bridge and inspection layer for a single ArduPilot drone.

It currently contains:

- `drone_status.py`: read-only terminal telemetry and pre-arm checklist
- `drone_gateway.py`: MAVLink to MQTT bridge plus MQTT command ingress for `ARM`, `DISARM`, and `FORCE_ARM`
- `fault_smoke_test.py`: validates the existing fault models against a hardware snapshot or live telemetry

## Prerequisites

- Python 3.11+ recommended
- A reachable ArduPilot flight controller over serial (`COM3`, `COM6`, etc.)
- Mission Planner closed before connecting, otherwise the serial port will be busy
- An MQTT broker running if you use `drone_gateway.py` (default `localhost:1883`)

## Install

From the repo root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r poc2\requirements.txt
pip install pytest
```

`pytest` is not in `poc2/requirements.txt`, but you need it to run the unit tests.

## 1. Verify The Gateway Logic Offline

These tests do not need hardware or MQTT:

```powershell
python -m pytest poc2\tests\test_gateway.py -q
```

This validates:

- MAVLink message mapping into internal state
- MQTT telemetry payload shape
- multi-port CLI parsing
- per-session state isolation

## 2. Read Live Hardware Status

Use this first when you want a safe read-only hardware check:

```powershell
python poc2\drone_status.py
```

Useful variants:

```powershell
python poc2\drone_status.py --port COM6
python poc2\drone_status.py --port COM6 --baud 57600
```

What it does:

- auto-detects a serial port if `--port` is omitted
- waits for a MAVLink heartbeat
- shows live telemetry and a ready-to-fly checklist
- does not arm or send flight commands

## 3. Bridge Hardware Into Mission Control

This publishes hardware telemetry onto the existing MQTT topic shape used by the UI/backend:

```powershell
python poc2\drone_gateway.py
```

Useful variants:

```powershell
python poc2\drone_gateway.py --port COM6 --baud 57600 --drone-id HW-001
python poc2\drone_gateway.py --port COM6 --broker 127.0.0.1 --mqtt-port 1883 --hz 1
python poc2\drone_gateway.py --ports COM6:HW-001,COM3:HW-002 --broker 127.0.0.1
```

What it does:

- reads live MAVLink telemetry
- publishes to:
  - `fleet/<drone_id>/telemetry`
  - `fleet/<drone_id>/status`
- subscribes to:
  - `fleet/<drone_id>/command`
- executes:
  - `ARM`
  - `DISARM`
  - `FORCE_ARM`
- publishes acknowledgements to:
  - `fleet/system/command_ack`
- uses `HW-*` IDs so the UI can distinguish hardware-origin drones
- rejects unsupported verbs

## 4. Run Fault Smoke Testing

Static snapshot mode:

```powershell
python poc2\fault_smoke_test.py
```

Live hardware mode:

```powershell
python poc2\fault_smoke_test.py --live --port COM6 --baud 57600
```

Skip writing the report file:

```powershell
python poc2\fault_smoke_test.py --live --port COM6 --baud 57600 --no-report
```

By default, the report is written under `.context/reports/`.

## Typical Workflow

1. Run `python -m pytest poc2\tests\test_gateway.py -q`
2. Run `python poc2\drone_status.py --port COM6`
3. If telemetry looks healthy, run `python poc2\drone_gateway.py --port COM6 --drone-id HW-001`
4. Open Mission Control and confirm the hardware drone appears via MQTT
5. Optionally run `python poc2\fault_smoke_test.py --live --port COM6`

## Troubleshooting

- `pymavlink not installed`: reinstall with `pip install -r poc2\requirements.txt`
- Serial port busy: close Mission Planner or any other ground-station tool using the same COM port
- No MQTT updates in Mission Control: confirm the broker is running and that `--broker` / `--mqtt-port` match the active stack
- Hardware not auto-detected: pass `--port COMx` explicitly

## Scope Notes

- `poc2` now supports first-command hardware control only: `ARM`, `DISARM`, and `FORCE_ARM`
- broader command execution is still intentionally out of scope until this narrow hardware path is validated
- it complements the existing Mission Control stack by feeding hardware telemetry into the existing MQTT contract and consuming the same command topic shape
