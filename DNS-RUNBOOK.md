# DNS-RUNBOOK — farsidelab.com go-live (Phase 1 prep)

Written 2026-08-04. **GATE: Kari executes every click in this file; Claude only
runs the read-only verification checks in §6 after propagation.** Nothing in
the repo flips until §5 is explicitly triggered.

**Decisions approved by Kari 2026-08-04:** (1) apex `farsidelab.com` primary,
www redirects to it; (2) DNS-only first, orange cloud only after Enforce HTTPS
is live; (3) CSP ships Report-Only, enforced only after a clean verification
window.

Current verified state (2026-08-04, see §5 for what changes):

| Thing | State today |
|---|---|
| Live site | https://kari-n0.github.io/space-catalogue/ (GitHub Pages, Actions deploy) |
| Build base path | CI env `BASE_PATH: /space-catalogue/` (ci.yml line 14); vite `base` and the budget checker both read it |
| Custom-domain artifacts | none — no `CNAME` file, no `robots.txt`, no `sitemap.xml`, no 404 page |
| Canonical tags | none on either page |
| Indexing | `concept/index.html` carries `<meta name="robots" content="noindex">` (deliberate — dev URL stays out of search) |
| Absolute self-URLs | exactly one: `og:image` in `concept/index.html` → `https://kari-n0.github.io/space-catalogue/assets/figures/fig02-shadow-clock-poster.webp` (+ one doc mention in `content/concepts/README.md`) |
| Email service | none yet (Brevo recommended; account creation still gated on your go) |

---

## 1. Cloudflare zone + nameserver switch

1. Cloudflare dashboard → **Add a domain** → `farsidelab.com` → **Free** plan.
2. Let it import existing DNS records; delete anything it imports that you
   don't recognize (a parked domain usually has registrar-parking A records —
   remove them).
3. Cloudflare shows **two assigned nameservers** (e.g. `xxx.ns.cloudflare.com`
   / `yyy.ns.cloudflare.com`). Copy them.
4. At your **registrar**: domain management → Nameservers → replace the
   registrar's nameservers with the two Cloudflare ones. (Registrar DNSSEC:
   if it was ON at the registrar, turn it OFF before the switch; re-enable
   later from Cloudflare → DNS → Settings → DNSSEC with the DS record they
   give you.)
5. Wait for Cloudflare's "site is active" email (minutes to hours; up to 24 h).

## 2. DNS records (Cloudflare → DNS → Records)

Create these — **all with the cloud toggled GREY (DNS only) for now**. Orange
comes later in §4; GitHub cannot issue the HTTPS certificate while Cloudflare
is proxying.

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `@` | `185.199.108.153` | DNS only |
| A | `@` | `185.199.109.153` | DNS only |
| A | `@` | `185.199.110.153` | DNS only |
| A | `@` | `185.199.111.153` | DNS only |
| AAAA | `@` | `2606:50c0:8000::153` | DNS only |
| AAAA | `@` | `2606:50c0:8001::153` | DNS only |
| AAAA | `@` | `2606:50c0:8002::153` | DNS only |
| AAAA | `@` | `2606:50c0:8003::153` | DNS only |
| CNAME | `www` | `kari-n0.github.io` | DNS only |
| TXT | `_github-pages-challenge-kari-n0` | *(value from step 3.1)* | DNS only |

(The four A/AAAA addresses are GitHub Pages' anycast set — current per GitHub
docs; the verification step in §6 re-checks them against the live docs.)

## 3. GitHub side

### 3.1 Verify the domain on your account (do this FIRST — takeover protection)
1. github.com → avatar → **Settings → Pages** (user-level, not the repo) →
   **Add a domain** → `farsidelab.com`.
2. GitHub shows a TXT record name + value
   (`_github-pages-challenge-kari-n0.farsidelab.com` → `<code>`). Add it in
   Cloudflare (last row of the §2 table), wait a few minutes, click **Verify**.

### 3.2 Attach the domain to the repo
1. Repo **Kari-N0/space-catalogue → Settings → Pages → Custom domain** →
   enter `farsidelab.com` → **Save**. (Actions-based deploys keep this setting
   across deploys; no CNAME file needed in the artifact.)
