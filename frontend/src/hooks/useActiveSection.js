// src/hooks/useActiveSection.js
// Tracks which section is currently visible as the user scrolls .app-main.
//
// Implementation: scroll event + getBoundingClientRect
//   The IntersectionObserver + non-viewport root approach has several edge
//   cases (rootMargin % calculation, threshold with tall sections, browser
//   inconsistencies). A scroll listener is simpler and fully reliable here.
//
// Algorithm:
//   On every scroll event, iterate sectionIds in order.
//   The LAST section whose top has passed the ACTIVATE_AT threshold is active.
//   "Passed the threshold" = its top is ≤ ACTIVATE_AT px from the top of .app-main.
//
//   Example (ACTIVATE_AT = 120px):
//     overview  top = -300px → ≤ 120 → qualifies → active = 'overview'
//     valuation top =  -80px → ≤ 120 → qualifies → active = 'valuation'  ← wins
//     financials top = +400px → > 120 → doesn't qualify
//     ... active = 'valuation'
//
// Retry logic:
//   On route change, sections may not be in DOM yet (data still loading).
//   We retry every RETRY_MS up to MAX_RETRIES times before giving up.

import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";

// Section is considered "entered" once its top is this many px above .app-main's top
const ACTIVATE_AT = 120;
// Retry interval when sections not yet in DOM (ms)
const RETRY_MS = 150;
// Max retries: 40 × 150ms = 6 seconds
const MAX_RETRIES = 40;

function computeActive(root, sectionIds) {
    // When scrolled to the bottom, the last section can't scroll far enough to
    // pass ACTIVATE_AT — so force-activate the last visible section instead.
    const atBottom = root.scrollTop + root.clientHeight >= root.scrollHeight - 4;
    if (atBottom) {
        for (let i = sectionIds.length - 1; i >= 0; i--) {
            if (document.getElementById(sectionIds[i])) return sectionIds[i];
        }
    }

    const rootTop = root.getBoundingClientRect().top;
    let active = null;

    for (const id of sectionIds) {
        const el = document.getElementById(id);
        if (!el) continue;
        const topInRoot = el.getBoundingClientRect().top - rootTop;
        if (topInRoot <= ACTIVATE_AT) active = id; // last qualifying section wins
    }

    return active;
}

export function useActiveSection(sectionIds) {
    const [active, setActive] = useState(null);
    const { pathname } = useLocation();

    useEffect(() => {
        setActive(null);
        if (!sectionIds?.length) return;

        let cancelled = false;
        let timeoutId = null;
        let removeScroll = null;
        let retries = 0;

        function setup() {
            if (cancelled) return;
            if (retries >= MAX_RETRIES) return; // give up after 6 seconds

            retries++;

            const root = document.querySelector(".app-main");
            if (!root) {
                timeoutId = setTimeout(setup, RETRY_MS);
                return;
            }

            // Check that at least one section is in the DOM
            const hasAnySections = sectionIds.some((id) =>
                document.getElementById(id),
            );
            if (!hasAnySections) {
                timeoutId = setTimeout(setup, RETRY_MS);
                return;
            }

            // Sections are ready — attach scroll listener
            const onScroll = () => setActive(computeActive(root, sectionIds));

            root.addEventListener("scroll", onScroll, { passive: true });
            removeScroll = () => root.removeEventListener("scroll", onScroll);

            // Set initial active state (before any scroll)
            setActive(computeActive(root, sectionIds));
        }

        setup();

        return () => {
            cancelled = true;
            clearTimeout(timeoutId);
            removeScroll?.();
        };
    }, [pathname]);

    return active;
}
