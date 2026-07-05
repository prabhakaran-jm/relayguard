# RelayGuard Dashboard — UI UX Pro Design Plan

Design intelligence for a judge-facing incident command center (hackathon demo, 3-minute screen recording).

## Design system

| Token | Value | Usage |
|-------|-------|--------|
| Background | `#0b1220` | Page base |
| Surface | `#111b2e` | Cards, panels |
| Border | `#1e3a5f` | Subtle separation |
| Text primary | `#e8f4ff` | Headlines, values |
| Text muted | `#8ba3c7` | Labels, captions |
| Accent cyan | `#22d3ee` | PASS, selected action, links |
| Accent teal | `#2dd4bf` | USE verdicts, positive metrics |
| Warning orange | `#fb923c` | INSPECT verdicts |
| Danger red | `#f87171` | FAIL, AVOID, rejected commits |

**Typography:** System UI stack, large metric numbers (2xl–4xl), semibold section titles, monospace for IDs and event types.

**Layout rhythm:** 24px outer padding, 16px card gap, no dense paragraphs.

## Screen 1 — Landing / latest incident dashboard

**Hero (full width)**
- Title: **RelayGuard**
- Subtitle: *Crash-safe memory for incident agents*

**Primary proof row (4 equal cards)**
1. Selected action — `ROUTE_TO_STANDBY` in cyan
2. Committed actions — `1` large number
3. Stale rejected — `1` in orange
4. Invariants — `PASS` badge (cyan glow) or `FAIL` (red)

**Two-column middle**
- **Left:** MemoryGate verdicts table (label, score, verdict pill, reason)
- **Right:** Execution timeline (event, worker, epoch, summary, time)

**Bottom**
- Action ledger table
- Audit proof strip: retrieved count, blocked count, committed, stale rejections
- One-line explainer: *Similarity retrieves candidates. MemoryGate decides which memories are safe. CockroachDB stores execution state, fencing epoch, action ledger, and audit trail.*

## Screen 2 — Incident detail

Same layout with incident selector dropdown in header. Deep-link `/incident/[id]`.

## Component states

| Verdict | Pill color |
|---------|------------|
| USE | Teal |
| INSPECT | Orange |
| AVOID | Red |

| Event | Timeline accent |
|-------|-----------------|
| `action.committed` | Cyan left border |
| `action.commit_rejected` | Red left border |
| Default | Blue border |

## UX principles (UI UX Pro)

1. **Result first** — PASS + action visible without scrolling on 1080p
2. **Evidence-focused** — tables over charts
3. **No clutter** — no nav sidebar, no settings, no auth
4. **Demo-safe** — high contrast for projectors and recordings
5. **Read-only** — no edit buttons, no write affordances

## Implementation notes

- shadcn-style card primitives via Tailwind only
- lucide-react: Shield, CheckCircle, XCircle, Activity, Database
- Subtle hover on table rows only
- No animations beyond optional 150ms opacity on load
