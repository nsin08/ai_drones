# 14) mqtt.cool Steps (Exact Publish/Subscribe for Demo)

This doc assumes:
- Broker: localhost:1883 (change if needed)
- You run mqtt.cool Test Client in browser
- You already started:
  - fleet_simulator.py
  - fault_injector.py
  - group_planner.py
  - simple_rules_ai.py
  - asset_simulator.py (for ESCORT demo)

---

## 14.1 Connect mqtt.cool to your broker

1) Open the Test Client UI.
2) Connection settings:
   1. Host: `localhost`
   2. Port: `1883`
   3. ClientId: `mqttcool-operator-01` (any unique string)
   4. SSL/TLS: OFF (for local mosquitto demo)
3) Click **Connect**.

---

## 14.2 Subscribe to key topics (copy/paste)

1) Subscribe: `fleet/+/telemetry`
2) Subscribe: `fleet/+/events`
3) Subscribe: `fleet/+/ai/recommendation`
4) Subscribe: `fleet/groups/+/plan/+`
5) Subscribe: `fleet/groups/+/ai/recommendation`
6) Subscribe: `assets/+/pos`

(If mqtt.cool requires separate subscriptions, add them one-by-one.)

---

## 14.3 Publish Group Membership (retained)

Topic: `fleet/groups/G01/members`  
Retain: **true**  
QoS: 1  
Payload:
```json
{"groupId":"G01","ts":"2026-01-31T00:00:00Z","members":["D001","D002","D003","D004","D005"]}
