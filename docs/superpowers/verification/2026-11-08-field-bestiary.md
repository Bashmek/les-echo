# Field bestiary verification — 2026-11-08

Implemented the spec in `../specs/2026-11-08-field-bestiary-design.md`.

## Delivered behavior

- A field journal for all 21 existing monster kinds, reachable from Esc and the controls panel. Search and region/status filters respect locked identities. Credited kills unlock discovery at 1, study at 5, and hunting mastery at 15.
- Lore and qualitative loot hints are authored in `bestiary.py`; stats and habitats come from the actual monster/population definitions. Tactical descriptions were checked against `encounters.py` and loot against `award_drop`.
- Counts survive character saves, sanitize malformed input, and recover existing boss history. Eligible co-op contributors receive one count per death. The static catalog is private to the own full row; compact updates carry counts and peers carry neither field.
- A 780 ms defeat echo shares the existing 70-effect pool. Eligible boss/mini-boss victories show a 2.6 s notice and a short, throttled WebAudio chord. Effects expire on real time and reset on travel/auth changes; reduced motion keeps stationary geometry and removes banner animation.
- Monster respawns now reset `_kill_rewarded` and `_contributors`, so later lives can reward players again.
- Review fixes allow Tab to reach the dialog focus trap, restore focus to the visible game-menu button, and fit all portrait silhouettes inside their canvas. The Esc menu's duplicate atlas insertion was removed; its canonical link remains functional.
- The in-game guide and README now describe the journal, +15/+10 tempering caps, and the current spell progression.

## Automated checks

- **165 Python tests passed** with `pytest.main(['tests', '-q'])`. A wrapper rejected `sqlite3.connect` calls to the real `echo_saves.sqlite3`; persistence cases used temporary databases. Four existing FastAPI `on_event` deprecation warnings remain.
- **149 Node tests passed**, including bestiary data/DOM tests, actual menu/socket handler integration, defeat effects and lifecycle, audio graph/throttling, and the atlas regression.
- All **13 static JavaScript files** passed `node --check`; `world.js` was checked again after removing the duplicate atlas insertion.
- The running local server returned HTTP 200 for the page and all 18 linked static assets. Modified assets have fresh cache versions.
- Independent backend review found no actionable defects. Independent client review found the Tab and portrait issues; both were reproduced with failing tests, fixed, and re-reviewed. The atlas duplication was reproduced in the full browser fixture and covered by two additional behavioral tests.

## Browser checks

The in-app browser worked even though earlier headless Chrome/Edge launches failed. Used temporary static fixtures served by the existing local server; no second game server was started.

The standalone fixture used real catalog data, real `bestiary.js`/CSS, and the real sprite renderer. Checked search, region/status filters, locked identities, empty results, portrait fitting and focus. Verified the one-column layout at 390 px, default two-column layout at 639 px, and three columns at 1440 px, with no horizontal page overflow. The viewport override was reset.

The full-client fixture used the shipped page and all client scripts. Authentication/fetch and WebSocket traffic were replaced with local test data built by `server.snapshot`; SQLite access was blocked while constructing it. Verified:

1. Esc → bestiary opens the real journal above the game and hides combat HUD presentation.
2. Shift+Tab wraps inside the dialog; Tab returns to its close button; Escape restores focus to `gameMenuButton`.
3. A defeat event passes through the real WebSocket dispatcher, removes the test monster, displays its echo and eligible victory notice, and updates discovery from 3 to 4 species.
4. The notice expires; the next region snapshot closes the journal and clears victory feedback.
5. The final menu has one atlas entry; clicking it closes the Esc menu and opens/focuses the atlas.

No warnings or errors were recorded in either fixture's browser console. These are client integration checks with simulated packets; real multiplayer reward/persistence behavior was tested separately in Python.

Screenshots and disposable preview HTML were retained under `.scratch/`. Temporary preview pages were removed from `static/` after checking. Existing live accounts and the real save database were not used for QA.
