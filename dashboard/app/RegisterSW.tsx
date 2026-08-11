"use client";

import { useEffect } from "react";

// Registers the service worker AND makes the installed app self-update. The old
// version registered once with no update path, so phones got stuck on a cached
// build. Now we: (1) bypass the HTTP cache when checking sw.js for updates, (2)
// poll for updates on load + when the tab regains focus, and (3) reload exactly
// once when a new worker takes control — so a redeploy reaches mobile without
// the user clearing site data.
export default function RegisterSW() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    // Only reload on an UPDATE (a controller already exists), never on the
    // first-ever install — that would refresh brand-new visitors pointlessly.
    const hadController = !!navigator.serviceWorker.controller;
    let reloaded = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (!hadController || reloaded) return;
      reloaded = true;
      window.location.reload();
    });

    navigator.serviceWorker
      .register("/sw.js", { updateViaCache: "none" })
      .then((reg) => {
        reg.update();
        // A waiting worker means an update is ready — tell it to activate now.
        const promote = () => reg.waiting?.postMessage("SKIP_WAITING");
        if (reg.waiting) promote();
        reg.addEventListener("updatefound", () => {
          const nw = reg.installing;
          if (!nw) return;
          nw.addEventListener("statechange", () => {
            if (nw.state === "installed" && navigator.serviceWorker.controller) {
              promote();
            }
          });
        });

        // Re-check for a new deploy whenever the user returns to the app.
        const recheck = () => {
          if (document.visibilityState === "visible") reg.update().catch(() => {});
        };
        document.addEventListener("visibilitychange", recheck);
      })
      .catch(() => {});
  }, []);

  return null;
}
