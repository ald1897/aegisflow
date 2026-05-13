# AI Evaluation Strategy

## Purpose

This document defines the evaluation architecture, quality measurement standards, regression testing model, and operational AI assessment strategy for AegisFlow.

The evaluation system exists to provide:
- measurable AI quality
- operational reliability validation
- hallucination detection
- prompt regression analysis
- workflow correctness assessment
- governance visibility
- continuous improvement signals

AI systems must be treated as probabilistic operational components requiring continuous evaluation and validation.

All AI-assisted workflows and agents must conform to the standards defined in this document.

---

# Evaluation Philosophy

## AI Systems Require Continuous Measurement

AI behavior is non-deterministic and may drift over time.

Evaluation systems exist to:
- quantify reliability
- detect degradation
- identify regressions
- validate operational safety
- support governance decisions

---

## Evaluation Is Operational, Not Academic

Evaluation should focus on:
- operational usefulness
- workflow correctness
- governance alignment
- production reliability

Avoid purely benchmark-oriented evaluation disconnected from real workflows.

---

## Human Oversight Remains Authoritative

Evaluation systems assist operational governance but do not replace:
- human review
- compliance oversight
- workflow approvals
- escalation decisions

---

## Observability and Evaluation Are Linked

Every evaluation result should remain:
- traceable
- reproducible
- auditable
- explainable

---

# Evaluation Architecture Overview

## Core Evaluation Components

The evaluation architecture consists of:
- evaluation pipelines
- replay execution systems
- prompt regression testing
- hallucination detection
- workflow scoring
- LLM-as-judge systems
- human review systems
- evaluation telemetry pipelines

---

# Evaluation Categories

# Workflow Evaluation

## Purpose

Measures:
- workflow correctness
- orchestration reliability
- escalation accuracy
- operational outcomes

---

## Example Metrics

Track:
- workflow completion rate
- escalation correctness
- operator override frequency
- workflow retry frequency
- workflow failure rate

---

# Agent Evaluation

## Purpose

Measures:
- agent output quality
- reasoning consistency
- operational usefulness
- execution reliability

---

## Example Metrics

Track:
- extraction accuracy
- classification accuracy
- hallucination rate
- confidence reliability
- retry frequency
- escalation recommendation quality

---

# Prompt Evaluation

## Purpose

Measures:
- prompt effectiveness
- regression risk
- operational consistency

---

## Example Metrics

Track:
- prompt success rate
- structured output validity
- downstream workflow impact
- token efficiency
- hallucination frequency

---

# Tool Usage Evaluation

## Purpose

Measures:
- tool invocation correctness
- operational safety
- retry behavior

---

## Example Metrics

Track:
- tool success rate
- invalid tool invocation attempts
- retry frequency
- execution latency

---

# Human Evaluation

## Purpose

Measures:
- operator trust
- approval consistency
- override frequency

---

## Example Metrics

Track:
- manual override frequency
- approval disagreement rates
- escalation acceptance rate
- reviewer correction frequency

---

# Evaluation Dataset Strategy

# Dataset Philosophy

Evaluation datasets should represent:
- realistic workflows
- operational edge cases
- failure conditions
- escalation scenarios

Avoid synthetic-only evaluation coverage.

---

# Dataset Categories

Datasets may include:
- historical workflow replays
- synthetic edge-case scenarios
- curated validation datasets
- escalation-heavy workflows
- adversarial prompt injection cases

---

# Dataset Requirements

Evaluation datasets should:
- remain versioned
- support replayability
- preserve operational realism
- expose expected outcomes

---

# Replay-Based Evaluation

# Replay Philosophy

Replay evaluation is a core operational capability.

Replay systems enable:
- regression testing
- workflow comparison
- prompt validation
- incident reconstruction

---

# Replay Requirements

Replay execution should preserve:
- workflow ordering
- prompt versions
- model metadata
- event sequences
- operational context

---

# Replay Constraints

Replay systems must avoid:
- duplicate side effects
- unsafe integration mutations
- hidden context drift

---

# LLM-as-Judge Strategy

# Purpose

LLM-as-judge systems provide automated qualitative evaluation of:
- summaries
- classifications
- extraction quality
- workflow recommendations

---

# Implemented Local Judge Boundary

The Phase 7 local implementation defines a judge-model boundary without enabling external model calls by default.

Implemented behavior:
- judge requests use bounded workflow evidence and optional expectations
- judge results include evaluator ID, evaluator version, rubric ID, rubric version, score name, score value, status, severity, rationale, and bounded metadata
- `ENABLE_EXTERNAL_JUDGE_MODEL` defaults to disabled
- local validation uses a deterministic fallback judge for reproducible PASS, WARN, and FAIL results
- external provider integration is future work and must be explicitly enabled before any provider path is used

Judge results are evaluation quality signals only. They do not approve, reject, complete, or mutate workflows.

Judge metadata must not persist prompt content, raw document contents, borrower PII, secrets, approval comments, or full model outputs.

---

# Evaluation Principles

Judge models should:
- use explicit scoring criteria
- remain reproducible
- expose evaluation rationale
- support auditability

