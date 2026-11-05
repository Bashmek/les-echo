import asyncio
import time

import pytest

import server


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "test.sqlite3")
    server.init_database()
    saved_mobs = list(server.mobs)
    server.players.clear()
    server.clients.clear()
    server.mobs.clear()
    server.arrows.clear()
    server.ground_effects.clear()

    async def noop_send(event):
        return None

    monkeypatch.setattr(server, "send_event", noop_send)
    yield
    server.players.clear()
    server.clients.clear()
    server.mobs[:] = saved_mobs
    server.arrows.clear()
    server.ground_effects.clear()


def make_test_hero(name: str = "OverhaulHero") -> tuple[str, dict]:
    pid = "test_hero_1"
    p = server.default_player(pid, name)
    server.players[pid] = p
    return pid, p


def add_mob(p: dict, dx: float = 30.0, dy: float = 0.0, kind: str = "wolf", level: int = 5) -> dict:
    mob = server.scaled_mob(kind, level, len(server.mobs) + 1, p["x"] + dx, p["y"] + dy)
    mob["region"] = p["region"]
    server.mobs.append(mob)
    return mob


def test_level_cap_100_and_multi_stat_upgrades():
    pid, p = make_test_hero()
    for _ in range(120):
        need = server.xp_for_next_level(p["level"])
        if need <= 0:
            break
        server.add_xp(p, need)

    assert p["level"] == server.PLAYER_MAX_LEVEL == 100
    assert p["xp"] == 0
    assert p["talent_points"] >= 19

    # Batch stat upgrade (+5 at once) past the old 50 cap up toward 100
    p["stats"]["might"] = 50
    server.reconcile_skill_points(p)
    pts_before = p["skill_points"]
    assert pts_before >= 5
    run(server.apply_stat_upgrade(pid, p, "might", count=5))
    assert p["stats"]["might"] == 55
    assert p["skill_points"] == pts_before - 5


def test_mastery_20_and_class_perks_unlock():
    pid, p = make_test_hero()
    p["level"] = 10
    run(server.choose_class(p, {"class": "warrior"}))
    assert p["class"] == "warrior"

    for _ in range(40):
        server.award_mastery(p, "warrior", 5000)
    assert p["mastery"]["warrior"]["level"] == server.MASTERY_MAX_LEVEL == 20

    row = server.player_row(pid, p, time.monotonic())
    perks = row["class_perks"]
    assert [pk["level"] for pk in perks] == [5, 10, 15, 20]
    assert all(pk["unlocked"] for pk in perks)


def test_ability_and_spell_rank_upgrades_and_new_mage_spells():
    pid, p = make_test_hero()
    p["level"] = 25
    p["weapon"] = "elder_staff"
    p["weapons"].append("elder_staff")
    p["magic_mana_spent"] = 2000
    run(server.choose_class(p, {"class": "mage"}))
    for _ in range(15):
        server.award_mastery(p, "mage", 2000)

    now = time.monotonic()
    row = server.player_row(pid, p, now)
    for sp_id in ("frost_ring", "root_bind", "mind_chill"):
        assert sp_id in row["spells_unlocked"]

    # Upgrade a class ability using talent points up to rank 5 (evolution)
    p["talent_points"] = 6
    for _ in range(4):
        run(server.apply_skill_upgrade(pid, p, {"kind": "ability", "id": "arcane_bolt"}))
    assert server.ability_rank(p, "arcane_bolt") == 5

    # Upgrade a spell using gold + crystals
    p["gold"] = 5000
    p["inventory"]["crystal"] = 50
    run(server.apply_skill_upgrade(pid, p, {"kind": "spell", "id": "frost_ring", "use_gold": True}))
    assert server.spell_upgrade_rank(p, "frost_ring") == 1
    assert server.spell_mastery_level(p, "frost_ring") >= 2

    # Cast the three newly wired crowd-control/debuff spells on a nearby mob
    p["region"] = "forest"
    p["x"], p["y"] = 600.0, 600.0
    mob = add_mob(p, dx=40.0, dy=0.0, kind="wolf", level=6)
    mob["hp"] = mob["max_hp"] = 5000
    p["mana"] = p["max_mana"] = 500

    now = time.monotonic()
    run(server.cast_spell(p, now, "frost_ring", 1.0, 0.0, mob["x"], mob["y"]))
    assert mob["slow_until"] > now

    p["mana"] = 500
    now = time.monotonic() + 20.0
    run(server.cast_spell(p, now, "root_bind", 1.0, 0.0, mob["x"], mob["y"]))
    assert mob["stun_until"] > now

    p["mana"] = 500
    now = time.monotonic() + 40.0
    run(server.cast_spell(p, now, "mind_chill", 1.0, 0.0, mob["x"], mob["y"]))
    assert mob["sunder_until"] > now


