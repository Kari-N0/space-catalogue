// M0 placeholder entry point. The Babylon engine is NOT loaded here and never
// will be on the landing route — it lazy-loads on first 3D interaction (PLAN.md §3).

const status = document.getElementById("status");
if (status) {
  status.textContent = `build ${import.meta.env.MODE} · ${new Date().getUTCFullYear()}`;
}

export {};
