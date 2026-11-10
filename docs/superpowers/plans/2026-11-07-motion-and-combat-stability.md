# Motion and combat stability

Goal: consistent movement and camera response at different refresh rates, bounded transient effects, and agreement between client combat controls and server rules.

The user delegated implementation choices and authorized running checks. Keep server authority, current content, SQLite saves and the existing running server intact.

## Design choices

Use elapsed-time exponential easing for visual positions. Preserve the current 260-unit teleport threshold, use an 18 ms half-life for the local hero and 32 ms for other entities, and return the same position on repeated calls at one frame timestamp. A buffered snapshot interpolator would add input delay; speculative movement would need client collision simulation. Neither is needed for this correction.

Keep real time for telegraphs, cooldowns and effect expiry. A separate monotonic motion clock pauses entity movement during hitstop. Snap visual history after map/respawn transitions or a render gap over 250 ms. Convert camera easing coefficients from the existing 60 Hz tuning to elapsed time.

## Work

- [x] Add `static/motion.js` and behavioral tests for refresh-rate invariance, same-frame idempotence, teleport/respawn resets, stale-view cleanup and a monotonic hitstop clock.
- [x] Integrate motion into `world.js` and `render.js`; use displayed positions for camera, culling and targeting; reset/prune entity animation caches.
- [x] Integrate the independently tested transient-effect pool; expire old combat queues in place and bound particles during suspended rendering.
- [x] Integrate client combat rules for charge speed, Mage/staff gating and armor temper benefits; correct misleading class copy.
- [x] Verify the isolated backend fixes for projectile criticals, elemental arrows and empty-quiver resource consumption.
- [x] Run related behavioral tests, syntax checks and the active project suites; perform a read-only review of integration risks.

Review focus: region changes during hitstop, multiple position lookups per frame, long background-tab gaps, expired effects while no RAF runs, full player updates followed by compact snapshots, negative attack-speed reforges, and attacks that fail before resource consumption.


## Verification

- Active Python suite: 147 passed, including 8 real projectile release/tick regressions; access to the real save database was blocked throughout the run.
- JavaScript suite: 124 passed, including actual renderer/handler integration, 30/60/120 Hz motion, bounded hitstop storms and 30/60/144 Hz particle trajectories.
- All 12 client scripts passed `node --check`; the existing HTTP server returned 200 for the page and all six modified/new runtime script endpoints.
- Independent backend/client reviews found no remaining issues after fixing sustained hitstop and HUD workshop-cache invalidation.
- Hitstop starts at most once per 250 ms, never extends an active pause, and nearby impacts affect the camera only within 280 world units.
- Browser visual QA was attempted in isolated headless profiles. Chrome failed GPU initialization and Edge timed out enabling its runtime; no screenshot or interactive visual result is claimed.
