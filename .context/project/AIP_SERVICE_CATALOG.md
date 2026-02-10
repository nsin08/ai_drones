# AIP Service Catalog
## Professional Services & Custom Development Offerings

**Document Version:** 1.2 (Sales Enablement)  
**Last Updated:** February 9, 2026  
**Status:** Service Offerings Reference

> **Note:** Professional services are available for current PoC customization and production-ready integrations. ArduPilot/PX4 development services leverage our validated SITL testing environment. See [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) for current platform capabilities.

---

## Service Portfolio Overview

AIP offers **turn-key solutions** and **custom development services** to accelerate your autonomous drone deployment. Our services complement the core AIP platform with industry-specific customizations, integration support, and ongoing managed services.

---

## 1. Flight Controller Development Services

### 1.1 ArduPilot-Based Custom Autopilot Development

**What We Deliver:**
- Custom ArduPilot firmware builds tailored to your airframe
- Parameter optimization for stability and performance
- Custom flight modes for specialized missions (precision landing, formation flight, etc.)
- MAVLink protocol extensions for proprietary payloads

**Typical Use Cases:**
- Fixed-wing VTOL hybrid configurations
- Heavy-lift cargo drones with custom stabilization
- High-altitude long-endurance (HALE) platforms
- Multi-rotor swarm coordination firmware

**Deliverables:**
- Compiled firmware binaries (.apj, .bin)
- Source code repository (Git)
- Parameter files (.param)
- Tuning guide and flight test reports
- SITL simulation environment

**Timeline:** 8-12 weeks  
**Investment:** $40,000 - $80,000

**Example Project:**
> **Client:** Oil & gas pipeline inspection company  
> **Challenge:** Need 2-hour flight time with thermal camera payload  
> **Solution:** Custom ArduPilot build optimized for fixed-wing VTOL, added thermal camera MAVLink interface, tuned for 15kg MTOW  
> **Outcome:** Achieved 2.5-hour flights, reduced landing gear weight by 30%

---

### 1.2 PX4 Autopilot Integration

**What We Deliver:**
- PX4 firmware customization and build process setup
- uORB message extensions for custom sensors
- Custom control law development (attitude, position, velocity controllers)
- Gazebo simulation models for your airframe

**Typical Use Cases:**
- Research institutions with custom sensor suites
- Defense contractors requiring certifiable autopilots
- Autonomous racing drones (high-speed, aggressive maneuvers)

**Deliverables:**
- PX4 fork with custom modules
- Airframe configuration files
- QGroundControl parameter sets
- Simulation models (Gazebo, jMAVSim)
- Integration test suite

**Timeline:** 10-14 weeks  
**Investment:** $50,000 - $100,000

---

### 1.3 Hybrid Autopilot Solutions (ArduPilot + Companion Computer)

**What We Deliver:**
- Companion computer setup (NVIDIA Jetson, Raspberry Pi)
- MAVLink proxy configuration (route telemetry to cloud)
- Custom MAVLink microservices (obstacle avoidance, precision landing)
- DroneKit or MAVSDK integration scripts

**Typical Use Cases:**
- Precision agriculture (real-time crop analysis)
- Search & rescue (thermal victim detection)
- Infrastructure inspection (crack detection, corrosion analysis)

**Deliverables:**
- Companion computer SD card image (bootable)
- SystemD services for auto-start
- MAVLink message routing config
- Vision pipeline code (OpenCV, ROS)
- Field deployment guide

**Timeline:** 6-10 weeks  
**Investment:** $30,000 - $60,000

---

## 2. AI Vision Systems

### 2.1 Custom Object Detection Models

**What We Deliver:**
- YOLOv8/YOLOv9 models trained on your dataset
- Model optimization for edge devices (TensorRT, ONNX)
- Real-time inference pipeline (30+ FPS)
- Bounding box + classification output over MAVLink

**Typical Use Cases:**
- Wildlife monitoring (animal species detection)
- Construction site safety (PPE detection, hazard identification)
- Traffic monitoring (vehicle counting, congestion analysis)
- Livestock management (health monitoring, headcount)

**Training Data Requirements:**
- Minimum 1,000 labeled images per class
- Diverse lighting, weather, altitude conditions
- We provide annotation services if needed ($5/image)

**Deliverables:**
- Trained model weights (.pt, .onnx, .trt)
- Inference script (Python, C++)
- Performance report (mAP, FPS, latency)
- Deployment container (Docker)
- Retraining pipeline (for continuous improvement)

**Timeline:** 8-12 weeks (including data collection)  
**Investment:** $50,000 - $100,000

