# Field bestiary implementation

Spec: `docs/superpowers/specs/2026-11-08-field-bestiary-design.md`.

- [x] Add persistent, sanitized bestiary progress and a full-snapshot catalog; emit idempotent region-scoped defeat events with co-op eligibility.
- [x] Add the searchable, filtered collection dialog and procedural portrait callback; verify data/DOM lifecycle behavior.
- [x] Add bounded monster defeat effects and eligible victory banners with real-time expiry and reduced-motion support.
- [x] Wire menu/controls, snapshots, event feedback and travel cleanup; update user-facing guidance.
- [x] Review integration, run active project tests with saves protected, and check script syntax/static asset delivery.

Integration review also fixed capture-phase Tab handling, focus restoration from the hidden parent menu, tall portrait clipping, and the pre-existing duplicate atlas link. See `docs/superpowers/verification/2026-11-08-field-bestiary.md` for checks and scope.
