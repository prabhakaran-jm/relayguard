import { NextResponse } from "next/server";

import { listIncidents } from "@/lib/db";
import { redactUnknown } from "@/lib/redaction";

export async function GET() {
  try {
    const incidents = await listIncidents();
    return NextResponse.json(redactUnknown({ incidents }));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to list incidents";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
