# Operator Console

## Purpose

The operator-console is the local frontend surface for AegisFlow human review workflows.

Current scope:
- display workflows waiting in `HUMAN_REVIEW_REQUIRED`
- show queue summary counts
- fetch queue and workflow review context from gateway-api
- display workflow timeline, agent execution records, tool invocation records, and approval history
- submit approval and rejection decisions through gateway-api
- preserve gateway-api as the only external workflow API boundary

The operator-console does not call agent-runtime, tool-runtime, or workflow-engine directly.

## Local Development

Start through Docker Compose from the repository root:

```powershell
docker compose -f infrastructure/local-dev/docker-compose.yml up -d operator-console
```

Open:

```text
http://localhost:3000
```

The console expects gateway-api at:

```text
http://localhost:8000
```

Override with:

```text
VITE_GATEWAY_API_URL
```

## Validation

From `apps/operator-console`:

```powershell
npm install
npm run build
```
