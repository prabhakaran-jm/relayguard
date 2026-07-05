/** Server-side data access — delegates to Python CLI via relayguard-api. */
export {
  listIncidents,
  fetchAuditReport,
  fetchDashboard,
  fetchLatestDashboard,
  toDashboardViewModel,
} from "./relayguard-api";
