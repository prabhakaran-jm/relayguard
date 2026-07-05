const SECRET_PATTERNS = [
  /postgresql:\/\//i,
  /password/i,
  /secret/i,
  /relayguard_app:[^@]+@/i,
];

export function assertNoSecrets(payload: string): void {
  for (const pattern of SECRET_PATTERNS) {
    if (pattern.test(payload)) {
      throw new Error("Response contained sensitive database material");
    }
  }
}

export function redactUnknown(value: unknown): unknown {
  if (typeof value === "string") {
    if (value.startsWith("postgresql://")) {
      return "[redacted-database-url]";
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(redactUnknown);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, redactUnknown(v)])
    );
  }
  return value;
}