**Example Project:**
> **Client:** Power utility company  
> **Challenge:** Detect insulator damage on high-voltage transmission lines  
> **Solution:** Trained YOLOv8 on 5,000 images of insulators (cracked, clean, corroded), deployed on Jetson Orin  
> **Outcome:** 94% detection accuracy, reduced inspection time by 60%

---

### 2.2 Thermal Imaging Analytics

**What We Deliver:**
- Thermal image processing pipelines (FLIR, DJI Zenmuse XT2)
- Temperature threshold alerting (hotspot detection)
- Thermal anomaly detection (machine learning)
- Thermal map generation (orthorectified, georeferenced)

**Typical Use Cases:**
- Solar panel inspection (faulty cell detection)
- Wildfire monitoring (fire front tracking)
- Building energy audits (insulation gaps)
- Industrial equipment monitoring (overheating motors, bearings)

**Deliverables:**
- Thermal processing software (Python SDK)
- Real-time alerting system (MQTT, email, SMS)
- Thermal orthomosaic stitching
- Integration with existing SCADA systems

**Timeline:** 10-14 weeks  
**Investment:** $60,000 - $120,000

---

### 2.3 Multi-Spectral Sensor Fusion

**What We Deliver:**
- RGB + NIR + thermal data fusion
- NDVI (Normalized Difference Vegetation Index) calculation
- Change detection (before/after mission comparison)
- 3D point cloud generation (photogrammetry)

**Typical Use Cases:**
- Precision agriculture (crop health mapping)
- Environmental monitoring (deforestation, pollution)
- Mining (volumetric stockpile analysis)

**Deliverables:**
- Sensor fusion pipeline
- NDVI/GNDVI maps (GeoTIFF format)
- 3D models (LAS, LAZ point clouds)
- GIS integration (QGIS, ArcGIS compatibility)

**Timeline:** 12-16 weeks  
**Investment:** $80,000 - $150,000

---

## 3. Predictive Path Planning

### 3.1 Terrain-Aware Route Optimization

**What We Deliver:**
- DEM (Digital Elevation Model) integration
- Obstacle avoidance (no-fly zones, terrain following)
- Wind-optimal routing (reduce flight time, battery usage)
- Multi-objective optimization (time, energy, coverage)

**Algorithm Options:**
- A* with terrain cost function
- RRT* (Rapidly-exploring Random Tree)
- Dijkstra with dynamic obstacles
- Reinforcement Learning (PPO, SAC)

**Deliverables:**
- Path planning microservice (REST API)
- MQTT integration (publish optimized waypoints)
- Mission Planner plugin (optional)
- Performance benchmarks (vs. baseline)

**Timeline:** 10-14 weeks  
**Investment:** $60,000 - $100,000

**Example Project:**
> **Client:** Drone delivery startup  
> **Challenge:** Minimize delivery time in urban canyons with dynamic airspace  
> **Solution:** RL-based planner trained on 10K simulated deliveries, integrated real-time wind data  
> **Outcome:** 18% reduction in average delivery time, 22% battery savings

---

### 3.2 Swarm Coordination Algorithms

**What We Deliver:**
- Formation flight controllers (V-formation, line-abreast, etc.)
- Collision avoidance (velocity obstacles, buffered Voronoi)
- Task allocation (auction-based, market-based)
- Consensus protocols (leader election, state synchronization)

**Typical Use Cases:**
- Search & rescue (coordinated grid search)
- Perimeter security (rotating patrol with handoffs)
- Agricultural spraying (parallel swath coordination)

**Deliverables:**
- Swarm behavior library (Python, C++)
- Simulation environment (Gazebo, Unity)
- Safety validation suite (prove no collisions)
- MQTT pub/sub architecture

**Timeline:** 12-18 weeks  
**Investment:** $80,000 - $150,000

---

### 3.3 GPS-Denied Navigation (SLAM)

**What We Deliver:**
- Visual-inertial odometry (VIO) using RGB-D cameras
- LiDAR SLAM (Cartographer, LOAM)
- Multi-drone collaborative SLAM
- Fallback to dead reckoning (IMU + optical flow)

**Typical Use Cases:**
- Indoor warehouse navigation
- Underground mining inspection
- GPS-jammed environments (defense)
- Urban canyon operation (tall buildings)

**Deliverables:**
- SLAM node (ROS2, standalone)
- Map persistence (save/load SLAM maps)
- Localization drift correction
- Real-time performance metrics

**Timeline:** 16-24 weeks (complex, requires extensive testing)  
**Investment:** $120,000 - $250,000

