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

## Local Log Diagnostics

Local services emit structured JSON logs with bounded operational fields such as `service`, `environment`, `correlation_id`, `trace_id`, `workflow_id`, `agent_id`, `tool_id`, `approval_id`, `operation`, and `status` where those values are available.

Logs are for local diagnostics only. They are not the system of record for workflow state, approval decisions, timeline history, or event publication.

Use the workflow correlation ID to inspect related logs across services:

```powershell
$correlationId = "phase6-ws7-log-check"
$services = @(
  "aegisflow-gateway-api",
  "aegisflow-workflow-engine",
  "aegisflow-agent-runtime",
  "aegisflow-tool-runtime"
)

foreach ($service in $services) {
  docker logs $service --since 15m 2>&1 |
    ForEach-Object {
      try { $_.ToString() | ConvertFrom-Json -ErrorAction Stop } catch { $null }
    } |
    Where-Object { $_.correlation_id -eq $correlationId } |
    Select-Object timestamp, service, level, message, correlation_id, trace_id, workflow_id, agent_id, tool_id, approval_id, status
}
```

Useful direct log commands:

```powershell
docker logs aegisflow-gateway-api --since 10m
docker logs aegisflow-workflow-engine --since 10m
docker logs aegisflow-agent-runtime --since 10m
docker logs aegisflow-tool-runtime --since 10m
```

Loki and Docker log collection are deferred for the local stack. Docker Desktop-compatible log collection adds host-specific setup, while Docker logs plus JSON filtering are sufficient for Phase 6 local correlation diagnostics.

Structured logs must not include borrower PII, raw document contents, secrets, prompt content, full model output, approval comments, or unrestricted request and response payloads.

---

## Current Boundary

Phase 6 includes local observability infrastructure, Python service tracing, Prometheus metrics, provisioned Grafana dashboards, structured local log diagnostics, and Postman/manual observability validation.

Production alerting, production log aggregation, SIEM integration, compliance reporting, AI evaluation, and replay scoring are outside the Phase 6 local implementation boundary.