---

# Example Evaluation Dimensions

Examples:
- factual consistency
- completeness
- operational usefulness
- policy alignment
- hallucination likelihood

---

# Human Evaluation Integration

# Human Review Philosophy

Human reviewers remain critical for:
- ambiguous workflow analysis
- governance validation
- operational trust measurement

---

# Human Evaluation Sources

Human evaluation may include:
- reviewer scoring
- escalation feedback
- override analysis
- workflow correction review

---

# Hallucination Detection Strategy

# Hallucination Philosophy

Hallucinations represent operational risk.

Detection systems should identify:
- unsupported claims
- fabricated workflow data
- invalid recommendations
- invented entities

---

# Hallucination Detection Signals

Signals may include:
- retrieval mismatch
- unsupported citations
- confidence inconsistencies
- schema validation failures
- reviewer disagreement

---

# Hallucination Severity Levels

Suggested severity categories:
- informational
- moderate
- critical

---

# Confidence Score Evaluation

# Confidence Philosophy

Confidence scores should correlate with:
- actual reliability
- escalation appropriateness
- reviewer agreement

---

# Confidence Validation

Measure:
- confidence calibration
- false confidence frequency
- escalation threshold accuracy

---

# Evaluation Pipelines

# Evaluation Pipeline Flow

Typical evaluation flow:

```text id="pq0b3l"
Workflow Execution
        ↓
Telemetry Collection
        ↓
Output Validation
        ↓
Automated Evaluation
        ↓
Human Review
        ↓
Metrics Aggregation
        ↓
Regression Tracking
```

## Implemented Local Run Orchestration

The Phase 7 local implementation can create evaluation runs for persisted workflow evidence.

Implemented flow:
- request an evaluation run for a workflow
- load persisted workflow, timeline, agent execution, tool invocation, and approval evidence
- reject missing workflows or workflows that have not reached a reviewable or terminal state
- execute deterministic local evaluators against bounded evidence
- optionally include the deterministic judge-boundary fallback when using `judge_model_disabled` mode
- optionally compare workflow evidence against a selected local dataset case when `dataset_case_id` is supplied
- persist evaluation run and evaluation result records
- retrieve a run with its results or list runs for a workflow
- retrieve persisted workflow evaluation summaries through gateway-api for operator and Postman ergonomics

Current implemented endpoints:

```text
POST /api/v1/evaluations/workflows/{workflow_id}/runs
GET /api/v1/evaluations/runs/{evaluation_run_id}
GET /api/v1/evaluations/workflows/{workflow_id}/runs
GET /api/v1/evaluations/datasets
GET /api/v1/evaluations/datasets/{dataset_id}/cases
GET /api/v1/workflows/{workflow_id}/evaluations
```

Evaluation run orchestration is side-effect free with respect to workflow state. It reads authoritative records and writes evaluation records only.

The initial local replay-aware dataset is `mortgage-exception-local-v1`. It includes approval, rejection, and human-review Mortgage Exception Review scenarios. Dataset replay means deterministic comparison against persisted records; it does not run a full workflow replay engine, invoke Temporal activities, call agents, execute tools, dispatch approvals, or perform recovery actions.

## Implemented Local Evaluators

Phase 7 implements deterministic local evaluators before any external judge-model behavior is enabled.

Implemented evaluators:
- `agent-output-contract` checks validated agent output shape, prompt/model references, confidence bounds, and human-review metadata consistency
- `tool-usage-contract` checks expected tool coverage, permission status, input validation, output validation, and tool completion
- `human-review-escalation` checks human-review state alignment and expected terminal approval or rejection evidence
- `evidence-consistency-signals` checks unsupported tool claims and high-confidence validation failure signals
- `dataset-replay-contract` compares persisted workflow evidence against a selected local dataset case
- `judge-model-boundary` provides a deterministic fallback for judge-style scoring while external judge providers remain disabled by default

Implemented score statuses:
- `PASS`
- `WARN`
- `FAIL`

Implemented severities:
- `informational`
- `moderate`
- `critical`

## Implemented Local Evaluation Observability

Evaluation-service emits:
- HTTP request traces and metrics
- evaluation run creation spans
- workflow evidence loading spans
- evaluator execution spans
- evaluation result persistence spans
- structured JSON logs for run start, completion, failure, and result persistence
- Prometheus metrics for run counts, run durations, result counts, evidence-consistency signals, and prompt-attributed result status

The local Grafana stack includes:
- `AegisFlow - Evaluation Quality`

Metric labels intentionally avoid workflow IDs, evaluation run IDs, trace IDs, borrower values, prompt content, document content, approval comments, and full model outputs.

## Current Phase 7 Boundary

Evaluation results are quality telemetry and governance support only.

Evaluation must not:
- approve workflows
- reject workflows
- complete workflows
- mutate workflow state
- bypass human review
- replace workflow timelines, approval records, audit records, or workflow-engine state
- call production mortgage systems
- store raw document contents, borrower PII, secrets, prompt content, approval comments as scoring metadata, or full model outputs
