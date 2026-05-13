param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')]
  [string]$WorkflowId,

  [Parameter(Mandatory = $false)]
  [ValidateLength(1, 80)]
  [string]$EventType = "workflow.created",

  [Parameter(Mandatory = $false)]
  [ValidateLength(1, 128)]
  [string]$EventId
)

if (-not $EventId) {
  $EventId = "${WorkflowId}:$EventType"
}

$escapedEventId = $EventId.Replace("'", "''")
$sql = @"
UPDATE workflow_event_outbox
SET
  publish_status = 'FAILED',
  retry_count = 1,
  last_error = 'postman seeded transient broker outage',
  published_at = NULL
WHERE event_id = '$escapedEventId'
RETURNING event_id, workflow_id, event_type, publish_status, retry_count, last_error IS NOT NULL AS last_error_present;
"@

$result = docker exec aegisflow-postgres psql `
  -U aegisflow `
  -d aegisflow `
  -t `
  -A `
  -F "|" `
  -v ON_ERROR_STOP=1 `
  -c $sql

if ($LASTEXITCODE -ne 0) {
  throw "Failed to seed retryable outbox failure for event '$EventId'."
}

$row = ($result | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1)
if (-not $row) {
  throw "No workflow_event_outbox record matched event '$EventId'. Create the workflow first, then rerun this script."
}

Write-Output "Seeded retryable outbox failure:"
Write-Output "event_id|workflow_id|event_type|publish_status|retry_count|last_error_present"
Write-Output $row
