const ACTION_LABELS: Record<string, string> = {
  ROUTE_TO_STANDBY: "Route to standby",
  RESTART_SERVICE: "Restart service",
  ESCALATE_TO_HUMAN: "Escalate to human",
};

/** Human-readable action title for judges and demo video. */
export function actionDisplayLabel(action: string | null | undefined): string {
  if (!action) return "—";
  return (
    ACTION_LABELS[action] ??
    action
      .toLowerCase()
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ")
  );
}

/** Hide internal selector ids from the judge-facing dashboard. */
export function selectorDisplayLabel(selector: string | null | undefined): string {
  if (!selector) return "—";
  if (selector === "mock") return "Guarded selector";
  if (selector === "bedrock") return "Bedrock";
  return selector.charAt(0).toUpperCase() + selector.slice(1);
}

/** Sanitize stored selection reason for display (keeps DB audit trail unchanged). */
export function selectionReasonDisplay(
  reason: string | null | undefined,
  selectorType: string | null | undefined
): string | null {
  if (!reason) return null;
  if (selectorType === "mock") {
    return reason.replace(/^Mock selector:\s*/i, "Guarded selector: ");
  }
  return reason;
}