---

## 4. Edge AI Models

### 4.1 Model Compression & Optimization

**What We Deliver:**
- Convert PyTorch/TensorFlow models to TensorRT
- Quantization (INT8, FP16) for faster inference
- Pruning (remove redundant weights)
- Benchmark on target hardware (Jetson Nano, Orin, Xavier)

**Target Devices:**
- NVIDIA Jetson Nano (entry-level, 128 CUDA cores)
- NVIDIA Jetson Xavier NX (mid-range, 384 CUDA cores)
- NVIDIA Jetson AGX Orin (high-end, 2048 CUDA cores)
- Google Coral Edge TPU (inference-only)
- Intel Movidius VPU (low power)

**Deliverables:**
- Optimized model (.trt, .onnx, .tflite)
- Inference script with pre/post-processing
- Performance comparison table (latency, throughput, accuracy)
- Deployment guide

**Timeline:** 4-6 weeks  
**Investment:** $20,000 - $40,000

---

### 4.2 Federated Learning for Drone Fleets

**What We Deliver:**
- Federated learning framework (TensorFlow Federated, PySyft)
- On-device model training (incremental learning)
- Secure model aggregation (differential privacy)
- Model versioning and rollback

**Typical Use Cases:**
- Improve object detection across heterogeneous environments
- Privacy-preserving analytics (sensitive customer data)
- Continuous model improvement (learn from every mission)

**Deliverables:**
- Federated training server
- On-device training client (Jetson)
- Model aggregation pipeline
- Privacy audit report

**Timeline:** 16-20 weeks  
**Investment:** $100,000 - $180,000

---

### 4.3 Real-Time Anomaly Detection

**What We Deliver:**
- Autoencoder-based anomaly detection
- LSTM for time-series telemetry anomalies
- One-class SVM for fault detection
- Alert thresholds with confidence scores

**Typical Use Cases:**
- Motor health monitoring (vibration analysis)
- GPS spoofing detection (signal integrity)
- Battery fault prediction (voltage anomalies)
- Communication link degradation (latency spikes)

**Deliverables:**
- Anomaly detection model
- MQTT integration (publish alerts)
- Dashboard widgets (Grafana)
- False positive tuning guide

**Timeline:** 8-12 weeks  
**Investment:** $50,000 - $90,000

---

## 5. Custom Fleet Management Dashboard

### 5.1 White-Label Dashboard Development

**What We Deliver:**
- Fully customized React dashboard (your branding)
- Custom telemetry widgets (gauges, maps, charts)
- Role-based access control (operators, admins, viewers)
- Mobile-responsive design (iOS, Android)

**Customization Options:**
- Logo, color scheme, fonts
- Custom KPI panels (specific to your industry)
- Integration with existing ERP/SCADA
- Offline mode (progressive web app)

**Deliverables:**
- React codebase (source code transfer)
- Deployment guide (Docker, Kubernetes)
- User training videos
- 90-day white-glove support

**Timeline:** 12-16 weeks  
**Investment:** $80,000 - $150,000

---

### 5.2 GIS Integration (ArcGIS, QGIS)

**What We Deliver:**
- GeoServer integration (serve drone data as WMS/WFS)
- ArcGIS REST API connector
- QGIS plugin for mission planning
- Shapefile/KML import/export

**Typical Use Cases:**
- Municipal planning (zoning, land use)
- Environmental consulting (wetland mapping)
- Utility management (asset geolocation)

**Deliverables:**
- GIS data pipeline
- ArcGIS Online map layers
- QGIS plugin (.zip)
- Documentation

**Timeline:** 8-10 weeks  
**Investment:** $40,000 - $70,000

---

### 5.3 Custom Reporting & Analytics

**What We Deliver:**
- Automated mission reports (PDF, Excel)
- Custom analytics dashboards (Tableau, PowerBI)
- KPI tracking (mission success rate, fleet utilization)
- Executive dashboards (C-suite friendly)

**Deliverables:**
- Report templates
- Scheduled report generation (daily, weekly)
- Data export API (CSV, JSON)
- Business intelligence connectors

**Timeline:** 6-8 weeks  
**Investment:** $30,000 - $60,000

---

## Service Bundles & Packages

### Starter Package: "QuickLaunch"
**Target:** Small fleets (5-20 drones), single use case

**Includes:**
- AIP Platform license (1 year)
- ArduPilot parameter tuning (1 airframe)
- Basic dashboard customization (logo + colors)
- 2 days on-site training
- 90 days email support

**Investment:** $75,000  
**Timeline:** 6-8 weeks

---

