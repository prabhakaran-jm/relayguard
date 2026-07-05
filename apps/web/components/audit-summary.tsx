import { Database } from "lucide-react";

import type { DashboardViewModel } from "@/lib/types";

export function AuditSummary({ data }: { data: DashboardViewModel }) {
  const p = data.proof_counts;
  const pass = p.invariant_status === "PASS";

  return (
    <section className="rounded-xl border border-navy-border bg-navy-surface p-5">
      <div className="mb-4 flex items-center gap-2">
        <Database className="h-5 w-5 text-accent-cyan" />
        <h2 className="text-lg font-semibold">CockroachDB-backed audit proof</h2>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <ProofItem label="Committed actions" value={p.committed_action_count} />
        <ProofItem label="Stale rejections" value={p.stale_commit_rejection_count} />
        <ProofItem label="Memories retrieved" value={p.retrieved_memory_count} />
        <ProofItem label="Memories blocked" value={p.blocked_memory_count} />
        <ProofItem
          label="Invariants"
          value={p.invariant_status}
          highlight={pass ? "pass" : "fail"}
        />
      </div>
      <p className="mt-4 text-sm leading-relaxed text-[#8ba3c7]">
        Similarity retrieves candidates. MemoryGate decides which memories are safe. CockroachDB
        stores the execution state, fencing epoch, action ledger, and audit trail.
      </p>
    </section>
  );
}

function ProofItem({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string | number;
  highlight?: "pass" | "fail";
}) {
  const valueClass =
    highlight === "pass"
      ? "text-accent-teal"
      : highlight === "fail"
        ? "text-red-400"
        : "text-accent-cyan";

  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-[#8ba3c7]">{label}</div>
      <div className={`text-2xl font-bold ${valueClass}`}>{value}</div>
    </div>
  );
}
