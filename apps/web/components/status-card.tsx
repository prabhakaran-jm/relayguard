import type { ReactNode } from "react";

type StatusCardProps = {
  label: string;
  value: string | number;
  /** Raw code shown below the human label (mono, no wrap). */
  monoCode?: string;
  tone?: "default" | "pass" | "warn" | "fail";
  icon?: ReactNode;
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
}: StatusCardProps) {
  return (
    <div
      className={`rounded-xl border bg-navy-surface p-5 shadow-lg shadow-black/20 ${toneClasses[tone]}`}
    >
      <div className="mb-2 flex items-center gap-2 text-sm uppercase tracking-wide text-[#8ba3c7]">
        {icon}
        {label}
      </div>
      <div className="text-2xl font-bold leading-snug tracking-tight sm:text-3xl">{value}</div>
      {monoCode ? (
        <div className="mt-2 font-mono text-xs tracking-wide text-[#8ba3c7] whitespace-nowrap">
          {monoCode}
        </div>
      ) : null}
    </div>
  );
}
