# AIP Production Deployment Guide
## Enterprise-Grade Setup, Scaling, and Operations

**Document Version:** 1.2 (Deployment Reference)  
**Last Updated:** February 9, 2026  
**Status:** Production Target State (Not Fully Implemented)

> **Context:** This guide describes **target production deployment** for 1000+ drone operations with HA, security, and monitoring. As of Feb 2026, the PoC runs on Docker Compose (7 services) with no authentication, single-node only. See [AIP_GAP_ANALYSIS.md](AIP_GAP_ANALYSIS.md) for production readiness roadmap (12-18 months, $1.64M budget).

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Infrastructure Requirements](#infrastructure-requirements)
3. [Deployment Topologies](#deployment-topologies)
4. [Step-by-Step Deployment](#step-by-step-deployment)
5. [Scaling Strategies](#scaling-strategies)
6. [Monitoring & Alerting](#monitoring--alerting)
7. [Security Hardening](#security-hardening)
8. [Backup & Disaster Recovery](#backup--disaster-recovery)
9. [SLA Definitions](#sla-definitions)
10. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

### Business Requirements

- [ ] **Fleet Size Defined** - Number of concurrent drones (20, 100, 500, 1000+)
- [ ] **Mission Types Identified** - PATROL, PERIMETER, ESCORT, custom
- [ ] **SLA Requirements** - Uptime target (99%, 99.9%, 99.99%)
- [ ] **Budget Approved** - Hardware, licenses, managed services
- [ ] **Team Trained** - Operators, DevOps, support engineers

### Technical Prerequisites

- [ ] **Network Infrastructure** - 4G/5G coverage map, LTE failover
- [ ] **DNS Configured** - `aip.yourdomain.com` (production), `aip-staging.yourdomain.com` (staging)
- [ ] **SSL Certificates** - Wildcard cert (`*.aip.yourdomain.com`) or Let's Encrypt
- [ ] **Firewall Rules** - Ports 443 (HTTPS), 8883 (MQTT/TLS), 5432 (PostgreSQL replication)
- [ ] **Secrets Management** - Vault, AWS Secrets Manager, or Azure Key Vault
- [ ] **Monitoring Tools** - Prometheus, Grafana, PagerDuty accounts

### Regulatory Compliance

- [ ] **Airspace Authorization** - FAA Part 107 waiver (USA), EASA STS (Europe)
- [ ] **Data Privacy** - GDPR compliance (if EU operations), data residency requirements
- [ ] **Cybersecurity** - SOC 2 Type II (if handling customer data)
- [ ] **Insurance** - Liability coverage for autonomous operations

---

## Infrastructure Requirements

### Sizing Guidelines

| Fleet Size | CPU Cores | RAM | Storage | Network | Monthly Cost (AWS) |
|------------|-----------|-----|---------|---------|-------------------|
| **20 drones** | 8 | 32GB | 500GB SSD | 100Mbps | $500 |
| **100 drones** | 32 | 128GB | 2TB SSD | 1Gbps | $2,500 |
| **500 drones** | 128 | 512GB | 10TB SSD | 10Gbps | $12,000 |
| **1000 drones** | 256 | 1TB | 25TB SSD | 10Gbps | $30,000 |

*Assumes 3-node HA cluster, 30% headroom, standard AWS pricing (us-east-1)*

### Recommended Hardware (On-Premise)

**Control Plane Server (Per Node, 3 nodes for HA):**
- **CPU:** Intel Xeon Gold 6254 (18 cores, 3.1 GHz) or AMD EPYC 7532 (32 cores)
- **RAM:** 128GB DDR4 ECC (minimum), 256GB recommended
- **Storage:** 2x 2TB NVMe SSD (RAID 1 for OS), 4x 4TB SSD (RAID 10 for data)
- **Network:** Dual 10GbE NICs (bonded for redundancy)
- **GPU:** NVIDIA A100 40GB (for AI inference, 1 per cluster)
- **Form Factor:** 2U rackmount server (Dell R750, HPE DL380 Gen11, Supermicro AS-2124US)

**Cost per Server:** $15,000 - $25,000

**Edge Servers (Field Deployment):**
- **Use Case:** Remote sites without reliable cloud connectivity
- **Hardware:** Intel NUC 13 Extreme Kit, NVIDIA Jetson AGX Orin Developer Kit
- **CPU:** 8+ cores (Intel i7 or ARM Cortex-A78AE)
- **RAM:** 32GB minimum
- **Storage:** 1TB NVMe SSD
- **Ruggedization:** IP65-rated enclosure, UPS (8-hour backup)

**Cost per Edge Server:** $2,000 - $5,000

---

## Deployment Topologies

### Topology 1: Cloud-Hosted (Managed Kubernetes)

**Recommended For:** SaaS deployments, multi-tenant, global reach

```
┌────────────────────────────────────────────────────────────┐
│  AWS (or Azure, GCP)                                       │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Region: us-east-1 (Primary)                         │ │
│  │                                                      │ │
│  │  EKS Cluster (Managed Kubernetes)                   │ │
│  │  ├─ Node Group 1: General (t3.2xlarge x 5)         │ │
│  │  ├─ Node Group 2: AI (g4dn.4xlarge x 2, GPU)       │ │
│  │  └─ Node Group 3: Telemetry (c6i.4xlarge x 3)      │ │
│  │                                                      │ │
│  │  Managed Services:                                   │ │
│  │  ├─ RDS PostgreSQL (Multi-AZ, r6g.2xlarge)         │ │
│  │  ├─ ElastiCache Redis (r6g.xlarge x 2, cluster)    │ │
│  │  ├─ MSK (Managed Kafka) - 3 brokers                │ │
│  │  ├─ S3 (telemetry archives, model weights)         │ │
│  │  └─ CloudFront (CDN for UI assets)                 │ │
│  │                                                      │ │
│  │  EMQX Cloud (MQTT Broker)                           │ │
│  │  └─ 3-node cluster, 100K connections               │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Region: us-west-2 (Hot Standby)                    │ │
│  │  - Read replicas for databases                      │ │
│  │  - Standby EKS cluster (scale from 0 on failover)  │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  Global Load Balancer: Route 53 (health-check based)      │
└────────────────────────────────────────────────────────────┘

Estimated Cost: $15,000 - $30,000/month (500 drones)
```

**Pros:**
- Auto-scaling (handle traffic spikes)
- Managed services (less ops burden)
- Global reach (multi-region)
- Pay-as-you-go (no upfront CapEx)

**Cons:**
- Higher monthly costs
- Network latency (drones → cloud)
- Vendor lock-in risk

---

### Topology 2: On-Premise (Private Cloud)

**Recommended For:** Defense, critical infrastructure, air-gapped environments

```
┌────────────────────────────────────────────────────────────┐
│  Customer Data Center                                      │
│                                                            │
│  Kubernetes Cluster (K3s or OpenShift)                    │
│  ├─ Control Plane: 3 servers (HA, etcd quorum)           │
│  ├─ Worker Nodes: 5-10 servers (application pods)        │
│  └─ GPU Nodes: 2 servers (AI inference)                  │
│                                                            │
│  Storage Layer:                                            │
│  ├─ Ceph Cluster (distributed block storage, 3+ nodes)   │
│  ├─ PostgreSQL HA (Patroni + HAProxy, 3 nodes)           │
│  ├─ InfluxDB Enterprise (2-node cluster)                 │
│  └─ Redis Sentinel (3 nodes, automatic failover)         │
│                                                            │
│  MQTT Broker:                                              │
│  ├─ EMQX Enterprise (3-node cluster)                     │
│  └─ LVS Load Balancer (virtual IP failover)              │
│                                                            │
│  Network:                                                  │
│  ├─ DMZ: Public-facing load balancer (NGINX)             │
│  ├─ App Zone: Kubernetes pods (isolated VLAN)            │
│  ├─ Data Zone: Databases (encrypted at rest)             │
│  └─ Edge Zone: VPN gateway for field drones              │
└────────────────────────────────────────────────────────────┘

Estimated Cost: $150,000 - $300,000 (CapEx), $3K/month (OpEx)
```

**Pros:**
- No cloud egress costs
- Full data sovereignty
- Air-gapped deployment possible
- Lower long-term TCO (3+ years)

**Cons:**
- High upfront CapEx
- Requires dedicated DevOps team
- Manual scaling (capacity planning)
- No multi-region (unless you build it)

---

### Topology 3: Hybrid Edge-Cloud

**Recommended For:** Remote operations, low-latency requirements

```
┌──────────────────────────────────────────────────────────┐
│  Edge Site (Field Server at Drone Launch Site)          │
│                                                          │
│  Intel NUC or Jetson AGX Orin                           │
│  ├─ Mission Control (local instance)                   │
│  ├─ EMQX Broker (local MQTT, 500 connections)          │
│  ├─ Redis (ephemeral state)                            │
│  ├─ InfluxDB (7-day retention, then sync to cloud)     │
│  └─ LTE Modem (4G/5G failover)                         │
│                                                          │
│  Drones connect to edge via 900 MHz radio or LTE       │
│  Edge makes decisions locally (<50ms latency)           │
│                                                          │
│  ↓ (Replicate to Cloud via VPN)                        │
└──────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  Cloud (AWS, Azure, GCP)                                 │
│                                                          │
│  Kubernetes Cluster                                      │
│  ├─ Analytics Services (long-term storage)             │
│  ├─ ML Training (retrain models)                       │
│  ├─ Fleet Manager (cross-site coordination)            │
│  └─ Executive Dashboard (C-suite reporting)            │
│                                                          │
│  PostgreSQL (mission history, 1 year+)                  │
│  S3 (telemetry archives, video recordings)              │
└──────────────────────────────────────────────────────────┘

Estimated Cost: $5K (edge) + $5K/month (cloud)
```

**Pros:**
- Low latency (edge processing)
- Offline operation (drones fly even if cloud down)
- Reduced cloud costs (only analytics in cloud)

**Cons:**
- Complex deployment (2 environments)
- Data synchronization challenges
- Edge hardware maintenance

---

## Step-by-Step Deployment

### Phase 1: Infrastructure Setup (Week 1-2)

#### Step 1: Provision Kubernetes Cluster

**Cloud (AWS EKS Example):**
```bash
# Install eksctl
brew install eksctl  # macOS
# choco install eksctl  # Windows

# Create cluster
eksctl create cluster \
  --name aip-production \
  --version 1.28 \
  --region us-east-1 \
  --nodegroup-name general \
  --node-type t3.2xlarge \
  --nodes 3 \
  --nodes-min 3 \
  --nodes-max 10 \
  --managed

# Verify
kubectl get nodes
```

**On-Premise (K3s Example):**
```bash
# Master node
curl -sfL https://get.k3s.io | sh -
sudo cat /var/lib/rancher/k3s/server/node-token

# Worker nodes (repeat on each)
curl -sfL https://get.k3s.io | K3S_URL=https://master:6443 \
  K3S_TOKEN=<token-from-master> sh -

# Verify
kubectl get nodes
```

#### Step 2: Install Helm & ArgoCD

```bash
# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install ArgoCD (GitOps deployment)
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Access ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
# User: admin, Password: kubectl get secret -n argocd argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

---

### Phase 2: Deploy Core Services (Week 2-3)

#### Step 3: Deploy PostgreSQL (HA)

**Using Helm (Bitnami Chart):**
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami

helm install postgresql-ha bitnami/postgresql-ha \
  --namespace aip \
  --create-namespace \
  --set postgresql.replicaCount=3 \
  --set postgresql.database=aip_production \
  --set postgresql.username=aip \
  --set postgresql.password=<STRONG_PASSWORD> \
  --set persistence.size=100Gi
```

**Verify:**
```bash
kubectl get pods -n aip | grep postgresql
# Should show: postgresql-ha-postgresql-0, postgresql-ha-postgresql-1, postgresql-ha-postgresql-2
```

#### Step 4: Deploy Redis (Sentinel for HA)

```bash
helm install redis bitnami/redis \
  --namespace aip \
  --set auth.password=<STRONG_PASSWORD> \
  --set sentinel.enabled=true \
  --set sentinel.quorum=2 \
  --set master.persistence.size=20Gi
```

#### Step 5: Deploy EMQX MQTT Broker

```bash
helm repo add emqx https://repos.emqx.io/charts
helm install emqx emqx/emqx \
  --namespace aip \
  --set replicaCount=3 \
  --set service.type=LoadBalancer \
  --set emqxConfig.EMQX_CLUSTER__DISCOVERY_STRATEGY=k8s \
  --set emqxConfig.EMQX_ALLOW_ANONYMOUS=false \
  --set emqxConfig.EMQX_LOADED_PLUGINS="emqx_auth_mnesia,emqx_recon,emqx_retainer,emqx_management"
```

**Configure ACLs:**
```bash
kubectl exec -it emqx-0 -n aip -- emqx_ctl acl add username aip-mission-control topic "fleet/+/command" pub
kubectl exec -it emqx-0 -n aip -- emqx_ctl acl add username aip-mission-control topic "fleet/+/telemetry" sub
```

#### Step 6: Deploy InfluxDB (Time-Series DB)

```bash
helm install influxdb bitnami/influxdb \
  --namespace aip \
  --set auth.admin.username=admin \
  --set auth.admin.password=<STRONG_PASSWORD> \
  --set auth.admin.org=aip \
  --set auth.admin.bucket=telemetry \
  --set persistence.size=500Gi
```

---

### Phase 3: Deploy AIP Application (Week 3-4)

#### Step 7: Create Helm Chart for AIP

**Directory Structure:**
```
aip-helm/
├── Chart.yaml
├── values.yaml
├── values-production.yaml
└── templates/
    ├── mission-control-deployment.yaml
    ├── fleet-manager-deployment.yaml
    ├── telemetry-processor-deployment.yaml
    ├── ai-recommender-deployment.yaml
    ├── command-executor-deployment.yaml
    ├── ingress.yaml
    └── secrets.yaml
```

**values-production.yaml (Example):**
```yaml
global:
  environment: production
  domain: aip.yourdomain.com

missionControl:
  replicaCount: 3
  image:
    repository: ghcr.io/your-org/aip-mission-control
    tag: v1.0.0
  resources:
    requests:
      cpu: 2
      memory: 4Gi
    limits:
      cpu: 4
      memory: 8Gi
  env:
    - name: MQTT_BROKER
      value: emqx-headless.aip.svc.cluster.local:1883
    - name: POSTGRES_HOST
      value: postgresql-ha-pgpool.aip.svc.cluster.local
    - name: REDIS_HOST
      value: redis-master.aip.svc.cluster.local

fleetManager:
  replicaCount: 2
  image:
    repository: ghcr.io/your-org/aip-fleet-manager
    tag: v1.0.0
  resources:
    requests:
      cpu: 1
      memory: 2Gi

aiRecommender:
  replicaCount: 2
  image:
    repository: ghcr.io/your-org/aip-ai-recommender
    tag: v1.0.0
  resources:
    requests:
      cpu: 4
      memory: 8Gi
      nvidia.com/gpu: 1  # Requires GPU node pool

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: aip.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: aip-tls
      hosts:
        - aip.yourdomain.com
```

**Deploy:**
```bash
helm install aip ./aip-helm \
  --namespace aip \
  --values aip-helm/values-production.yaml
```

#### Step 8: Verify Deployment

```bash
# Check all pods running
kubectl get pods -n aip

# Expected output:
# NAME                                    READY   STATUS    RESTARTS   AGE
# mission-control-xxxxxx-xxxxx           1/1     Running   0          5m
# mission-control-xxxxxx-xxxxx           1/1     Running   0          5m
# mission-control-xxxxxx-xxxxx           1/1     Running   0          5m
# fleet-manager-xxxxxx-xxxxx             1/1     Running   0          5m
# ai-recommender-xxxxxx-xxxxx            1/1     Running   0          5m
# ...

# Check ingress
kubectl get ingress -n aip

# Test external access
curl https://aip.yourdomain.com/api/health
# Should return: {"status": "healthy", "version": "1.0.0"}
```

---

### Phase 4: Deploy Monitoring (Week 4)

#### Step 9: Deploy Prometheus + Grafana

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=100Gi \
  --set grafana.adminPassword=<STRONG_PASSWORD>
```

**Access Grafana:**
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
# Open http://localhost:3000, login with admin/<password>
```

**Import AIP Dashboards:**
- Fleet Status Overview (dashboard ID: 15001)
- Mission Execution Metrics (dashboard ID: 15002)
- Telemetry Latency (dashboard ID: 15003)

#### Step 10: Configure Alerting (PagerDuty)

**prometheus-values.yaml:**
```yaml
alertmanager:
  config:
    global:
      resolve_timeout: 5m
    route:
      group_by: ['alertname', 'cluster']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 12h
      receiver: 'pagerduty'
    receivers:
    - name: 'pagerduty'
      pagerduty_configs:
      - service_key: '<PAGERDUTY_INTEGRATION_KEY>'
```

**Critical Alerts:**
- Mission Control pod down (>1 minute)
- MQTT broker connection drop (>30 seconds)
- Database connection pool exhausted
- Disk usage >90%
- Command latency >200ms (P99)

---

## Scaling Strategies

### Horizontal Pod Autoscaling (HPA)

**mission-control-hpa.yaml:**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: mission-control-hpa
  namespace: aip
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mission-control
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: websocket_active_connections
      target:
        type: AverageValue
        averageValue: "500"
```

**Apply:**
```bash
kubectl apply -f mission-control-hpa.yaml
```

### Cluster Autoscaling

**AWS EKS Example:**
```bash
eksctl create nodegroup \
  --cluster aip-production \
  --name autoscale-ng \
  --node-type c6i.4xlarge \
  --nodes 2 \
  --nodes-min 2 \
  --nodes-max 20 \
  --asg-access
```

**Enable Cluster Autoscaler:**
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml
```

---

## Monitoring & Alerting

### Key Performance Indicators (KPIs)

| Metric | Target | Alert Threshold | Dashboard |
|--------|--------|----------------|-----------|
| **Command Latency (P50)** | <100ms | >150ms (warning) | Mission Execution |
| **Command Latency (P99)** | <200ms | >250ms (critical) | Mission Execution |
| **Telemetry Lag** | <150ms | >300ms (warning) | Telemetry Latency |
| **MQTT Throughput** | 10K msg/sec | >80% capacity | MQTT Broker |
| **CPU Utilization** | <70% | >85% (warning), >95% (critical) | Cluster Overview |
| **Memory Utilization** | <75% | >90% (critical) | Cluster Overview |
| **Pod Restart Rate** | <1/hour | >5/hour (warning) | Pod Health |
| **Database Query Time (P95)** | <50ms | >100ms (warning) | Database Performance |
| **Disk IOPS** | <60% provisioned | >80% (warning) | Storage |

### Sample Prometheus Queries

**Command Latency (P99):**
```promql
histogram_quantile(0.99, 
  rate(aip_command_latency_seconds_bucket[5m])
)
```

**Mission Success Rate:**
```promql
sum(rate(aip_missions_completed_total[1h])) /
sum(rate(aip_missions_started_total[1h])) * 100
```

**Active Drones:**
```promql
count(aip_drone_heartbeat_timestamp_seconds > (time() - 60))
```

---

## Security Hardening

### Network Policies

**Deny all ingress by default:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
  namespace: aip
spec:
  podSelector: {}
  policyTypes:
  - Ingress
```

**Allow Mission Control → MQTT:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-mission-control-to-mqtt
  namespace: aip
spec:
  podSelector:
    matchLabels:
      app: mission-control
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: emqx
    ports:
    - protocol: TCP
      port: 1883
```

### Pod Security Standards

**Enforce restricted profile:**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: aip
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

### Secrets Management

**Using Sealed Secrets:**
```bash
# Install Sealed Secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Encrypt secret
echo -n "supersecret" | kubectl create secret generic mqtt-password \
  --dry-run=client \
  --from-file=password=/dev/stdin \
  -o yaml | \
kubeseal -o yaml > mqtt-password-sealed.yaml

# Commit to Git (safe, encrypted)
git add mqtt-password-sealed.yaml
```

---

## Backup & Disaster Recovery

### Database Backup Strategy

**PostgreSQL (Daily backups):**
```bash
# CronJob for pg_dump
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgresql-backup
  namespace: aip
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:15
            command:
            - /bin/sh
            - -c
            - pg_dump -h postgresql-ha-pgpool -U aip aip_production | gzip > /backups/aip-$(date +%Y%m%d).sql.gz
            volumeMounts:
            - name: backup-volume
              mountPath: /backups
          volumes:
          - name: backup-volume
            persistentVolumeClaim:
              claimName: postgresql-backups
          restartPolicy: OnFailure
EOF
```

**InfluxDB (Incremental backups):**
```bash
influx backup /backups/influxdb-$(date +%Y%m%d) \
  --host http://influxdb:8086 \
  --token <INFLUX_TOKEN>
```

**Retention Policy:**
- Daily backups: 30 days
- Weekly backups: 12 weeks
- Monthly backups: 12 months

---

## SLA Definitions

### Tier 1: Standard (99% Uptime)

**Guaranteed:**
- Maximum downtime: 7.2 hours/month
- Support response: 24 hours (business days)
- Incident resolution: Best effort

**Price:** Included with platform license

---

### Tier 2: Professional (99.9% Uptime)

**Guaranteed:**
- Maximum downtime: 43 minutes/month
- Support response: 4 hours (24/7)
- Incident resolution: 24 hours (critical), 48 hours (major)
- Monthly health reports

**Price:** +20% of platform license

---

### Tier 3: Enterprise (99.99% Uptime)

**Guaranteed:**
- Maximum downtime: 4.3 minutes/month
- Support response: 1 hour (24/7)
- Incident resolution: 4 hours (critical), 12 hours (major)
- Dedicated TAM (Technical Account Manager)
- Quarterly business reviews

**Price:** +50% of platform license

---

## Troubleshooting

### Common Issues

**Issue 1: High Command Latency (>200ms)**

**Symptoms:**
- Prometheus alert: `command_latency_p99 > 0.2`
- Operators report sluggish UI

**Diagnosis:**
```bash
# Check MQTT broker queue depth
kubectl exec -it emqx-0 -n aip -- emqx_ctl queues list

# Check Mission Control pod CPU
kubectl top pods -n aip | grep mission-control
```

**Resolution:**
- If MQTT queue > 10K: Scale up EMQX replicas
- If CPU > 90%: Trigger HPA or increase resource limits
- If network latency: Check cloud region proximity to drones

---

**Issue 2: Database Connection Pool Exhausted**

**Symptoms:**
- Error logs: `"FATAL: remaining connection slots are reserved"`
- Mission creation fails

**Diagnosis:**
```bash
kubectl logs -n aip deployment/mission-control | grep "connection"
```

**Resolution:**
```sql
-- Increase max_connections (requires restart)
ALTER SYSTEM SET max_connections = 500;
SELECT pg_reload_conf();

-- Or scale out with PgBouncer connection pooler
helm install pgbouncer bitnami/pgbouncer --namespace aip
```

---

**Issue 3: Drone Telemetry Not Appearing**

**Symptoms:**
- Dashboard shows "No data"
- MQTT topic subscriptions empty

**Diagnosis:**
```bash
# Test MQTT connectivity
kubectl run -it --rm mqtt-test --image=efrecon/mqtt-client --restart=Never -- \
  mosquitto_sub -h emqx-headless.aip.svc.cluster.local -t "fleet/+/telemetry" -v
```

**Resolution:**
- If timeout: Check MQTT broker network policy
- If authentication failed: Verify drone credentials in EMQX ACL
- If topic empty: Verify drone is publishing (check drone logs)

---

**Document Control**

- **Author:** AIP DevOps Team
- **Reviewers:** CTO, VP Engineering, Head of Support
- **Next Review:** Quarterly (Q2 2026)
- **Distribution:** Internal (Ops team) + Customers (Enterprise tier)
