import { NextResponse } from "next/server";

import { fetchDashboard } from "@/lib/db";
import { redactUnknown } from "@/lib/redaction";

type Params = { params: Promise<{ incidentId: string }> };

export async function GET(_request: Request, { params }: Params) {
  const { incidentId } = await params;

  try {
    const dashboard = await fetchDashboard(incidentId);

    if (dashboard.incident_title === "(not found)") {
      return NextResponse.json({ error: `Incident ${incidentId} not found` }, { status: 404 });
    }

    return NextResponse.json(
      redactUnknown({
        incident: {
          incident_id: dashboard.incident_id,
          title: dashboard.incident_title,
          status: "completed",
        },
        selected_action: dashboard.selected_action,
        memory_verdicts: dashboard.memory_verdicts,
        execution_timeline: dashboard.execution_timeline,
        action_ledger: dashboard.action_ledger,
        proof_counts: dashboard.proof_counts,
        invariant_status: dashboard.invariant_status,
        selector_type: dashboard.selector_type,
        selection_reason: dashboard.selection_reason,
        selection_confidence: dashboard.selection_confidence,
      })
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to load incident";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
