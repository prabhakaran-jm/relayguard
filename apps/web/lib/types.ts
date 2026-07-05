export type IncidentSummary = {
  incident_id: string;
  title: string;
  status: string;
  created_at: string | null;
  invariant_status: "PASS" | "FAIL" | null;
};

export type MemoryVerdict = {
  memory_id: string;
  label: string;
  verdict: string;
  reason: string;
  similarity_score: number | null;
};

export type TimelineEntry = {
  event_type: string;
  worker: string | null;
  lease_epoch: number | null;
  summary: string;
  created_at: string | null;
};

export type ActionLedgerEntry = {
  action_type: string;
  idempotency_key: string;
  status: string;
  result_id: string | null;
};

export type AuditReport = {
  incident_id: string;
  incident_title: string;
  selected_action: string | null;
  selector_type: string | null;
  selection_reason: string | null;
  selection_confidence: number | null;
  fallback_used: boolean;
  used_memory_ids: string[];
  inspected_memory_ids: string[];
  memory_verdicts: MemoryVerdict[];
  execution_timeline: TimelineEntry[];
  action_ledger: ActionLedgerEntry[];
  committed_action_count: number;
  stale_commit_rejection_count: number;
  retrieved_memory_count: number;
  blocked_memory_count: number;
  invariant_status: "PASS" | "FAIL";
  invariant_errors: string[];
};

export type DashboardViewModel = AuditReport & {
  proof_counts: {
    committed_action_count: number;
    stale_commit_rejection_count: number;
    retrieved_memory_count: number;
    blocked_memory_count: number;
    invariant_status: "PASS" | "FAIL";
  };
};