2. Wait for the DNS check to go green, then for the certificate
   (Let's Encrypt, usually < 1 h). When the **Enforce HTTPS** checkbox becomes
   available, **tick it**.
3. `www.farsidelab.com` needs no separate setting — with the CNAME in place,
   GitHub 301-redirects www → apex automatically. The old
   `kari-n0.github.io/space-catalogue/*` URLs also start 301-redirecting to
   `farsidelab.com/*` (that's the "canonical twin" handled at the HTTP level;
   the in-page canonical/meta updates are §5).

**Tell Claude when 3.2 is done** → verification pass A (§6) before going on.

## 4. Turn Cloudflare on (after the cert exists)

### 4.1 Proxy + TLS
1. DNS → Records: flip the four A, four AAAA and the `www` CNAME to
   **Proxied (orange)**. Leave every TXT (and any future MX/DKIM) grey.
2. **SSL/TLS → Overview** → mode **Full (strict)** — never "Flexible".
3. **SSL/TLS → Edge Certificates**:
   - **Always Use HTTPS: ON**
   - **HSTS: leave OFF for now** (enable after a clean week; start
     `max-age=86400`, no preload, includeSubdomains off)
   - Minimum TLS 1.2.
4. **The ACME gotcha (required):** GitHub renews its certificate every ~90
   days over plain-HTTP ACME. "Always Use HTTPS" would break that renewal.
   Rules → **Configuration Rules → Create**:
   - Name: `acme-passthrough`
   - When: URI Path **starts with** `/.well-known/acme-challenge/`
   - Then: **Automatic HTTPS Rewrites: OFF** and **"Always Use HTTPS": OFF**
     (the setting toggle inside the rule)
   - Deploy. (If Configuration Rules doesn't expose the toggle on the plan,
     the equivalent legacy Page Rule is: URL
     `farsidelab.com/.well-known/acme-challenge/*` → SSL: Off, Always Use
     HTTPS: Off.)

### 4.2 Speed
- **Speed → Optimization**: Brotli **ON** (usually default), **HTTP/3: ON**,
  **Early Hints: ON**, 0-RTT ON.
- Auto Minify: **all OFF** (Vite already minifies; double-minify risks maps).
- Rocket Loader: **OFF** (module scripts + engine lazy-boundary — do not let
  Cloudflare rewrite script loading).

### 4.3 Cache rules (Caching → Cache Rules)
GitHub Pages sends `Cache-Control: max-age=600` on everything. Our splats and
videos are large but REPLACED IN PLACE under stable names (`splat_hero_d.sog`),
so browsers must keep revalidating (respect origin) while Cloudflare's edge can
hold them longer — with a purge after any deploy that swaps assets.

Rule 1 — `splats-and-video` (create first, order matters):
- When: Hostname eq `farsidelab.com` AND URI Path matches regex
  `\.(sog|mp4|webm)$`  *(if regex isn't available on Free: two rules with
  "URI Path ends with" `.sog` / `.mp4` / `.webm`)*
- Then: **Eligible for cache**; Edge TTL: **Override → 1 day**;
  Browser TTL: **Respect origin**.

Rule 2 — `hashed-bundles`:
- When: Hostname eq `farsidelab.com` AND URI Path starts with `/assets/` AND
  URI Path matches `\.(js|css|woff2)$`
- Then: Eligible for cache; Edge TTL **Override → 30 days**; Browser TTL
  **Override → 7 days**. (Safe: Vite content-hashes every js/css filename;
  fonts are immutable files.)

Leave everything else (HTML, `content/concepts/*.json`) on default — those are
edited in place and must stay on the origin's 600 s.

**Operational rule from now on:** after any push that replaces a `.sog`/video
under the same filename, Caching → **Purge Cache → Custom purge** with the
file's URL (or "Purge everything" — the site is small).

### 4.4 Security headers (Rules → Transform Rules → Modify Response Header)
Pages alone can't set these; Cloudflare can. One rule, `security-headers`,
When: Hostname eq `farsidelab.com`. Set static headers:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |
| `X-Frame-Options` | `DENY` |
| `Content-Security-Policy-Report-Only` | `default-src 'self'; script-src 'self' 'wasm-unsafe-eval' https://plausible.io 'sha256-NGZKiTSkpb8HhMF5Pus6Xp2oskibeW4015D/xeWIs2g=' 'sha256-AW3rhsROpK5GJqo/gqlL9tJtqMDO3J6Lu8zkg/f8hiI='; worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'; connect-src 'self' https://plausible.io https://buttondown.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://buttondown.com` |

CSP ships **Report-Only on purpose**: Babylon needs wasm + blob workers and
injects style tags; the policy above is written for that, but we verify the
console stays clean on the live domain for a few days (Claude checks in §6),
THEN flip the header name to `Content-Security-Policy`. Amended 2026-08-04
for the services that went live: `https://plausible.io` in script-src +
connect-src and the two `sha256-…` entries for the inline Plausible init
snippets (index.html / concept/index.html — recompute if those snippets
change byte-for-byte), `https://buttondown.com` in connect-src (signup
fetch) and form-action (no-JS form fallback). Any future service grows
`script-src`/`connect-src` by exactly its origin — amend the rule the same
day the service goes live.

## 5. What flips in the repo when the domain is live

Claude prepares all of these as one commit **on your word** (after §6 pass B):

1. `.github/workflows/ci.yml`: `BASE_PATH: /` (one line — build + budget
   checker share it; local builds already default to `/`).
2. `apps/web/concept/index.html`: `og:image` →
   `https://farsidelab.com/assets/figures/fig02-shadow-clock-poster.webp`.
3. Add to `concept/index.html` head (and the landing page):
   `<link rel="canonical" href="https://farsidelab.com/…">` + `og:url` —
   exact URLs proposed for your approval at flip time (concept pages are
   query-string routes; canonical should be `?id=lunar-base` explicitly).
4. `content/concepts/README.md`: view-URL doc line.
5. **NOT automatic — your separate launch call:** removing
   `<meta name="robots" content="noindex">`. That single line is what keeps
   the site out of search engines. It can flip with the domain or later with
   the launch content — say which.
6. Optional post-launch niceties (separate, low priority): `robots.txt` +
   `sitemap.xml`, a styled `404.html` (Pages serves its default otherwise —
   relevant once real URLs circulate).

Note on timing: until item 1 lands, the site at `farsidelab.com` would serve
a build whose internal URLs still say `/space-catalogue/` — **so §3.2 and the
item-1 commit should happen in the same sitting.** Sequence: you finish §3.2
→ ping Claude → verification pass A → Claude pushes the flip commit (item 1,
2, 4 + approved 3) → CI deploys → verification pass B → then §4.

## 6. Verification (Claude, read-only, after your pings)

Pass A (after §3.2): `dig NS farsidelab.com` shows the two Cloudflare NS;
`dig A/AAAA farsidelab.com @1.1.1.1` and `@8.8.8.8` return exactly the four
+four GitHub addresses; TXT challenge resolves; GitHub Pages check green;
`curl -I https://farsidelab.com` returns the site with a Let's Encrypt cert
(issuer check), `http://` 301s to `https://`, `www.` 301s to apex,
`kari-n0.github.io/space-catalogue/` 301s to the domain.

Pass B (after the §5 flip deploys): built HTML references `/assets/…` not
`/space-catalogue/assets/…`; budgets green in CI; og:image/canonical point at
farsidelab.com; splats and viewer load on the live domain (headless browser
run against https://farsidelab.com/concept/?id=lunar-base).

Pass C (after §4): `cf-ray` + `content-encoding: br` present;
`cf-cache-status: HIT` on a second `.sog` fetch; security headers present;
CSP-Report-Only produces zero console violations across landing + concept +
3D interaction; cert renewal path — `curl -sI
http://farsidelab.com/.well-known/acme-challenge/test` is NOT redirected to
https (the §4.1.4 rule works).

## 7. Email service records — PLACEHOLDERS (account creation still gated)

All TXT/MX records: **DNS only (grey)**, never proxied. When the provider
account exists (Brevo recommended, 2026-07-12), paste their exact values into
the slots — hosts/names sometimes differ per account, the provider dashboard
wins over this table.

| Purpose | Type | Name | Value | Notes |
|---|---|---|---|---|
| Provider domain verification | TXT | `@` *(or provider-given host)* | `[PASTE: e.g. brevo-code:xxxxxxxx]` | one-time proof |
| SPF | TXT | `@` | `[PASTE — Brevo's is currently shaped like: v=spf1 include:spf.brevo.com ~all]` | **max ONE SPF record per domain** — if a TXT starting `v=spf1` already exists, merge the `include:` into it instead of adding a second |
| DKIM | TXT *(some providers: CNAME)* | `[PASTE host, e.g. mail._domainkey]` | `[PASTE key, k=rsa; p=…]` | copy exactly; long values are fine in Cloudflare |
| DMARC | TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:[PASTE reporting address]; fo=1` | start at `p=none` (monitor only); tighten to `quarantine` after 2–4 clean weeks of reports |

Not included on purpose: **MX records** — Brevo is for *sending* (signup
confirmations). Receiving mail at `@farsidelab.com` (e.g. the DMARC `rua`
mailbox or `kari@farsidelab.com`) needs a mailbox/forwarding provider — a
separate decision; until then point `rua` at an existing mailbox you own.

---

*Sequence summary: §1 → §2 → §3 (ping: pass A) → §5 items 1–4 same sitting
(pass B) → §4 (pass C) → §7 whenever the email account gets its go. The
`noindex` removal (§5.5) is its own switch, on your word only.*
