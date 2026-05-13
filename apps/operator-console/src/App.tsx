import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  FileText,
  History,
  RefreshCw,
  Send,
  ShieldCheck,
  UserCheck,
  Wrench,
  XCircle,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  gatewayBaseUrl,
  getHumanReviewQueue,
  getWorkflowRecoveryActions,
  getWorkflowReplayRuns,
  getWorkflowReviewContext,
  submitApprovalDecision,
} from "./api";
import type {
  AgentExecutionRecord,
  ApprovalDecision,
  ApprovalDecisionResponse,
  HumanReviewQueueItem,
  RecoveryAction,
  ReplayRun,
  TimelineEntry,
  ToolInvocationRecord,
  WorkflowReviewContext,
} from "./types";

type LoadState = "idle" | "loading" | "ready" | "error";
type DecisionState = "idle" | "submitting" | "submitted" | "error";

const priorityClass: Record<string, string> = {
  LOW: "bg-slate-100 text-slate-700 ring-slate-200",
  NORMAL: "bg-sky-50 text-sky-700 ring-sky-200",
  HIGH: "bg-amber-50 text-amber-800 ring-amber-200",
  URGENT: "bg-rose-50 text-rose-700 ring-rose-200",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function caseReferenceFromMetadata(metadata: Record<string, unknown>): string {
  const caseReference = metadata.case_reference;
  return typeof caseReference === "string" && caseReference.trim() ? caseReference : "Unassigned case";
}

function caseReferenceFor(workflow: HumanReviewQueueItem): string {
  return caseReferenceFromMetadata(workflow.metadata);
}

function summarizeQueue(items: HumanReviewQueueItem[]) {
  return {
    total: items.length,
    urgent: items.filter((item) => item.priority === "URGENT").length,
    high: items.filter((item) => item.priority === "HIGH").length,
  };
}

function compactJson(value: Record<string, unknown>): string {
  if (Object.keys(value).length === 0) {
    return "No metadata";
  }
  return JSON.stringify(value, null, 2);
}

export default function App() {
  const [items, setItems] = useState<HumanReviewQueueItem[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [reviewContext, setReviewContext] = useState<WorkflowReviewContext | null>(null);
  const [replayRuns, setReplayRuns] = useState<ReplayRun[]>([]);
  const [recoveryActions, setRecoveryActions] = useState<RecoveryAction[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [contextState, setContextState] = useState<LoadState>("idle");
  const [decisionState, setDecisionState] = useState<DecisionState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [contextError, setContextError] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [decisionResult, setDecisionResult] = useState<ApprovalDecisionResponse | null>(null);
  const [lastLoadedAt, setLastLoadedAt] = useState<Date | null>(null);

  const loadQueue = useCallback(async () => {
    setLoadState("loading");
    setError(null);
    try {
      const queue = await getHumanReviewQueue();
      setItems(queue.items);
      setLastLoadedAt(new Date());
      setLoadState("ready");
      if (!selectedWorkflowId && queue.items.length > 0) {
        setSelectedWorkflowId(queue.items[0].workflow_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load review queue");
      setLoadState("error");
    }
  }, [selectedWorkflowId]);

  const loadReviewContext = useCallback(async (workflowId: string) => {
    setContextState("loading");
    setContextError(null);
    setDecisionError(null);
    setDecisionResult(null);
    try {
      const [context, replayResponse, recoveryResponse] = await Promise.all([
        getWorkflowReviewContext(workflowId),
        getWorkflowReplayRuns(workflowId),
        getWorkflowRecoveryActions(workflowId),
      ]);
      setReviewContext(context);
      setReplayRuns(replayResponse.runs);
      setRecoveryActions(recoveryResponse.actions);
      setContextState("ready");
    } catch (err) {
      setReviewContext(null);
      setReplayRuns([]);
      setRecoveryActions([]);
      setContextError(err instanceof Error ? err.message : "Unable to load workflow review context");
      setContextState("error");
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (selectedWorkflowId) {
      void loadReviewContext(selectedWorkflowId);
    }
  }, [selectedWorkflowId, loadReviewContext]);

  const summary = useMemo(() => summarizeQueue(items), [items]);

  const handleSelect = (workflowId: string) => {
    setSelectedWorkflowId(workflowId);
  };

  const handleDecisionSubmitted = async (result: ApprovalDecisionResponse) => {
    setDecisionResult(result);
    setReviewContext((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        workflow: result.workflow,
        approvals: [...current.approvals, result.approval],
      };
    });
    await loadQueue();
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1480px] items-center justify-between gap-4 px-6 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-emerald-600 text-white">
                <ShieldCheck size={20} aria-hidden="true" />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-normal">AegisFlow Operator Console</h1>
                <p className="text-sm text-slate-600">Human review workspace</p>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadQueue()}
            className="inline-flex h-10 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={loadState === "loading"}
            title="Refresh review queue"
          >
            <RefreshCw size={16} aria-hidden="true" className={loadState === "loading" ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      <div className="mx-auto grid max-w-[1480px] gap-6 px-6 py-6 xl:grid-cols-[300px_minmax(460px,0.95fr)_minmax(520px,1.25fr)]">
        <aside className="space-y-4">
          <section className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-800">Queue Snapshot</h2>
            <dl className="mt-4 grid grid-cols-3 gap-3 xl:grid-cols-1">
              <Metric label="Awaiting review" value={summary.total} />
              <Metric label="Urgent" value={summary.urgent} />
              <Metric label="High" value={summary.high} />
            </dl>
          </section>

          <section className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-800">Connection</h2>
            <div className="mt-3 space-y-2 text-sm text-slate-600">
              <p className="break-all">{gatewayBaseUrl}</p>
              <p>{lastLoadedAt ? `Loaded ${formatDate(lastLoadedAt.toISOString())}` : "Waiting for first load"}</p>
            </div>
          </section>
        </aside>

        <section className="min-w-0 rounded-md border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Human Review Queue</h2>
              <p className="text-sm text-slate-600">Select a workflow to inspect and decision</p>
            </div>
            <StatusIndicator state={loadState} />
          </div>

          {loadState === "error" ? (
            <AlertMessage tone="danger" message={error ?? "Queue unavailable"} />
          ) : null}

          {loadState !== "error" && items.length === 0 && loadState !== "loading" ? (
            <div className="px-4 py-10 text-center">
              <CheckCircle2 className="mx-auto text-emerald-600" size={28} aria-hidden="true" />
              <p className="mt-3 text-sm font-medium text-slate-800">No workflows are waiting for review</p>
            </div>
          ) : null}

          {items.length > 0 ? (
            <QueueTable items={items} selectedWorkflowId={selectedWorkflowId} onSelect={handleSelect} />
          ) : null}
        </section>

        <section className="min-w-0 rounded-md border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Workflow Review</h2>
              <p className="text-sm text-slate-600">Workflow facts, AI assistance, tool outputs, and human decision</p>
            </div>
            <StatusIndicator state={contextState} />
          </div>

          {!selectedWorkflowId ? (
            <div className="px-4 py-10 text-center">
              <FileText className="mx-auto text-slate-400" size={28} aria-hidden="true" />
              <p className="mt-3 text-sm font-medium text-slate-800">Select a workflow to begin review</p>
            </div>
          ) : null}

          {contextState === "error" ? (
            <AlertMessage tone="danger" message={contextError ?? "Review context unavailable"} />
          ) : null}

          {contextState === "ready" && reviewContext ? (
            <ReviewWorkspace
              context={reviewContext}
              decisionState={decisionState}
              decisionError={decisionError}
              decisionResult={decisionResult}
              replayRuns={replayRuns}
              recoveryActions={recoveryActions}
              onDecisionStateChange={setDecisionState}
              onDecisionError={setDecisionError}
              onDecisionSubmitted={(result) => void handleDecisionSubmitted(result)}
            />
          ) : null}
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 px-3 py-2">
      <dt className="text-xs font-medium uppercase text-slate-500">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold text-slate-950">{value}</dd>
    </div>
  );
}

function StatusIndicator({ state }: { state: LoadState }) {
  if (state === "loading") {
    return (
      <span className="inline-flex items-center gap-2 rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
        <Clock3 size={14} aria-hidden="true" />
        Loading
      </span>
    );
  }

  if (state === "error") {
    return (
      <span className="inline-flex items-center gap-2 rounded-md bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-700">
        <AlertCircle size={14} aria-hidden="true" />
        Attention
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-2 rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
      <CheckCircle2 size={14} aria-hidden="true" />
      Ready
    </span>
  );
}

function AlertMessage({ tone, message }: { tone: "danger" | "success"; message: string }) {
  const style =
    tone === "danger"
      ? "border-rose-200 bg-rose-50 text-rose-800"
      : "border-emerald-200 bg-emerald-50 text-emerald-800";
  const Icon = tone === "danger" ? AlertCircle : CheckCircle2;
  return (
    <div className={`m-4 flex items-start gap-3 rounded-md border px-3 py-3 text-sm ${style}`}>
      <Icon size={18} aria-hidden="true" className="mt-0.5 shrink-0" />
      <p>{message}</p>
    </div>
  );
}

function QueueTable({
  items,
  selectedWorkflowId,
  onSelect,
}: {
  items: HumanReviewQueueItem[];
  selectedWorkflowId: string | null;
  onSelect: (workflowId: string) => void;
}) {
  return (
    <div className="divide-y divide-slate-200">
      {items.map((item) => {
        const isSelected = item.workflow_id === selectedWorkflowId;
        return (
          <button
            type="button"
            key={item.workflow_id}
            onClick={() => onSelect(item.workflow_id)}
            className={`block w-full px-4 py-3 text-left hover:bg-slate-50 ${
              isSelected ? "bg-emerald-50 ring-1 ring-inset ring-emerald-200" : "bg-white"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-slate-900">{caseReferenceFor(item)}</div>
                <div className="mt-1 truncate font-mono text-xs text-slate-600">{item.workflow_id}</div>
              </div>
              <span
                className={`shrink-0 rounded-md px-2 py-1 text-xs font-semibold ring-1 ${
                  priorityClass[item.priority] ?? priorityClass.NORMAL
                }`}
              >
                {item.priority}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
              <span>{item.state}</span>
              <span className="text-right">{formatDate(item.updated_at)}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function ReviewWorkspace({
  context,
  decisionState,
  decisionError,
  decisionResult,
  replayRuns,
  recoveryActions,
  onDecisionStateChange,
  onDecisionError,
  onDecisionSubmitted,
}: {
  context: WorkflowReviewContext;
  decisionState: DecisionState;
  decisionError: string | null;
  decisionResult: ApprovalDecisionResponse | null;
  replayRuns: ReplayRun[];
  recoveryActions: RecoveryAction[];
  onDecisionStateChange: (state: DecisionState) => void;
  onDecisionError: (message: string | null) => void;
  onDecisionSubmitted: (result: ApprovalDecisionResponse) => void;
}) {
  const workflow = context.workflow;
  const isReviewable = workflow.state === "HUMAN_REVIEW_REQUIRED";

  return (
    <div className="space-y-4 p-4">
      <section className="rounded-md border border-slate-200 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-lg font-semibold text-slate-950">{caseReferenceFromMetadata(workflow.metadata)}</h3>
            <p className="mt-1 break-all font-mono text-xs text-slate-600">{workflow.workflow_id}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-md bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200">
              {workflow.state}
            </span>
            <span
              className={`rounded-md px-2 py-1 text-xs font-semibold ring-1 ${
                priorityClass[workflow.priority] ?? priorityClass.NORMAL
              }`}
            >
              {workflow.priority}
            </span>
          </div>
        </div>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <Definition label="Workflow type" value={workflow.workflow_type} />
          <Definition label="Updated" value={formatDate(workflow.updated_at)} />
          <Definition label="Correlation ID" value={workflow.correlation_id} />
          <Definition label="Temporal workflow" value={workflow.temporal_workflow_id ?? "Not assigned"} />
        </dl>
      </section>

      {decisionResult ? (
        <AlertMessage
          tone="success"
          message={`Decision recorded as ${decisionResult.approval.decision}. Workflow state is ${decisionResult.workflow.state}.`}
        />
      ) : null}

      {decisionError ? <AlertMessage tone="danger" message={decisionError} /> : null}

      <DecisionForm
        workflowId={workflow.workflow_id}
        disabled={!isReviewable || decisionState === "submitting"}
        onDecisionStateChange={onDecisionStateChange}
        onDecisionError={onDecisionError}
        onDecisionSubmitted={onDecisionSubmitted}
      />

      <div className="grid gap-4 2xl:grid-cols-2">
        <TimelinePanel entries={context.timeline} />
        <ReplayRecoveryPanel replayRuns={replayRuns} recoveryActions={recoveryActions} />
        <MetadataPanel title="Workflow Metadata" metadata={workflow.metadata} />
        <AgentPanel records={context.agent_executions} />
        <ToolPanel records={context.tool_invocations} />
        <ApprovalPanel records={context.approvals} />
      </div>
    </div>
  );
}

function Definition({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md border border-slate-200 px-3 py-2">
      <dt className="text-xs font-medium uppercase text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-slate-900">{value}</dd>
    </div>
  );
}

function DecisionForm({
  workflowId,
  disabled,
  onDecisionStateChange,
  onDecisionError,
  onDecisionSubmitted,
}: {
  workflowId: string;
  disabled: boolean;
  onDecisionStateChange: (state: DecisionState) => void;
  onDecisionError: (message: string | null) => void;
  onDecisionSubmitted: (result: ApprovalDecisionResponse) => void;
}) {
  const [actorId, setActorId] = useState("operator-local");
  const [decision, setDecision] = useState<ApprovalDecision>("APPROVED");
  const [comment, setComment] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    onDecisionError(null);

    if (!actorId.trim()) {
      onDecisionError("Operator identity is required.");
      onDecisionStateChange("error");
      return;
    }

    if (!comment.trim()) {
      onDecisionError("Decision comment is required.");
      onDecisionStateChange("error");
      return;
    }

    onDecisionStateChange("submitting");
    try {
      const result = await submitApprovalDecision(workflowId, actorId.trim(), {
        decision,
        decision_reason: decision === "APPROVED" ? "exception_review_completed" : "exception_review_incomplete",
        comment: comment.trim(),
        metadata: { review_channel: "operator_console" },
      });
      setComment("");
      onDecisionStateChange("submitted");
      onDecisionSubmitted(result);
    } catch (err) {
      onDecisionError(err instanceof Error ? err.message : "Unable to submit decision");
      onDecisionStateChange("error");
    }
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="rounded-md border border-slate-200 p-4">
      <div className="flex items-center gap-2">
        <UserCheck size={18} aria-hidden="true" className="text-slate-600" />
        <h3 className="text-sm font-semibold text-slate-900">Human Decision</h3>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,220px)_minmax(0,1fr)]">
        <label className="block">
          <span className="text-xs font-medium uppercase text-slate-500">Operator ID</span>
          <input
            value={actorId}
            onChange={(event) => setActorId(event.target.value)}
            className="mt-1 h-10 w-full rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
            disabled={disabled}
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium uppercase text-slate-500">Decision</span>
          <select
            value={decision}
            onChange={(event) => setDecision(event.target.value as ApprovalDecision)}
            className="mt-1 h-10 w-full rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
            disabled={disabled}
          >
            <option value="APPROVED">Approve</option>
            <option value="REJECTED">Reject</option>
          </select>
        </label>
      </div>
      <label className="mt-3 block">
        <span className="text-xs font-medium uppercase text-slate-500">Decision Comment</span>
        <textarea
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          rows={3}
          className="mt-1 w-full resize-y rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
          disabled={disabled}
        />
      </label>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="submit"
          className="inline-flex h-10 items-center gap-2 rounded-md bg-emerald-700 px-3 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={disabled}
          title="Submit human review decision"
        >
          {decision === "APPROVED" ? <Send size={16} aria-hidden="true" /> : <XCircle size={16} aria-hidden="true" />}
          Submit {decision === "APPROVED" ? "Approval" : "Rejection"}
        </button>
      </div>
    </form>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-md border border-slate-200">
      <h3 className="border-b border-slate-200 px-3 py-2 text-sm font-semibold text-slate-900">{title}</h3>
      <div className="p-3">{children}</div>
    </section>
  );
}

function TimelinePanel({ entries }: { entries: TimelineEntry[] }) {
  return (
    <Panel title="Timeline">
      <div className="space-y-3">
        {entries.map((entry) => (
          <div key={entry.timeline_entry_id} className="rounded-md border border-slate-200 px-3 py-2">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-medium text-slate-900">{entry.message}</p>
              <span className="shrink-0 text-xs text-slate-500">{formatDate(entry.created_at)}</span>
            </div>
            <p className="mt-1 text-xs text-slate-600">
              {entry.entry_type}
              {entry.state ? ` / ${entry.state}` : ""}
            </p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function MetadataPanel({ title, metadata }: { title: string; metadata: Record<string, unknown> }) {
  return (
    <Panel title={title}>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-slate-950 p-3 text-xs text-slate-100">
        {compactJson(metadata)}
      </pre>
    </Panel>
  );
}

function ReplayRecoveryPanel({
  replayRuns,
  recoveryActions,
}: {
  replayRuns: ReplayRun[];
  recoveryActions: RecoveryAction[];
}) {
  const latestReplay = replayRuns.length > 0 ? replayRuns[replayRuns.length - 1] : undefined;
  const latestRecovery = recoveryActions.length > 0 ? recoveryActions[recoveryActions.length - 1] : undefined;

  return (
    <Panel title="Replay And Recovery">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border border-slate-200 px-3 py-2">
          <div className="flex items-center gap-2">
            <History size={16} aria-hidden="true" className="text-slate-600" />
            <p className="text-sm font-semibold text-slate-900">Replay Runs</p>
          </div>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{replayRuns.length}</p>
          <p className="mt-1 text-xs text-slate-600">
            {latestReplay
              ? `${latestReplay.replay_mode} / ${latestReplay.status} / ${latestReplay.steps.length} steps`
              : "No replay runs recorded"}
          </p>
        </div>
        <div className="rounded-md border border-slate-200 px-3 py-2">
          <div className="flex items-center gap-2">
            <Wrench size={16} aria-hidden="true" className="text-slate-600" />
            <p className="text-sm font-semibold text-slate-900">Recovery Actions</p>
          </div>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{recoveryActions.length}</p>
          <p className="mt-1 text-xs text-slate-600">
            {latestRecovery
              ? `${latestRecovery.action_type} / ${latestRecovery.status}`
              : "No recovery actions recorded"}
          </p>
        </div>
      </div>

      {latestReplay ? (
        <div className="mt-3 rounded-md border border-slate-200 px-3 py-2">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-medium text-slate-900">{latestReplay.replay_mode}</p>
            <span className="shrink-0 text-xs font-semibold text-emerald-700">{latestReplay.status}</span>
          </div>
          <p className="mt-1 break-all font-mono text-xs text-slate-600">{latestReplay.replay_run_id}</p>
          <p className="mt-2 text-xs text-slate-600">{formatDate(latestReplay.created_at)}</p>
        </div>
      ) : null}

      {latestRecovery ? (
        <div className="mt-3 rounded-md border border-slate-200 px-3 py-2">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-medium text-slate-900">{latestRecovery.action_type}</p>
            <span className="shrink-0 text-xs font-semibold text-amber-700">{latestRecovery.status}</span>
          </div>
          <p className="mt-1 break-all font-mono text-xs text-slate-600">{latestRecovery.recovery_action_id}</p>
          <p className="mt-2 text-xs text-slate-600">{latestRecovery.target_resource_type}</p>
        </div>
      ) : null}
    </Panel>
  );
}

function AgentPanel({ records }: { records: AgentExecutionRecord[] }) {
  return (
    <Panel title="Agent Executions">
      <div className="space-y-3">
        {records.length === 0 ? <p className="text-sm text-slate-600">No agent execution records.</p> : null}
        {records.map((record) => (
          <div key={record.agent_execution_id} className="rounded-md border border-slate-200 px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <p className="font-medium text-slate-900">{record.agent_id}</p>
              <span className="text-xs font-semibold text-emerald-700">{record.validation_status}</span>
            </div>
            <p className="mt-1 text-xs text-slate-600">
              {record.prompt_id} v{record.prompt_version} / confidence {record.confidence_score.toFixed(2)}
            </p>
            <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap rounded-md bg-slate-100 p-2 text-xs text-slate-800">
              {compactJson(record.output)}
            </pre>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ToolPanel({ records }: { records: ToolInvocationRecord[] }) {
  return (
    <Panel title="Tool Invocations">
      <div className="space-y-3">
        {records.length === 0 ? <p className="text-sm text-slate-600">No tool invocation records.</p> : null}
        {records.map((record) => (
          <div key={record.tool_invocation_id} className="rounded-md border border-slate-200 px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <p className="font-medium text-slate-900">{record.tool_id}</p>
              <span className="text-xs font-semibold text-emerald-700">{record.permission_status}</span>
            </div>
            <p className="mt-1 text-xs text-slate-600">
              {record.status} / input {record.input_validation_status} / output {record.output_validation_status}
            </p>
            <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap rounded-md bg-slate-100 p-2 text-xs text-slate-800">
              {compactJson(record.output)}
            </pre>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ApprovalPanel({ records }: { records: WorkflowReviewContext["approvals"] }) {
  return (
    <Panel title="Approval Records">
      <div className="space-y-3">
        {records.length === 0 ? <p className="text-sm text-slate-600">No approval records have been submitted.</p> : null}
        {records.map((record) => (
          <div key={record.approval_id} className="rounded-md border border-slate-200 px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <p className="font-medium text-slate-900">{record.decision}</p>
              <span className="text-xs text-slate-500">{formatDate(record.reviewed_at)}</span>
            </div>
            <p className="mt-1 text-xs text-slate-600">{record.reviewed_by}</p>
            <p className="mt-2 text-sm text-slate-800">{record.comment}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}
