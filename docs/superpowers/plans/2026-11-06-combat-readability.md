# Combat and presentation implementation plan

Goal: make combat readable, deliberate and visually rewarding while retaining saves and server authority.

Architecture: a pure Python encounter module owns attack geometry, windup timing and boss patterns. The server resolves damage using that geometry. Canvas draws the same serialized shape. Existing classes, equipment and nine regions remain compatible.

Decision: improve the existing Canvas/FastAPI game rather than replacing its renderer or progression. The user delegated implementation choices and authorized continuous execution. This directory is not a Git repository; changes stay in the supplied workspace.

- [x] Add behavioral tests for windup, locked aim, geometry, recovery and boss phases.
- [x] Implement encounter state and integrate it into the server tick and snapshots.
- [x] Render attack shapes under characters, phase cues and delayed health trails.
- [x] Add a compact boss HUD, contextual combat guidance and skill readiness feedback.
- [x] Run Python and JavaScript suites, launch locally, inspect the game and document results.

Constraints: no save reset, no new production dependencies, preserve regional isolation and safe areas. Attack shapes must match damage checks. Interrupted attacks must not resume invisibly. Death/respawn resets encounter state. Reduced motion must remain supported.
