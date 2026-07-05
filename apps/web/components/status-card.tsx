import type { ReactNode } from "react";

type StatusCardProps = {
  label: string;
  value: string | number;
  /** Raw code shown below the human label (mono, no wrap). */
  monoCode?: string;
  tone?: "default" | "pass" | "warn" | "fail";
  icon?: ReactNode;
  /** Keep metric values on one line (counts, PASS/FAIL). */
  compactValue?: boolean;
};

const toneClasses = {
  default: "border-navy-border text-accent-cyan",
  pass: "border-accent-teal/50 text-accent-teal",
  warn: "border-orange-400/50 text-orange-400",
  fail: "border-red-400/50 text-red-400",
};

export function StatusCard({
  label,
  value,
  monoCode,
  tone = "default",
  icon,
  compactValue = false,
}: StatusCardProps) {
  const valueClass = compactValue
    ? "text-3xl font-bold leading-none tracking-tight whitespace-nowrap tabular-nums sm:text-4xl"
    : "text-xl font-bold leading-snug tracking-tight sm:text-2xl";

  return (
    <div
      className={`flex min-h-[7.5rem] flex-col rounded-xl border bg-navy-surface p-5 shadow-lg shadow-black/20 ${toneClasses[tone]}`}
    >
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[#8ba3c7]">
        {icon}
        <span className="leading-snug">{label}</span>
      </div>
      <div className={`mt-auto ${valueClass}`}>{value}</div>
      {monoCode ? (
        <div className="mt-2 font-mono text-[11px] tracking-wide text-[#8ba3c7] whitespace-nowrap sm:text-xs">
          {monoCode}
        </div>
      ) : null}
    </div>
  );
}
