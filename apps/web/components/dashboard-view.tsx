import { Activity, CheckCircle, Shield, XCircle } from "lucide-react";

import { ActionLedger } from "@/components/action-ledger";
import { AuditSummary } from "@/components/audit-summary";
import { ExecutionTimeline } from "@/components/execution-timeline";
import { IncidentSelector } from "@/components/incident-selector";
import { MemoryVerdictTable } from "@/components/memory-verdict-table";
import { StatusCard } from "@/components/status-card";
import type { DashboardViewModel, IncidentSummary } from "@/lib/types";
import {
  actionDisplayLabel,
  selectionReasonDisplay,
  selectorDisplayLabel,
  selectorMetaLabel,
} from "@/lib/display-labels";

type Props = {
  data: DashboardViewModel;
  incidents: IncidentSummary[];
};

export function DashboardView({ data, incidents }: Props) {
  const pass = data.invariant_status === "PASS";
  const actionLabel = actionDisplayLabel(data.selected_action);
  const selectorLabel = selectorDisplayLabel(data.selector_type);
  const selectorMeta = selectorMetaLabel(data.selector_type);
  const reasonLabel = selectionReasonDisplay(data.selection_reason, data.selector_type);

  return (
    <main className="mx-auto min-h-screen max-w-[1600px] px-8 py-8">
      <header className="mb-8">
        <div className="mb-2 flex items-center gap-3">
          <Shield className="h-8 w-8 text-accent-cyan" />
          <h1 className="text-3xl font-bold tracking-tight md:text-4xl">RelayGuard</h1>
        </div>
        <p className="text-lg text-[#8ba3c7]">Crash-safe memory for incident agents</p>
      </header>

      <div className="mb-6 grid gap-5 rounded-xl border border-navy-border bg-navy-surface p-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
        <div className="min-w-0 space-y-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[#8ba3c7]">Incident</div>
            <h2 className="mt-1 text-xl font-semibold leading-snug md:text-2xl">{data.incident_title}</h2>
            <p className="rg-mono-id mt-2 text-accent-cyan">{data.incident_id}</p>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-[#8ba3c7]">
            <span>
              Selected: <strong className="text-[#e8f4ff]">{actionLabel}</strong>
            </span>
            <span>
              Selector:{" "}
              <strong className="text-[#e8f4ff]">{selectorLabel}</strong>
              {selectorMeta ? (
                <span className="ml-1 font-mono text-xs text-[#6b829e]">({selectorMeta})</span>
              ) : null}
            </span>
            <span>
              Confidence:{" "}
              <strong className="text-[#e8f4ff]">
                {data.selection_confidence != null ? data.selection_confidence.toFixed(2) : "—"}
              </strong>
            </span>
          </div>
          {reasonLabel && (
            <p className="max-w-4xl text-sm leading-relaxed text-[#c5d9f0]">{reasonLabel}</p>
          )}
        </div>
        {incidents.length > 0 && (
          <div className="shrink-0 lg:justify-self-end">
            <IncidentSelector incidents={incidents} currentId={String(data.incident_id)} />
          </div>
        )}
      </div>

      <div className="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard
          label="Selected action"
          value={actionLabel}
          monoCode={data.selected_action ?? undefined}
          icon={<Activity className="h-4 w-4" />}
        />
        <StatusCard
          label="Committed actions"
          value={data.committed_action_count}
          tone="pass"
          compactValue
        />
        <StatusCard
          label="Stale commits rejected"
          value={data.stale_commit_rejection_count}
          tone={data.stale_commit_rejection_count > 0 ? "warn" : "default"}
          compactValue
        />
        <StatusCard
          label="Invariants"
          value={data.invariant_status}
          tone={pass ? "pass" : "fail"}
          icon={pass ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          compactValue
        />
      </div>

      <div className="mb-8 space-y-6">
        <MemoryVerdictTable verdicts={data.memory_verdicts} />
        <ExecutionTimeline timeline={data.execution_timeline} />
      </div>

      <div className="space-y-6">
        <ActionLedger ledger={data.action_ledger} />
        <AuditSummary data={data} />
      </div>
    </main>
  );
}
