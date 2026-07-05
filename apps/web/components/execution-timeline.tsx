import type { TimelineEntry } from "@/lib/types";

function eventBorder(eventType: string): string {
  if (eventType === "action.committed") return "border-l-accent-cyan";
  if (eventType === "action.commit_rejected") return "border-l-red-400";
  return "border-l-blue-500/60";
}

export function ExecutionTimeline({ timeline }: { timeline: TimelineEntry[] }) {
  return (
    <section className="rounded-xl border border-navy-border bg-navy-surface p-5">
      <h2 className="mb-4 text-lg font-semibold">Execution timeline</h2>
      <div className="rg-table-scroll">
        <table className="rg-table min-w-[52rem]">
          <thead>
            <tr className="border-b border-navy-border">
              <th className="w-[12rem]">Event</th>
              <th className="w-[6rem]">Worker</th>
              <th className="w-[4rem]">Epoch</th>
              <th>Summary</th>
              <th className="w-[9.5rem]">Created</th>
            </tr>
          </thead>
          <tbody>
            {timeline.map((entry, i) => (
              <tr
                key={`${entry.event_type}-${i}`}
                className={`border-b border-navy-border/50 border-l-2 ${eventBorder(entry.event_type)} hover:bg-white/5`}
              >
                <td className="whitespace-nowrap font-mono text-xs text-accent-cyan">
                  {entry.event_type}
                </td>
                <td className="whitespace-nowrap">{entry.worker ?? "—"}</td>
                <td className="whitespace-nowrap font-mono">{entry.lease_epoch ?? "—"}</td>
                <td className="min-w-[14rem] text-[#c5d9f0]">{entry.summary}</td>
                <td className="whitespace-nowrap font-mono text-xs text-[#8ba3c7]">
                  {entry.created_at ? entry.created_at.slice(0, 19).replace("T", " ") : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
