# Fault Injection Test Plan

Test Matrix (run on 5 drones in a group):
1) RF_LOSS_BURST: drop all telemetry for 8s every 120s
   Expect: telemetry stale alert + AI recommends HOLD/RTL depending on mission

2) GNSS_MULTIPATH: 20m jumps + hdop spike to 6.0 for 30s
   Expect: GPS anomaly event + AI recommends slow/hold/replan

3) EKF_UNHEALTHY: ekf_ok=false for 20s
   Expect: critical alert + AI recommends HOLD/LAND per policy

4) THRUST_SHORTFALL: climb rate suppressed + current draw increases
   Expect: performance degradation + AI suggests reduce speed / abort

5) BATTERY_SAG: nonlinear curve with sudden drop below 25%
   Expect: early warning + role swap suggestion for POINT_MAN
