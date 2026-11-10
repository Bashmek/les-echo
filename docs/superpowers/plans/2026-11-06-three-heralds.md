# Three Heralds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship three phase-based regional mini-bosses, a persistent side-story chapter, a high-tier reforge catalyst, one chapter-locked chain spell, and a lower-cost minimap loop.

**Architecture:** Keep combat outcomes and progression in FastAPI's existing server and region population. `encounters.py` owns attack timing and tells; `world.py` supplies stable spawns. The existing quest journal and NPC dialogue expose the story. Client canvas recognizes mini-bosses as elites without marking them as main-boss victories.

**Tech Stack:** Python 3.12, FastAPI, SQLite JSON saves, Canvas 2D, browser JavaScript, `pytest`, and Node's built-in test runner. No dependencies are added.

**Spec:** `docs/superpowers/specs/2026-11-06-three-heralds-design.md`

## Global Constraints

- Keep nine existing regions, existing main story, and saves intact.
- Server remains authoritative for combat, quest progress, spell unlocks, and materials.
- Mini-bosses do not count as main bosses or unlock world travel.
- A herald seal guarantees reforge prefix tier `>= 3`, costs one seal, and cannot be combined with rune dust.
- Mini-map refresh interval is 100 ms; the main scene remains requestAnimationFrame-driven.
- Existing saves missing herald fields use zero/empty state; no database reset or new dependency.

## Review Focus

- A client cannot claim a herald chapter without accepting it and defeating the correct mini-boss.
- A mini-boss kill in another region does not advance the active hunt.
- Defeating a mini-boss or claiming an old boss does not set main-boss travel unlocks.
- Reforge requests with both catalysts, missing seals, or invalid items spend neither material.
- Chapter progress and awarded spell availability survive save/load for both current and legacy characters.

---

### Task 1: Clean duplicate state and pace the minimap

**Files:**
- Modify: `server.py`
- Modify: `static/map-events.js`, `static/game.js`
- Test: `tests/test_stability_regressions.py`, `tests/map_events.test.js`

**Interfaces:**
- Produces: `EchoMapEvents.createMinimapRefreshGate(intervalMs)` returns a stateful `(nowMs, regionId) -> boolean` gate; `frame(now)` consults the gate before drawing the minimap.

- [x] Add a regression test for one `spell_control` definition and a behavioral test for `createMinimapRefreshGate`: first draw, suppress at 99 ms, redraw at 100 ms, and redraw immediately after a region id changes.
- [x] Run those tests and confirm they fail because the helper is absent and `spell_control` is duplicated.
- [x] Remove the duplicate definition and confirmed dead locals in `upgrades_view` and `stats_upgrade_endpoint`. Confirm the `player_row` mana field is unique.
- [x] Add and use the 100 ms minimap gate. Reset it when no region snapshot exists so the next valid region paints immediately.
- [x] Run `pytest tests/test_stability_regressions.py tests/test_progression_and_combat_overhaul.py -q` and `node --test tests/map_events.test.js`; expect all pass.

### Task 2: Add three region mini-bosses and authored attack cycles

**Files:**
- Modify: `server.py`, `world.py`, `encounters.py`
- Test: `tests/test_heralds.py`, `tests/test_encounters.py`

**Interfaces:**
- Produces: enemy ids `bramble_warden`, `fen_matron`, and `ashbound_herald`, each with `mini_boss: true`, three server-defined phases and a unique attack name for each attack shape.
- Consumes: `encounters.advance_attack`, serialized `attack_hint`, existing `scaled_mob`, and `world.populate`.

- [x] Add failing tests that each mini-boss spawns exactly once in forest/marsh/ruins at its configured level, carries `mini_boss` without `boss`, and yields a distinct three-phase attack view.
- [x] Run the focused tests and confirm failures identify missing mob data and phase-aware patterns.
- [x] Add authored monster specs, deterministic fixed spawns outside the existing main-boss arena, and three new population entries.
- [x] Extend encounter phase and cooldown logic to mini-bosses, with unique tell names and shapes while retaining existing main-boss patterns.
- [x] Run focused encounter and world suites; expect all pass and existing main-boss phase tests unchanged.

### Task 3: Connect herald hunts, reforge seals, and the echo spell

**Files:**
- Modify: `server.py`
- Test: `tests/test_heralds.py`, `tests/test_itemization_forge_overhaul.py`, `tests/test_mage.py`

