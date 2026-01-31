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

## Retain/QoS guidance
- telemetry: QoS0 or QoS1 (MVP uses QoS1 for simplicity)
- health/events/recommendations: QoS1
- members/status: retained
