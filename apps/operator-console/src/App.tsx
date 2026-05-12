import { AlertCircle, CheckCircle2, Clock3, RefreshCw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { gatewayBaseUrl, getHumanReviewQueue } from "./api";
import type { HumanReviewQueueItem } from "./types";

type LoadState = "idle" | "loading" | "ready" | "error";

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

function caseReferenceFor(workflow: HumanReviewQueueItem): string {
  const caseReference = workflow.metadata.case_reference;
  return typeof caseReference === "string" && caseReference.trim() ? caseReference : "Unassigned case";
}

function summarizeQueue(items: HumanReviewQueueItem[]) {
  return {
    total: items.length,
    urgent: items.filter((item) => item.priority === "URGENT").length,
    high: items.filter((item) => item.priority === "HIGH").length,
  };
}

export default function App() {
  const [items, setItems] = useState<HumanReviewQueueItem[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [lastLoadedAt, setLastLoadedAt] = useState<Date | null>(null);

  const loadQueue = useCallback(async () => {
    setLoadState("loading");
    setError(null);
    try {
      const queue = await getHumanReviewQueue();
      setItems(queue.items);
      setLastLoadedAt(new Date());
      setLoadState("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load review queue");
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const summary = useMemo(() => summarizeQueue(items), [items]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-emerald-600 text-white">
                <ShieldCheck size={20} aria-hidden="true" />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-normal">AegisFlow Operator Console</h1>
                <p className="text-sm text-slate-600">Human review queue</p>
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

      <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <section className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-800">Queue Snapshot</h2>
            <dl className="mt-4 grid grid-cols-3 gap-3 lg:grid-cols-1">
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
              <p className="text-sm text-slate-600">Workflows paused for accountable operator decisioning</p>
            </div>
            <StatusIndicator state={loadState} />
          </div>

          {loadState === "error" ? (
            <div className="flex items-start gap-3 px-4 py-5 text-sm text-rose-700">
              <AlertCircle size={18} aria-hidden="true" className="mt-0.5 shrink-0" />
              <p>{error}</p>
            </div>
          ) : null}

          {loadState !== "error" && items.length === 0 && loadState !== "loading" ? (
            <div className="px-4 py-10 text-center">
              <CheckCircle2 className="mx-auto text-emerald-600" size={28} aria-hidden="true" />
              <p className="mt-3 text-sm font-medium text-slate-800">No workflows are waiting for review</p>
            </div>
          ) : null}

          {items.length > 0 ? <QueueTable items={items} /> : null}
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

function QueueTable({ items }: { items: HumanReviewQueueItem[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full table-fixed border-collapse text-left text-sm">
        <thead className="bg-slate-100 text-xs uppercase text-slate-600">
          <tr>
            <th className="w-[28%] px-4 py-3 font-semibold">Case</th>
            <th className="w-[20%] px-4 py-3 font-semibold">Workflow</th>
            <th className="w-[14%] px-4 py-3 font-semibold">Priority</th>
            <th className="w-[20%] px-4 py-3 font-semibold">Updated</th>
            <th className="w-[18%] px-4 py-3 font-semibold">Correlation</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {items.map((item) => (
            <tr key={item.workflow_id} className="hover:bg-slate-50">
              <td className="px-4 py-3 align-top">
                <div className="font-medium text-slate-900">{caseReferenceFor(item)}</div>
                <div className="mt-1 text-xs text-slate-500">{item.workflow_type}</div>
              </td>
              <td className="px-4 py-3 align-top">
                <div className="font-mono text-xs text-slate-700">{item.workflow_id}</div>
                <div className="mt-1 text-xs font-medium text-emerald-700">{item.state}</div>
              </td>
              <td className="px-4 py-3 align-top">
                <span
                  className={`inline-flex rounded-md px-2 py-1 text-xs font-semibold ring-1 ${
                    priorityClass[item.priority] ?? priorityClass.NORMAL
                  }`}
                >
                  {item.priority}
                </span>
              </td>
              <td className="px-4 py-3 align-top text-slate-700">{formatDate(item.updated_at)}</td>
              <td className="px-4 py-3 align-top">
                <span className="block truncate font-mono text-xs text-slate-600" title={item.correlation_id}>
                  {item.correlation_id}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
