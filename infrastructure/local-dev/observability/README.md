# Local Observability Stack

## Purpose

This directory contains local observability configuration for Phase 6.

The stack provides:
- OpenTelemetry Collector for local telemetry intake
- Jaeger for trace inspection
- Prometheus for metrics collection
- Grafana for local operational views

Observability data is operational telemetry only.

It is not the system of record for workflow state, approval decisions, audit history, or event facts.

---

## Local URLs

```text
Grafana: http://localhost:3001
Prometheus: http://localhost:9090
Jaeger: http://localhost:16686
OpenTelemetry Collector OTLP gRPC: localhost:4317
OpenTelemetry Collector OTLP HTTP: http://localhost:4318
OpenTelemetry Collector internal metrics: http://localhost:8888/metrics
OpenTelemetry Collector exported metrics: http://localhost:8889/metrics
```

Grafana local credentials:

```text
Username: admin
Password: aegisflow
```

---

## Current Boundary

Workstream 1 starts the observability infrastructure only.

Application service instrumentation is intentionally assigned to later Phase 6 workstreams.

Until those workstreams are implemented:
- Prometheus will show infrastructure and collector metrics
- Jaeger will be reachable but may not contain AegisFlow service traces
- Grafana will have datasource provisioning but no Phase 6 dashboards
