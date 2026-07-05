import type { MemoryVerdict } from "@/lib/types";

const verdictTone: Record<string, string> = {
  USE: "bg-teal-500/20 text-teal-300 border-teal-500/40",
  INSPECT: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  AVOID: "bg-red-500/20 text-red-300 border-red-500/40",
};

export function MemoryVerdictTable({ verdicts }: { verdicts: MemoryVerdict[] }) {
  return (
    <section className="rounded-xl border border-navy-border bg-navy-surface p-5">
      <h2 className="text-lg font-semibold text-[#e8f4ff]">MemoryGate verdicts</h2>
      <p className="mb-4 mt-1 text-sm text-[#8ba3c7]">
        Similarity retrieved candidates. MemoryGate blocked unsafe memory before action.
      </p>
      <div className="rg-table-scroll">
        <table className="rg-table min-w-[40rem]">
          <thead>
            <tr className="border-b border-navy-border">
              <th className="w-[10rem]">Memory label</th>
              <th className="w-[5rem]">Score</th>
              <th className="w-[6rem]">Verdict</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {verdicts.map((v) => (
              <tr key={v.memory_id} className="border-b border-navy-border/50 hover:bg-white/5">
                <td className="font-medium">{v.label}</td>
                <td className="whitespace-nowrap font-mono text-accent-cyan">
                  {v.similarity_score != null ? v.similarity_score.toFixed(3) : "—"}
                </td>
                <td>
                  <span
                    className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-semibold ${
                      verdictTone[v.verdict] ?? "bg-slate-500/20 text-slate-300"
                    }`}
                  >
                    {v.verdict}
                  </span>
                </td>
                <td className="text-[#8ba3c7]">{v.reason}</td>
              </tr>
            ))}
            {!verdicts.length && (
              <tr>
                <td colSpan={4} className="py-4 text-[#8ba3c7]">
                  No memory verdicts recorded.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