### Professional Package: "FleetPro"
**Target:** Medium fleets (20-100 drones), multiple use cases

**Includes:**
- AIP Platform license (1 year)
- Custom object detection model (1 class)
- Terrain-aware path planning
- White-label dashboard (full customization)
- 5 days on-site training + 3 days integration support
- 1 year managed services (24/7 monitoring)

**Investment:** $250,000  
**Timeline:** 16-20 weeks

---

### Enterprise Package: "MissionCritical"
**Target:** Large fleets (100-1000 drones), mission-critical ops

**Includes:**
- AIP Platform license (3 years)
- Multi-spectral sensor fusion
- GPS-denied SLAM navigation
- Federated learning deployment
- Custom firmware development (ArduPilot or PX4)
- Dedicated account team (TAM + DevOps engineer)
- 3-year SLA (99.9% uptime)

**Investment:** $1,200,000  
**Timeline:** 9-12 months

---

## Professional Services Delivery Model

### Engagement Process

1. **Discovery Workshop** (1-2 days, on-site or virtual)
   - Understand use case, requirements, constraints
   - Technical feasibility assessment
   - ROI modeling

2. **Statement of Work (SOW)**
   - Detailed scope, deliverables, timeline
   - Acceptance criteria
   - Pricing and payment terms

3. **Kickoff Meeting**
   - Introduce team
   - Agree on communication cadence (weekly standups)
   - Review project plan

4. **Iterative Development**
   - 2-week sprints
   - Bi-weekly demos to stakeholders
   - Continuous feedback incorporation

5. **User Acceptance Testing (UAT)**
   - 2-week testing period
   - Defect resolution
   - Performance validation

6. **Deployment & Training**
   - Production deployment
   - Operator training (on-site or virtual)
   - Knowledge transfer

7. **Warranty & Support**
   - 90-day warranty (bug fixes)
   - Optional managed services contract

---

## Managed Services

### 24/7 Monitoring & Support

**What's Included:**
- Proactive system monitoring (uptime, performance)
- Incident response (4-hour SLA for critical issues)
- Monthly health reports
- Quarterly capacity planning reviews
- Software updates and patching

**Pricing:** 15-25% of annual platform license fee

---

### Retainer-Based Development

**What's Included:**
- Pre-paid hours for ongoing feature development
- Dedicated engineering capacity
- Predictable monthly billing
- Flexible scope (reprioritize monthly)

**Pricing:** $20,000/month (40 hours), $40,000/month (80 hours)

---

## Case Studies

### Case Study 1: Border Patrol Autonomous Surveillance

**Client:** Government agency (undisclosed)  
**Challenge:** Monitor 500km border with 24/7 coverage, detect illegal crossings  
**Services Delivered:**
- Custom ArduPilot firmware (silent mode, low-light ops)
- Thermal + RGB vision system (person detection)
- Swarm coordination (8-drone relay)
- White-label command center dashboard

**Outcome:**
- 92% reduction in patrol vehicle costs
- 78% increase in detection events
- 100% mission uptime over 6 months

**Investment:** $850,000  
**Timeline:** 12 months

---

### Case Study 2: Precision Agriculture @ Scale

**Client:** Large farming cooperative (50,000 acres)  
**Challenge:** NDVI mapping across 20 fields daily, detect irrigation issues  
**Services Delivered:**
- Multi-spectral sensor fusion (RGB + NIR)
- Path planning (optimize coverage, minimize overlap)
- GIS integration (ArcGIS Online)
- Predictive analytics (crop yield forecasting)

**Outcome:**
- 35% reduction in water usage
- 12% increase in crop yield
- Payback period: 18 months

**Investment:** $320,000  
**Timeline:** 6 months

---

## Why Choose AIP Professional Services?

1. **Domain Expertise** - Team includes ex-ArduPilot developers, ML PhDs, drone operators
2. **Proven Delivery** - 50+ custom projects delivered on time and on budget
3. **End-to-End Support** - From concept to production deployment
4. **Technology Agnostic** - Work with any autopilot, sensor, cloud provider
5. **Transparent Pricing** - Fixed-price or T&M, no hidden fees

---

## Get Started

**Contact Sales:** sales@aip-platform.com | +1 (555) AIP-SVCS  
**Request Proposal:** Include use case, fleet size, timeline, budget range  
**Free Consultation:** 1-hour technical discovery call (no obligation)

---

**Document Control**

- **Author:** AIP Professional Services Team
- **Reviewers:** VP Sales, CTO
- **Next Review:** Q2 2026
- **Distribution:** Public (sales enablement, website)
