import type { ActionLedgerEntry } from "@/lib/types";

const statusTone: Record<string, string> = {
  committed: "text-accent-teal",
  reserved: "text-accent-cyan",
  rejected: "text-red-400",
};

export function ActionLedger({ ledger }: { ledger: ActionLedgerEntry[] }) {
  return (
    <section className="rounded-xl border border-navy-border bg-navy-surface p-5">
      <h2 className="mb-4 text-lg font-semibold">Action ledger</h2>
      <div className="rg-table-scroll">
        <table className="rg-table min-w-[44rem]">
          <thead>
            <tr className="border-b border-navy-border">
              <th className="w-[9rem]">Action type</th>
              <th>Idempotency key</th>
              <th className="w-[7rem]">Status</th>
              <th>Result ID</th>
            </tr>
          </thead>
          <tbody>
            {ledger.map((row) => (
              <tr key={row.idempotency_key} className="border-b border-navy-border/50 hover:bg-white/5">
                <td className="whitespace-nowrap font-semibold">{row.action_type}</td>
                <td className="rg-mono-id text-[#8ba3c7]">{row.idempotency_key}</td>
                <td className={`whitespace-nowrap font-semibold uppercase ${statusTone[row.status] ?? ""}`}>
                  {row.status}
                </td>
                <td className="rg-mono-id">{row.result_id ?? "—"}</td>
              </tr>
            ))}
            {!ledger.length && (
              <tr>
                <td colSpan={4} className="py-4 text-[#8ba3c7]">
                  No ledger entries.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
