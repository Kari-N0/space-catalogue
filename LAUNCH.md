# LAUNCH.md — go-live tracker

Created 2026-08-04 (no earlier LAUNCH.md existed in the repo — this file was
seeded from DNS-RUNBOOK.md when Phase 1 completed; if a private draft exists
elsewhere, merge it in). Detailed procedures live in **DNS-RUNBOOK.md**;
this file only tracks status.

## Phase 1 — domain (farsidelab.com) — ✅ COMPLETE 2026-08-04

- [x] Cloudflare zone active, nameservers switched (neil/penny.ns.cloudflare.com) — Kari, 2026-08-04
- [x] DNS records for GitHub Pages created (runbook §2) — Kari, 2026-08-04
- [x] Domain verified on GitHub account (TXT challenge) — Kari, 2026-08-04
- [x] Custom domain `farsidelab.com` attached to repo, DNS check green — Kari, 2026-08-04
- [x] **Enforce HTTPS ticked** (GitHub/Let's Encrypt cert issued) — Kari, 2026-08-04
- [x] **⚠ proxy re-enable order respected**: Cloudflare proxy (orange) turned ON only AFTER the GitHub cert existed — the runbook warning that proxying too early blocks cert issuance. Proxy live on the Pages records — Kari, 2026-08-04
- [x] Redirects verified: http→https, www→apex, github.io twin→domain (all 301) — Claude, 2026-08-04
- [x] BASE_PATH flipped to `/` + canonicals/og:url/og:image → farsidelab.com — Claude, 2026-08-04 (this commit)
- [x] Email service: **Buttondown** (buttondown.com/FarsideLab), sending domain `mail.farsidelab.com` — Kari set up account/domain/double-opt-in (tracking pixels off, UTM on); DMARC + return-path CNAME verified externally, DKIM shows Present in dashboard (selector not externally known, so no independent dig) — Kari + Claude, 2026-08-04
- [x] Signup form wired to the Buttondown embed endpoint (client fetch + no-JS form fallback) and **response kept deliberately generic** for every server outcome (enumeration protection — see CLAUDE.md web rules); all four UI states verified against the endpoint's real response shapes, deployed — Claude, 2026-08-04
  - Footnote (by design, no action): **resubscribe after unsubscribe is suppressed** by Buttondown's suppression list — the form can't re-add a previously-unsubscribed address. Returning subscribers use the hosted page (buttondown.com/FarsideLab) or email us. Post-launch footnote only.
- [x] Analytics: **Plausible** wired site-wide (landing + concept routes), cookieless default config; goals: `Signup Completed` (form success state), `Enter 3D` (first 3D-canvas interaction), pageview goal on `/concept/` (Kari adds the three goals in the dashboard); self-exclusion via `#analytics-off` URL toggle; CSP draft in runbook §4.4 amended same day (plausible.io + inline-snippet hashes + buttondown.com) — Claude, 2026-08-04
- [x] **Privacy page** — `/privacy/` live in site chrome, documents Buttondown (double opt-in, no pixels, enumeration-protected form, US processor under SCC-based DPA) + Plausible (EU-hosted, cookieless, aggregate) + hosting logs + GDPR rights (Finnish DPA); footer PRIVACY link wired; Kari reviewed and signed off pre-commit — 2026-08-04. Note: Cloudflare Email Address Obfuscation rewrites the page's static mailto links (decodes in-browser; verified live).

## Phase 1.5 — hardening (deferred, own clocks — not launch-blocking)

- [ ] ACME passthrough rule (`/.well-known/acme-challenge/*` exempt from Always-Use-HTTPS) — runbook §4.1.4; **needed before GitHub's first cert renewal (~90 days, early November 2026)**
- [x] Cloudflare cache rules for .sog/video (runbook §4.3 Rule 1) — done + verified 2026-08-05 (Phase 2 audit); Rule 2 (hashed-bundles 30-day edge TTL) still optional
- [x] Security headers transform rule, CSP in Report-Only (runbook §4.4) — done + verified 2026-08-05 (Phase 2 audit)
- [ ] CSP enforced after a clean Report-Only window (Claude verifies console)
- [ ] HSTS (only after a clean week; start max-age=86400)

## Phase 2 — content & services — ✅ COMPLETE 2026-08-05
(the two launch-day switches below stay open by design until launch day)

- [ ] **Launch-day switch: NAS sync fresh within 24 h** — check `~/.local/state/sync-nas/last.log` (written by `scripts/sync-nas.sh`; also runs via SessionEnd hook + weekly systemd user timer)
- [ ] **Launch-day switch: `noindex` removal** — Kari's explicit launch call (concept/index.html)
- [x] robots.txt + sitemap.xml + styled 404 — live and verified 2026-08-05 (sitemap lists /concept/ while noindex holds; meta governs until the flip)

### Phase 2 audit — security & quality (Claude, 2026-08-05)

- [x] **A1 secret scan**: gitleaks 8.30.1 + trufflehog 3.96.0 over full history, all branches — **zero findings**
- [x] **A2 dependencies & repo settings**: `npm audit` clean after fix (2 high dev-time advisories, lockfile-only); Dependabot alerts + automated security fixes enabled + `dependabot.yml` (weekly, babylon grouped); branch protection on main (force-push/deletion blocked — direct pushes still allowed, push-to-deploy flow intact; requiring PRs+checks would break it → Kari's call if ever wanted); Actions default perms read-only + explicit `contents: read` in ci.yml; no secrets in workflows (deploy uses OIDC)
- [x] **B5–B7 mobile tiers**: five `_m` splats (`-H 0` from current `_d` sources) + 720p hero video (`hero_v001_m.mp4`, 3.0 MB) wired via `scene_file_mobile`/`video_mobile`; stale July mobile hero deleted; budget checker tier regex accepts `_d`/`_m`
- [x] **C9 accessibility**: reduced-motion → posters (hero + FIG_02), canvases tabbable (arrows orbit, +/- zoom, envelope-clamped), pins already buttons, focus rings, alt sweep clean — Lighthouse a11y 100
- [x] **C10 landing**: CTA pill → /concept/?id=moon-base (M3.5 blocker closed); M0 debug footer line removed; email slot not specified in M3.5 (signup lives on the concept page)
- [x] **C11 Lighthouse (live)**: landing 99/100/100/100; concept a11y 100 · best-practices 100 · SEO 69 (noindex by design) · perf not measurable headless (software GL) → real-device numbers are Phase 3
- [x] **Cache rule live** (Kari created runbook §4.3 Rule 1, 2026-08-05) — verified: all ten splats + both hero videos `cf-cache-status: HIT` at the edge, browser TTL respects origin (600 s) so in-place asset swaps stay safe. **Reminder: purge cache after any deploy that swaps a .sog/video in place** (runbook §4.3 note).
- [x] **Security headers live** (Kari created the runbook §4.4 Transform Rule 2026-08-05; first paste dropped 3 chars mid-CSP — `default-src 'selfscript-src` — caught in verification, re-pasted, now **byte-identical to the runbook**). Verified live on all routes; full E2E under Report-Only (viewer + splats, pins, FIG videos, signup fetch to Buttondown, 4 Plausible beacons) = **zero violation reports, clean console**. Next clocks (Phase 1.5): RO→enforce after a clean Report-Only window; HSTS after a clean week.

## Phase 3 — device testing (Kari on hardware, Claude analyzes results)

The full step-by-step script was printed in the 2026-08-05 session; condensed
tracker (order matters — goals test BEFORE self-exclusion):

- [ ] Plausible goals fire from a real phone (pageview `/concept/`, `Enter 3D`, `Signup Completed` via a `+alias` test address; delete the pending subscriber in Buttondown afterward). Requires the three goals added in the Plausible dashboard first (pending since Phase 1).
- [ ] Then self-exclude every test browser: visit `https://farsidelab.com/#analytics-off` once per browser.
- [ ] Performance per device (phone + laptop, cellular AND Wi-Fi): cold-load time to hero video / to 3D splat; `?hud=1` → fps, tier, engine. Expect tier=mobile + steady ≥30 fps on the phone.
- [ ] Mobile splat quality verdicts (Kari's call, per card): `?tier=mobile` vs `?tier=desktop` A/B on the same device — hero, de_gerlache (6.5 MB), spacex (7.0 MB), mk2, base → ship / poster-only / decimate per card.
- [ ] 720p hero video on the phone panel (banding in sky, blocking in terrain pan) vs 1080p via `?tier=desktop`.
- [ ] Touch controls in EVERY 3D window: one-finger orbit, pinch zoom, two-finger/right pan, glide feel, envelope limits hold. **Known risk: pinch-zoom in the four feature windows (custom pointer controls) — hero uses Babylon stock pinch, feature windows may not pinch; report.**
- [ ] iOS Safari (if available): inline autoplay, 3D loads, fullscreen chip auto-hidden on iPhone (guard, not bug), Add-to-Home-Screen icon, Reduce Motion → posters.
- [ ] Android: Remove-animations → posters; Add-to-Home-Screen icon.
- [ ] Keyboard on laptop: Tab → pins (Enter opens, Esc closes, focus returns), canvas ring + arrows/+/-, signup form.
- [ ] Social preview: paste the concept URL in a chat draft → FIG_02 poster + title render.
- [ ] Optional: laptop on phone hotspot → `cf-cache-status: HIT` from a second network.
