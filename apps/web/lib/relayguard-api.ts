import { execFile } from "child_process";
import { accessSync } from "fs";
import path from "path";
import { promisify } from "util";

import type { AuditReport, DashboardViewModel, IncidentSummary } from "./types";
import { assertNoSecrets } from "./redaction";

const execFileAsync = promisify(execFile);

const REPO_ROOT = path.resolve(process.cwd(), "../..");

function pythonCommand(): string {
  const winVenv = path.join(REPO_ROOT, ".venv", "Scripts", "python.exe");
  const unixVenv = path.join(REPO_ROOT, ".venv", "bin", "python");
  try {
    accessSync(winVenv);
    return winVenv;
  } catch {
    try {
      accessSync(unixVenv);
      return unixVenv;
    } catch {
      return process.platform === "win32" ? "python" : "python3";
    }
  }
}

async function runPythonJson<T>(args: string[]): Promise<T> {
  const python = pythonCommand();
  const { stdout } = await execFileAsync(python, args, {
    cwd: REPO_ROOT,
    env: process.env,
    maxBuffer: 10 * 1024 * 1024,
  });
  assertNoSecrets(stdout);
  return JSON.parse(stdout) as T;
}

export async function listIncidents(limit = 20): Promise<IncidentSummary[]> {
  const data = await runPythonJson<{ incidents: IncidentSummary[] }>([
    "-m",
    "apps.cli.list_incidents",
    "--json",
    "--limit",
    String(limit),
  ]);
  return data.incidents;
}

export async function fetchAuditReport(incidentId: string): Promise<AuditReport> {
  return runPythonJson<AuditReport>([
    "-m",
    "apps.cli.audit_incident",
    "--incident-id",
    incidentId,
    "--json",
  ]);
}

export function toDashboardViewModel(report: AuditReport): DashboardViewModel {
  return {
    ...report,
    proof_counts: {
      committed_action_count: report.committed_action_count,
      stale_commit_rejection_count: report.stale_commit_rejection_count,
      retrieved_memory_count: report.retrieved_memory_count,
      blocked_memory_count: report.blocked_memory_count,
      invariant_status: report.invariant_status,
    },
  };
}

export async function fetchLatestDashboard(): Promise<DashboardViewModel | null> {
  const incidents = await listIncidents(1);
  if (!incidents.length) {
    return null;
  }
  const report = await fetchAuditReport(incidents[0].incident_id);
  return toDashboardViewModel(report);
}

export async function fetchDashboard(incidentId: string): Promise<DashboardViewModel> {
  const report = await fetchAuditReport(incidentId);
  return toDashboardViewModel(report);
}
