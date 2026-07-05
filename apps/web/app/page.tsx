import { DashboardView } from "@/components/dashboard-view";
import { fetchLatestDashboard, listIncidents } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [data, incidents] = await Promise.all([fetchLatestDashboard(), listIncidents()]);

  if (!data) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16 text-center">
        <h1 className="text-2xl font-bold">RelayGuard</h1>
        <p className="mt-4 text-[#8ba3c7]">
          No incidents found. Run <code className="text-accent-cyan">scripts/run-demo</code> first.
        </p>
      </main>
    );
  }

  return <DashboardView data={data} incidents={incidents} />;
}
