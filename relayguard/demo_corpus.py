"""Realistic demo memory corpus for seed_demo_memories.

~55-60 (label, content, memory_kind) tuples spanning SRE runbooks, historical
incidents, deprecated/failed actions, and a majority of off-topic noise. The
first five entries are the original labels referenced by tests/dashboard
scripts (do not rename or remove).

Wording note: only entries genuinely relevant to "API latency spike in
us-east-1" reuse words from embeddings._INCIDENT_TERMS (api, latency, spike,
outage, standby, routing, primary, health, restart, traffic, node, failure,
incident, resolved, similar, east, deprecated, cascading, checks, route,
fail). Everything else stays off that vocabulary so semantic ranking, not
manual curation, keeps the noise out of top-5.
"""

from __future__ import annotations

from relayguard.models import MemoryKind

DEMO_CORPUS: list[tuple[str, str, MemoryKind]] = [
    # --- Original 5 (verbatim, labels are load-bearing) ---
    ("current_runbook", "Route traffic to standby when primary health checks fail.", MemoryKind.CURRENT_RUNBOOK),
    ("expired_runbook", "Restart primary node immediately (deprecated 2024-Q1).", MemoryKind.EXPIRED_RUNBOOK),
    ("failed_restart", "Prior restart attempt caused cascading failure.", MemoryKind.FAILED_RESTART),
    ("historical_incident", "Similar outage in us-east-1 resolved via standby routing.", MemoryKind.HISTORICAL_INCIDENT),
    ("unrelated_finance", "Quarterly billing report template for finance team.", MemoryKind.UNRELATED),

    # --- Runbooks for other systems (current, not related to this incident) ---
    ("runbook_db_failover", "Promote the read replica to primary when the database leader is unreachable for 60 seconds.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_cert_rotation", "Rotate TLS certificates 30 days before expiry using the internal cert-manager job.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_cache_purge", "Purge the CDN edge cache for a stale asset by invalidating its path in the CDN console.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_disk_alert", "Free up disk space on a host by rotating logs and clearing the tmp partition when usage exceeds 90%.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_deploy_rollback", "Roll back a bad deploy by re-pointing the load balancer to the previous stable release tag.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_dns_cutover", "Update the DNS weighted record to shift traffic between regions during a planned cutover.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_queue_backlog", "Scale up consumer workers when the message queue depth exceeds 10k pending jobs.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_pod_eviction", "Cordon and drain a Kubernetes node before decommissioning to avoid pod eviction storms.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_ssl_handshake", "Restart the ingress controller when SSL handshake errors spike after a cert renewal.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_backup_verify", "Verify nightly database backups by restoring the latest snapshot to a scratch instance weekly.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_rate_limit", "Raise the per-tenant rate limit temporarily during a verified traffic surge from a known partner.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_secrets_rotation", "Rotate database credentials quarterly and redeploy dependent services with the new secret.", MemoryKind.CURRENT_RUNBOOK),
    ("runbook_autoscale_tune", "Adjust the autoscaling target CPU threshold when sustained load patterns change.", MemoryKind.CURRENT_RUNBOOK),

    # --- Deprecated / expired runbooks (other systems) ---
    ("expired_runbook_manual_failover", "Manually edit the hosts file to switch the database over (superseded by automated failover 2023).", MemoryKind.EXPIRED_RUNBOOK),
    ("expired_runbook_ftp_cert", "Send fresh credentials via legacy file transfer to the old app host (retired, host shut down).", MemoryKind.EXPIRED_RUNBOOK),
    ("expired_runbook_cron_purge", "Purge cache via nightly cron script on the old monolith (superseded after CDN migration).", MemoryKind.EXPIRED_RUNBOOK),
    ("expired_runbook_manual_scale", "Manually SSH into hosts to add queue workers (superseded by autoscaling group).", MemoryKind.EXPIRED_RUNBOOK),
    ("expired_runbook_legacy_dns", "Edit DNS zone file directly on the legacy nameserver (superseded by managed DNS).", MemoryKind.EXPIRED_RUNBOOK),
    ("expired_runbook_old_rollback", "Restore from a tagged archive on the release machine to unwind a faulty version (superseded by CI workflow).", MemoryKind.EXPIRED_RUNBOOK),

    # --- Failed-action records (other systems) ---
    ("failed_action_cache_purge", "Attempted CDN cache purge during a peak sale event caused a thundering herd on origin servers.", MemoryKind.FAILED_RESTART),
    ("failed_action_db_failover", "Automated database promotion triggered a split-brain when network partition was misdiagnosed.", MemoryKind.FAILED_RESTART),
    ("failed_action_autoscale", "Aggressive autoscaling threshold change caused rapid scale-flapping and a billing surge.", MemoryKind.FAILED_RESTART),
    ("failed_action_dns_cutover", "DNS weighted cutover was rolled out too fast and dropped requests during propagation delay.", MemoryKind.FAILED_RESTART),
    ("failed_action_secrets_rotation", "Rotating database credentials without redeploying dependents locked out three services.", MemoryKind.FAILED_RESTART),
    ("failed_action_pod_drain", "Draining a Kubernetes worker without cordoning first caused a brief service disruption.", MemoryKind.FAILED_RESTART),
    ("failed_action_similar_restart", "A prior try to restart the same node during a similar spike caused a related failure.", MemoryKind.FAILED_RESTART),

    # --- Historical incidents (other services, unrelated to this incident) ---
    ("historical_incident_db_outage", "Database disruption last spring was fixed by promoting the read replica after leader election stalled.", MemoryKind.HISTORICAL_INCIDENT),
    ("historical_incident_cert_expiry", "Certificate expiry problem in checkout was fixed by emergency manual renewal and redeploy.", MemoryKind.HISTORICAL_INCIDENT),
    ("historical_incident_queue_backlog", "Message queue pileup was fixed by temporarily doubling consumer worker count.", MemoryKind.HISTORICAL_INCIDENT),
    ("historical_incident_disk_full", "Disk-full problem on the logging cluster was fixed by expanding volumes and rotating old logs.", MemoryKind.HISTORICAL_INCIDENT),
    ("historical_incident_bad_deploy", "Bad release in the billing service was fixed by reverting to the prior release tag.", MemoryKind.HISTORICAL_INCIDENT),
    ("historical_incident_rate_limit", "Partner integration problem was fixed by granting a temporary rate limit exception.", MemoryKind.HISTORICAL_INCIDENT),

    # --- Off-topic noise: HR, meeting notes, marketing, misc finance ---
    ("noise_hr_pto_policy", "Updated PTO accrual policy takes effect at the start of the next fiscal year for all full-time staff.", MemoryKind.UNRELATED),
    ("noise_hr_onboarding", "New hire onboarding checklist includes laptop provisioning, badge access, and benefits enrollment.", MemoryKind.UNRELATED),
    ("noise_hr_review_cycle", "Performance review cycle self-assessments are due by the end of the month for all employees.", MemoryKind.UNRELATED),
    ("noise_meeting_standup_notes", "Weekly product standup notes: roadmap review pushed to Thursday, design mockups pending approval.", MemoryKind.UNRELATED),
    ("noise_meeting_offsite", "Team offsite agenda includes a retrospective session and a catered lunch on day two.", MemoryKind.UNRELATED),
    ("noise_meeting_1on1_template", "Manager 1:1 template covers career growth goals, current blockers, and recognition shoutouts.", MemoryKind.UNRELATED),
    ("noise_marketing_launch_copy", "New landing page copy emphasizes the product's ease of use and free trial signup flow.", MemoryKind.UNRELATED),
    ("noise_marketing_newsletter", "Monthly newsletter draft highlights customer testimonials and an upcoming webinar.", MemoryKind.UNRELATED),
    ("noise_marketing_brand_guide", "Brand style guide specifies the approved logo colors and typography for social media assets.", MemoryKind.UNRELATED),
    ("noise_finance_expense_policy", "Updated travel expense policy caps per-diem meal reimbursement at fifty dollars.", MemoryKind.UNRELATED),
    ("noise_finance_vendor_invoice", "Vendor invoice reconciliation for office supplies is due before month-end close.", MemoryKind.UNRELATED),
    ("noise_finance_budget_review", "Annual budget review meeting will cover department spending variances from projections.", MemoryKind.UNRELATED),
    ("noise_legal_nda_template", "The default two-way confidentiality agreement now includes a revised data storage section.", MemoryKind.UNRELATED),
    ("noise_office_facilities", "Office facilities team scheduled HVAC maintenance for the third floor over the weekend.", MemoryKind.UNRELATED),
    ("noise_office_snacks", "Kitchen snack restocking is now handled by a rotating vendor contract on Mondays.", MemoryKind.UNRELATED),
    ("noise_recruiting_pipeline", "Recruiting pipeline dashboard shows candidate counts by stage for the open engineering roles.", MemoryKind.UNRELATED),
    ("noise_support_macro", "Customer support macro for password reset requests links to the self-service portal.", MemoryKind.UNRELATED),
    ("noise_sales_deck", "Sales enablement deck was refreshed with the latest competitive comparison slide.", MemoryKind.UNRELATED),
    ("noise_events_conference", "Booth setup for the industry conference ships next week along with the banner stand.", MemoryKind.UNRELATED),
    ("noise_design_style_tokens", "Design style variables were reworked to align with new accessibility guidelines.", MemoryKind.UNRELATED),
    ("noise_procurement_laptop", "Procurement approved a bulk laptop refresh order for the design and engineering teams.", MemoryKind.UNRELATED),
    ("noise_compliance_training", "Annual compliance training modules on data privacy are due for all staff by year-end.", MemoryKind.UNRELATED),
    ("noise_facilities_badge", "Employee keycard requests now go through the updated office request tool.", MemoryKind.UNRELATED),
    ("noise_marketing_survey", "Customer satisfaction survey results will be shared in the next all-hands meeting.", MemoryKind.UNRELATED),
    ("noise_hr_holiday_calendar", "Company holiday calendar for next year was published on the internal wiki.", MemoryKind.UNRELATED),
    ("noise_finance_payroll_cutoff", "Payroll processing cutoff for time-off requests is the 25th of each month.", MemoryKind.UNRELATED),
]