def test_combo_chain_staff_orb_perfect_dodge_and_stagger():
    pid, p = make_test_hero()
    p["level"] = 20
    p["region"] = "forest"
    p["x"], p["y"] = 500.0, 500.0
    p["stamina"] = p["max_stamina"] = 200
    mob = add_mob(p, dx=24.0, dy=0.0, kind="wolf", level=8)
    mob["hp"] = mob["max_hp"] = 9000
    mob["max_stagger"] = 45.0
    mob["stagger"] = 0.0

    # 3-hit melee combo chain advances 1 -> 2 -> 3 and builds stagger until break
    t = time.monotonic()
    for expected_step in (1, 2, 3):
        p["next_attack"] = 0.0
        p["stamina"] = 200
        mob["x"], mob["y"] = p["x"] + 24.0, p["y"]
        server.start_attack(p, t, 1.0, 0.0)
        t += 0.45
        server.attack_release(p, t, 1.0, 0.0)
        assert p["combo_step"] == expected_step
        t += 0.35

    assert mob["staggered_until"] > 0

    # Perfect dodge when a nearby mob is about to strike grants counter-attack buff
    now = time.monotonic() + 10.0
    p["dodge_at"] = 0.0
    p["counter_until"] = 0.0
    mob["staggered_until"] = 0.0
    mob["stun_until"] = 0.0
    mob["attack_at"] = now + 0.15
    mob["x"], mob["y"] = p["x"] + 30.0, p["y"]
    run(server.handle_message(pid, p, {"type": "dodge"}, now))
    assert p["counter_until"] > now

    # Staff basic attack fires an arcane orb projectile
    p["weapon"] = "apprentice_staff"
    p["weapons"].append("apprentice_staff")
    p["next_attack"] = 0.0
    p["stamina"] = 200
    before = len(server.arrows)
    server.start_attack(p, now + 2.0, 1.0, 0.0)
    server.attack_release(p, now + 2.5, 1.0, 0.0)
    assert len(server.arrows) == before + 1
    orb = server.arrows[-1]
    assert orb["kind"] == "ability_arrow"
    assert orb["spell_kind"] == "Аркана"
    assert orb["mana_on_hit"] >= 5

    # Elemental Reaction: Frost -> Fire triggers Steam Blast bonus multiplier
    now_rx = time.monotonic() + 25.0
    mob["slow_until"] = now_rx + 3.0
    mult, rx_name = server.evaluate_combat_reaction(p, mob, "fire", False, now_rx)
    assert mult > 1.2
    assert rx_name == "ПАРОВОЙ ВЗРЫВ"


def test_post_boss_free_world_travel_unlock():
    pid, p = make_test_hero()
    p["level"] = 30
    p["region"] = "camp"
    p["last_combat"] = -999.0

    # Locked before defeating the main boss (ancient_warden)
    run(server.world_travel_action(p, {"region": "abyss"}))
    assert p["region"] == "camp"
    assert server.has_free_world_travel(p) is False

    # Defeating ancient_warden unlocks free world travel across all 9 worlds
    p["region"] = "garden"
    warden = add_mob(p, dx=20.0, dy=0.0, kind="ancient_warden", level=45)
    server.award_drop(p, warden)

    assert "ancient_warden" in p["bosses_defeated"]
    assert p["world_travel_unlocked"] is True
    assert server.has_free_world_travel(p) is True

    # Out of combat: can travel directly to any region regardless of neighbors
    p["last_combat"] = -999.0
    p["travel_lock_until"] = 0.0
    run(server.world_travel_action(p, {"region": "abyss"}))
    assert p["region"] == "abyss"

    p["travel_lock_until"] = 0.0
    run(server.world_travel_action(p, {"region": "glacier"}))
    assert p["region"] == "glacier"

    # Blocked while in combat
    p["travel_lock_until"] = 0.0
    p["last_combat"] = time.monotonic()
    run(server.world_travel_action(p, {"region": "camp"}))
    assert p["region"] == "glacier"