**Interfaces:**
- Produces: `HERALD_QUESTS`, `herald_story_view(p)`, persisted `herald_story_stage`, `herald_story_active`, and `herald_story_kills`; a `champion_seal` inventory reagent; story-locked `echo_lattice` spell.
- Consumes: `npc_quest_action`, `quest_journal`, `award_drop`, `roll_reforge_prefix`, and the existing lightning spell branch.

- [x] Add failing tests for the three chapter actions, wrong-target kills, reward and spell unlock, save/load continuity, herald-seal drop, high-tier reroll, and rejection without spending when catalyst inputs are invalid.
- [x] Run these tests and confirm failures identify missing quest state, drop behavior, spell definition, and reforge tier floor.
- [x] Implement the separate quest state and serialize it. Award one seal per mini-boss defeat and advance only the matching accepted hunt.
- [x] Add a herald catalyst with guaranteed prefix tier 3+, mutual exclusion from rune dust, and atomic validation before consuming gold or materials.
- [x] Add `echo_lattice` to the spell catalog; route its chain hits through the existing spell damage/control path and unlock it only after chapter completion.
- [x] Run herald, quest, itemization, and mage suites; expect pass without changing prior reforge odds or old quest stages.

### Task 4: Show the new chapter and elite fights in the client

**Files:**
- Modify: `static/game.js`, `static/world.js`, `static/render.js`, `static/encounters.js`, `static/encounters.css`, `static/inventory.js`, `static/index.html`
- Test: `tests/encounters.test.js`, `tests/itemization_forge_ui.test.js`, `tests/progression_ui.test.js`, `tests/render.test.js`

**Interfaces:**
- Consumes: player-row herald story view and `mini_boss`/attack fields in snapshots.
- Produces: visible camp dialogue actions and journal card, clear mini-boss name/aura/health HUD, inventory seal entry, forge seal toggle, and named spell card.

- [x] Add failing UI tests for mini-boss selection, spell display, journal/dialogue action, forge catalyst, and authored names/models.
- [x] Run the focused UI suite and confirm it reports each missing surface.
- [x] Render client-side objectives and camp dialogue actions using text-safe escaping; send `quest_kind: 'herald_story'` to the server.
- [x] Mark mini-bosses as elites in canvas and HUD, add authored silhouettes/details and consistent boss-color tells; keep main boss travel indicators tied to `boss` only.
- [x] Add the reagent label and the selectable high-tier forge catalyst, including handling that never sends both catalysts.
- [x] Bump the static cache version, run Python and JavaScript suites and syntax checks, and verify the local site plus versioned game/render assets return HTTP 200 with the new story/elite UI.
- [ ] Visually verify the quest and forge UI at desktop and mobile viewport sizes. The local app window launch hit a computer-use approval timeout; no browser window was changed.

### Task 5: Give herald signature attacks distinct combat riders

**Files:**
- Modify: `server.py`, `encounters.py`, `static/encounters.js`, `static/encounters.css`, `static/game.js`
- Test: `tests/test_encounters.py`, `tests/test_herald_combat_effects.py`, `tests/test_movement.py`, `tests/encounters.test.js`, `tests/progression_ui.test.js`

**Interfaces:**
- Produces: authored slow, poison, and burn riders attached to the Root Warden's rush, the Fen Matron's spit, and the Ashbound Herald's ash ring; live player status and damage-over-time ticks.
- Consumes: the existing server-side attack geometry, player status HUD, and status fields already used by PvP abilities.

- [x] Add failing tests for the three attack riders, unaffected ordinary/main bosses, non-stacking DOT refresh, tick timing, and slow movement.
- [x] Run the focused tests and confirm they fail because the attack metadata and player effect handling are absent.
- [x] Apply status only after a herald hit lands, never on a successful parry or dodge; expose an explanatory effect label in the attack tell.
- [x] Make player slow and stun influence movement and make existing poison/fire player effects tick with bounded damage, PvP scaling, and status cleanup on death/respawn.
- [x] Run focused combat suites, all project Python/JavaScript tests, syntax checks, and live static-asset checks.

### Task 6: Keep crafting UI state and listeners stable between snapshots

**Files:**
- Modify: `static/game.js`
- Test: `tests/itemization_forge_ui.test.js`

- [x] Add a regression test that crafting tab state is outside `updateHud` and tab handlers are not rebound per snapshot.
- [x] Confirm the focused UI test fails on the nested state and listener registration.
- [x] Lift crafting view state/helpers and one-time event binding out of `updateHud`; keep per-snapshot rendering in the HUD update path.
- [x] Run focused and complete JavaScript suites and syntax checks.

## Workspace note

No `.git` directory is present in the supplied project, so work directly in this explicitly authorized workspace and do not create commits. Preserve the existing SQLite file and all saved characters.
