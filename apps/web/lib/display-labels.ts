const ACTION_LABELS: Record<string, string> = {
  ROUTE_TO_STANDBY: "Route to standby",
  RESTART_SERVICE: "Restart service",
  ESCALATE_TO_HUMAN: "Escalate to human",
};

const SELECTOR_LABELS: Record<string, string> = {
  mock: "Guarded selector",
  bedrock: "Amazon Bedrock",
};

const SELECTOR_META: Record<string, string | null> = {
  mock: "local mock",
  bedrock: null,
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

/** Judge-facing selector title (raw selector_type preserved in JSON/API). */
export function selectorDisplayLabel(selector: string | null | undefined): string {
  if (!selector) return "—";
  return SELECTOR_LABELS[selector] ?? selector.charAt(0).toUpperCase() + selector.slice(1);
}

/** Small metadata line under selector label (e.g. local mock). */
export function selectorMetaLabel(selector: string | null | undefined): string | null {
  if (!selector) return null;
  return SELECTOR_META[selector] ?? null;
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
