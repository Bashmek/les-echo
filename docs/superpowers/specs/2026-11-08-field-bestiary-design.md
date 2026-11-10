# Field bestiary and victory feedback

The user requested continued broad game improvements and delegated implementation choices, testing and agents. This increment gives existing monsters a visible collection/progression loop and clear defeat feedback, using existing maps and procedural sprites.

## Player experience

A bestiary opens from the game menu and the controls panel. It has search, region/status filters, a discovered-species total and cards with portraits. Before the first credited kill, show an unknown silhouette and its region; after discovery reveal the monster name, lore, base stats, tactical advice and qualitative loot hints. State clearly that combat stats scale with monster level. Collection ranks use credited kills: 1 discovered, 5 studied, 15 hunting mastery. Ranks are collection goals and do not change combat power.

Defeated monsters leave a short procedural shatter/echo effect. Eligible players defeating a boss or mini-boss see a brief victory banner with its identity. A first credited normal-monster kill produces a small discovery notice. All effects are region-scoped, bounded and expire on the real clock; map transitions clear them. Respect reduced motion. Keep existing hitstop bounds.

## Backend contract

- Persist `bestiary_kills`, a map from known monster kind to credited kill count. Sanitize unknown keys, malformed values and counts outside 0..1,000,000. Initialize fresh players with an empty map. Legacy `bosses_defeated` seeds one kill for known boss kinds without inventing ordinary-species history.
- Every recipient accepted by the existing co-op reward rules gets exactly one count; the existing `_kill_rewarded` guard prevents duplicates. Do not reset collection counts when quests change.
- Own `player_row` exposes `bestiary_kills` in all snapshots and `bestiary_catalog` only in full snapshots. Peers never receive either field. Compact snapshots retain the current protocol and omit the static catalog.
- `bestiary_catalog` is a list of entries, one per known monster. Each has `id`, `name`, `regions` (list of `{id,name,level}`), `boss`, `mini_boss`, `color`, `size`, `base_hp`, `base_damage`, `range`, `cooldown`, `xp`, `lore`, `tactics` (list of strings), `loot` (qualitative display strings). Build numeric data from actual monster definitions and locations from actual population data. No fabricated drop rates.
- `award_drop` emits one region-scoped event per rewarded death:

```text
{type:'mob_defeated',region,mob,kind,name,level,x,y,boss,mini_boss,color,size,
 participants:[eligible player IDs],discoveries:[IDs with their first credited kill of this kind]}
```

## Client contracts and ownership

- Backend worker owns `server.py`, new `bestiary.py`, `tests/test_bestiary.py` only.
- Bestiary UI worker owns new `static/bestiary.js`, `static/bestiary.css`, `tests/bestiary.test.js` only. UMD API `EchoBestiary.create({document,drawPortrait})` returns `{open(player),close(),sync(player),isOpen(),root}`. Lazily inject a dialog with id `bestiaryOverlay`, role dialog and close button. `drawPortrait(canvas,entry,discovered)` is called on card rebuild only. `sync` does no DOM work while closed and signatures include counts/filter changes. Export useful pure selection/summary helpers for behavioral tests.
- Victory worker owns `static/render.js`, `static/encounters.js`, `static/encounters.css`, new `tests/defeat_feedback.test.js` only. Add `LesEchoFx.defeat(event)` for world effects, and `EncounterView.onDefeat(event,playerId,nowMs)` for an eligible boss/mini-boss victory banner. Add/reset lifecycle APIs as needed; keep effects in existing bounded pools and preserve the real/motion clock distinction.
- Root owns `static/game.js`, `static/index.html`, `static/world.js`, documentation and integration tests. It wires scripts/styles/menu, event dispatch, current player updates, portraits and map/reset cleanup. Keep the current keymap; no new reserved gameplay shortcut.

## Verification

Behavioral tests cover co-op/duplicate counting, save-load migration/sanitization, catalog coverage and snapshot privacy/compaction, locked-card filtering, ranks/search/regions, open/closed UI updates, defeat effect expiry/pool cap, local eligibility and region changes. Root runs the active Python/Node suites with real-save access blocked, syntax/HTTP checks and independent review. Do not launch another game server or use the real save database for QA.
