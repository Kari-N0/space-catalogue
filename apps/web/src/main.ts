// Landing route. Engine-free by contract: nothing under src/viewer/ or
// @babylonjs/* may be imported here (see CLAUDE.md viewer lazy boundary) —
// which is also why the video tier pick below is a plain media query
// instead of the viewer's tiering module.

const BUTTONDOWN_SUBSCRIBE_URL = "https://buttondown.com/api/emails/embed-subscribe/FarsideLab";

function trackEvent(name: string): void {
  (window as { plausible?: (event: string) => void }).plausible?.(name);
}

/* -- hero video: tier pick + autoplay fallback (same rules as concept) ---- */

function startHeroVideo(): void {
  const hero = document.querySelector<HTMLElement>(".hero");
  const video = document.querySelector<HTMLVideoElement>(".hero-media");
  if (!hero || !video) return;

  const posterFallback = (): void => {
    video.remove();
    hero.classList.add("no-video");
  };

  // reduced motion: the poster stands in (CSS already hides the video;
  // removing it also stops the fetch)
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    posterFallback();
    return;
  }

  // phone-size viewports get the 720p encode
  const mobile = matchMedia("(max-width: 820px)").matches;
  video.src = mobile ? "/assets/video/hero_v001_m.mp4" : "/assets/video/hero_v001.mp4";
  video.addEventListener("error", posterFallback);
  // autoplay can be denied (iOS Low Power Mode, data saver) — a paused
  // video would sit as a dead play glyph under the hero text, so fall
  // back to the poster, same as the concept hero.
  void video.play().catch(posterFallback);
}

/* -- email capture: identical behavior to the concept-page form ----------- */

function wireSignup(): void {
  const form = document.querySelector<HTMLFormElement>(".notify-form");
  const fieldset = form?.querySelector("fieldset") ?? null;
  const input = document.querySelector<HTMLInputElement>("#notify-email");
  const status = document.querySelector<HTMLElement>(".notify-status");
  if (!form || !fieldset || !input || !status) return;

  const say = (msg: string): void => {
    status.textContent = msg;
    status.hidden = msg === "";
  };

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const email = input.value.trim();
    // input[type=email] validity + a basic shape check; server re-validates
    if (email === "" || !input.checkValidity() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      say("That doesn't look like a valid email address — please check it.");
      return;
    }
    fieldset.disabled = true;
    say("Sending…");
    void fetch(BUTTONDOWN_SUBSCRIBE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ email }),
    })
      .then(() => {
        trackEvent("Signup Completed");
        // Deliberately no res.ok branch (enumeration protection, CLAUDE.md):
        // membership is never echoed back, and Buttondown's embed endpoint
        // can't distinguish it anyway — duplicates and flagged addresses both
        // return the same 400 + CAPTCHA page (verified 2026-08-04). Fieldset
        // stays disabled so the terminal state is identical for every outcome.
        say(
          "Thanks — if this address isn't already on the list, a confirmation email is on its way. One click and you're in.",
        );
      })
      .catch(() => {
        say("Network error — nothing was sent. Please try again.");
        fieldset.disabled = false;
      });
  });
}

startHeroVideo();
wireSignup();
