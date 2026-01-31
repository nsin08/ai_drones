# 13) Demo Runbook (Windows, No Drones)

## 13.1 Start MQTT broker
1) Open PowerShell
2) cd ops
3) docker compose up -d

## 13.2 Start mock fleet pipeline
1) Open a new PowerShell
2) cd sim
3) python -m venv .venv
4) .venv\Scripts\activate
5) pip install -r requirements.txt

## 13.3 Start raw fleet simulator (12 drones)
1) python fleet_simulator.py --broker localhost --drones 12 --hz 1

## 13.4 Start fault injector (adds RF/GNSS/EKF/battery/thrust symptoms)
1) python fault_injector.py --broker localhost --config config.example.json

## 13.5 Start group planner
1) python group_planner.py --broker localhost

## 13.6 Start rules AI (recommendations)
1) python simple_rules_ai.py --broker localhost

## 13.7 Create group + roles (publish retained config)
Use any MQTT client (e.g., mqtt.cool test client) to publish:

A) Group members (retain=true):
Topic: fleet/groups/G01/members
Payload:
{"groupId":"G01","ts":"2026-01-31T00:00:00Z","members":["D001","D002","D003","D004","D005"]}

B) Roles (retain=true):
fleet/D001/role -> {"droneId":"D001","role":"LEADER"}
fleet/D002/role -> {"droneId":"D002","role":"POINT_MAN"}
fleet/D003/role -> {"droneId":"D003","role":"WINGMAN"}
fleet/D004/role -> {"droneId":"D004","role":"SCOUT"}
fleet/D005/role -> {"droneId":"D005","role":"RELAY"}

## 13.8 Run a mission intent (publish retain=false)
Publish PATROL intent to:
- fleet/groups/G01/intent

Use the example from docs/12_example_intents.md

## 13.9 Observe outputs
Subscribe to:
- fleet/groups/G01/plan/<intentId>
- fleet/D00x/plan/<intentId>
- fleet/D00x/ai/recommendation
- fleet/D00x/telemetry
- fleet/D00x/events
