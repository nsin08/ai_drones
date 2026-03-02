# MQTT Topic Taxonomy

## Telemetry & health (published by drone bridge or simulator)
- raw/fleet/<droneId>/telemetry          (simulator output)
- fleet/<droneId>/telemetry              (post fault-injection / normalized)
- fleet/<droneId>/health
- fleet/<droneId>/events

## Roles & grouping (published by orchestrator/planner)
- fleet/<droneId>/role
- fleet/groups/<groupId>/members         (retained)
- fleet/groups/<groupId>/status

## Commands & acks (mission control/planner publishes)
- fleet/<droneId>/command
- fleet/system/command_ack

## Intents (operator or orchestrator publishes)
- fleet/intents/<intentId>
- fleet/groups/<groupId>/intent

## Plans (planner publishes)
- fleet/<droneId>/plan/<intentId>
- fleet/groups/<groupId>/plan/<intentId>

## AI recommendations (AI publishes)
- fleet/<droneId>/ai/recommendation
- fleet/groups/<groupId>/ai/recommendation
- fleet/ai/recommendation

## Acks (operator/system publishes)
- fleet/acks/<intentId>
- fleet/acks/<recommendationId>

## Inventory (inventory service publishes)
- fleet/system/inventory
- fleet/system/inventory/<droneId>

## Retain/QoS guidance
- telemetry: QoS0 or QoS1 (MVP uses QoS1 for simplicity)
- health/events/recommendations: QoS1
- members/status: retained
