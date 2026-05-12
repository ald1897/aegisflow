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

## Provisioned Dashboards

Grafana provisions the AegisFlow dashboards into the `AegisFlow` folder.

Current local dashboards:
- `AegisFlow - Workflow Operations`
- `AegisFlow - Service Health And Latency`
- `AegisFlow - Agent And Tool Execution`
- `AegisFlow - Approval Decisions`

The dashboards use Prometheus metrics and the provisioned Jaeger datasource.

Dashboard panels intentionally aggregate by low-cardinality operational dimensions such as service, route, workflow state, agent, tool, decision, and status. They do not use borrower values, workflow IDs, approval IDs, trace IDs, operator IDs, prompt content, document content, or comments as metric labels.

---

## Current Boundary

Phase 6 currently includes local observability infrastructure, Python service tracing, Prometheus metrics, and provisioned Grafana dashboards.

Current remaining Phase 6 work:
- structured log enrichment and local diagnostics
- Postman and manual observability validation documentation
- final Phase 6 roadmap and current functionality closeout
