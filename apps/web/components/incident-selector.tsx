"use client";

import type { IncidentSummary } from "@/lib/types";

type Props = {
  incidents: IncidentSummary[];
  currentId: string;
};

export function IncidentSelector({ incidents, currentId }: Props) {
  return (
    <form className="flex flex-wrap items-center gap-3" action="/incident" method="get">
      <label htmlFor="incident-select" className="text-sm text-[#8ba3c7]">
        Incident
      </label>
      <select
        id="incident-select"
        name="id"
        defaultValue={currentId}
        className="min-w-[14rem] max-w-full rounded-lg border border-navy-border bg-[#0b1220] px-3 py-2 text-sm text-[#e8f4ff]"
        onChange={(e) => {
          window.location.href = `/incident/${e.target.value}`;
        }}
      >
        {incidents.map((inc) => (
          <option key={inc.incident_id} value={inc.incident_id}>
            {inc.title} ({inc.invariant_status ?? "—"})
          </option>
        ))}
      </select>
    </form>
  );
}
