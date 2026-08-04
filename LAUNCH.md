# LAUNCH.md — go-live tracker

Created 2026-08-04 (no earlier LAUNCH.md existed in the repo — this file was
seeded from DNS-RUNBOOK.md when Phase 1 completed; if a private draft exists
elsewhere, merge it in). Detailed procedures live in **DNS-RUNBOOK.md**;
this file only tracks status.

## Phase 1 — domain (farsidelab.com)

- [x] Cloudflare zone active, nameservers switched (neil/penny.ns.cloudflare.com) — Kari, 2026-08-04
- [x] DNS records for GitHub Pages created (runbook §2) — Kari, 2026-08-04
- [x] Domain verified on GitHub account (TXT challenge) — Kari, 2026-08-04
- [x] Custom domain `farsidelab.com` attached to repo, DNS check green — Kari, 2026-08-04
- [x] **Enforce HTTPS ticked** (GitHub/Let's Encrypt cert issued) — Kari, 2026-08-04
- [x] **⚠ proxy re-enable order respected**: Cloudflare proxy (orange) turned ON only AFTER the GitHub cert existed — the runbook warning that proxying too early blocks cert issuance. Proxy live on the Pages records — Kari, 2026-08-04
- [x] Redirects verified: http→https, www→apex, github.io twin→domain (all 301) — Claude, 2026-08-04
- [x] BASE_PATH flipped to `/` + canonicals/og:url/og:image → farsidelab.com — Claude, 2026-08-04 (this commit)
- [ ] ACME passthrough rule (`/.well-known/acme-challenge/*` exempt from Always-Use-HTTPS) — runbook §4.1.4; **needed before GitHub's first cert renewal (~90 days, early November 2026)**
- [ ] Cloudflare cache rules for .sog/video + hashed bundles (runbook §4.3)
- [ ] Security headers transform rule, CSP in Report-Only (runbook §4.4)
- [ ] CSP enforced after a clean Report-Only window (Claude verifies console)
- [ ] HSTS (only after a clean week; start max-age=86400)

## Phase 2 — content & services (separate gates)

- [ ] `noindex` removal — **Kari's explicit launch call, its own switch** (concept/index.html)
- [ ] Email service account (Brevo recommended) — gated on Kari's go; then SPF/DKIM/DMARC per runbook §7
- [ ] Analytics (Plausible or Simple Analytics) — gated on Kari's go; CSP rule amended same day
- [ ] robots.txt + sitemap.xml + styled 404 (optional, post-launch)
