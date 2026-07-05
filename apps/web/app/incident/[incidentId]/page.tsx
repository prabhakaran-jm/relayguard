import { notFound } from "next/navigation";

import { DashboardView } from "@/components/dashboard-view";
import { fetchDashboard, listIncidents } from "@/lib/db";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ incidentId: string }> };

export default async function IncidentPage({ params }: Props) {
  const { incidentId } = await params;

  try {
    const [data, incidents] = await Promise.all([
      fetchDashboard(incidentId),
      listIncidents(),
    ]);

    if (data.incident_title === "(not found)") {
      notFound();
    }

    return <DashboardView data={data} incidents={incidents} />;
  } catch {
    notFound();
  }
}
