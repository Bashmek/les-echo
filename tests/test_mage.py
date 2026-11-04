"""Mage kit: class abilities that cost mana, and the spell row moved off 1–9."""

import math
import time

import pytest

import server


MAGE_ABILITIES = ["arcane_bolt", "frost_lance", "flame_burst", "chain_lightning",
                  "blink", "arcane_shield", "mana_surge", "meteor_fall"]


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "test.sqlite3")
    server.init_database()
    # The world population is module-level state: keep it for the other tests.
    saved_mobs = list(server.mobs)
    server.players.clear()
    server.clients.clear()
    server.mobs.clear()
    server.arrows.clear()
    server.ground_effects.clear()
    yield
    server.players.clear()
    server.clients.clear()
    server.mobs[:] = saved_mobs
    server.arrows.clear()
    server.ground_effects.clear()


@pytest.fixture
def events(monkeypatch):
    captured = []

    async def capture(event):
        captured.append(event)

    monkeypatch.setattr(server, "send_event", capture)
    return captured


def mage(pid="m", mastery=5, mana=200, max_mana=None, **kw):
    p = server.default_player(pid, "Мерлин")
    p["class"] = "mage"
    p["class_name"] = "Маг"
    p["weapon"] = "apprentice_staff"
    p["mana"] = mana
    p["max_mana"] = int(max_mana if max_mana is not None else max(100, mana))
    p["mastery"] = server.normalize_mastery({tree: {"level": mastery} for tree in server.MASTERY_TREES})
    p.update(kw)
    server.players[pid] = p
    return p


def add_mob(pid, dx, dy, kind="wolf", level=2):
    mob = server.scaled_mob(kind, level, len(server.mobs), 0.0, 0.0)
    mob["region"] = server.players[pid]["region"]
    mob["x"] = server.players[pid]["x"] + dx
    mob["y"] = server.players[pid]["y"] + dy
    server.mobs.append(mob)
    return mob


def cast(p, ability, aim=(1, 0), target=None):
    p["ability_lock_until"] = 0.0
    tx, ty = target if target else (p["x"] + aim[0] * 120, p["y"] + aim[1] * 120)
    import asyncio
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        server.use_ability(p, time.monotonic(), ability, aim[0], aim[1], tx, ty))


# ── catalog ──────────────────────────────────────────────────────────────
def test_every_mage_ability_is_mana_based_and_in_the_class_list():
    assert sorted(server.CLASSES["mage"]["abilities"]) == sorted(MAGE_ABILITIES)
    for ability_id in MAGE_ABILITIES:
        spec = server.ABILITY_CATALOG[ability_id]
        assert spec["tree"] == "mage", ability_id
        assert spec.get("resource") == "mana", ability_id
        assert int(spec["cost"]) >= 0
        assert 1 <= int(spec["mastery"]) <= server.MASTERY_MAX_LEVEL
        assert spec["desc"] and spec["name"] and spec.get("key")


def test_mage_ability_keys_do_not_collide_with_the_rest_of_the_keymap():
    keys = [server.ABILITY_CATALOG[a].get("key") for a in MAGE_ABILITIES]
    assert len(set(keys)) == len(keys), "маг не должен делить клавишу между способностями"
    busy = {"KeyW", "KeyA", "KeyS", "KeyD", "KeyE", "KeyF", "KeyI", "KeyM", "KeyB",
            "KeyG", "KeyH", "KeyQ", "KeyC", "KeyV", "KeyZ"}
    for key in keys:
        assert key not in busy, key


def test_mage_abilities_roll_out_with_mastery():
    low = mage(pid="low", mastery=1)
    assert server.ability_unlocked(low, "arcane_bolt")
    assert not server.ability_unlocked(low, "meteor_fall")
    high = mage(pid="high", mastery=5)
    assert all(server.ability_unlocked(high, a) for a in MAGE_ABILITIES)


# ── gating ───────────────────────────────────────────────────────────────
def test_abilities_need_the_class_and_a_staff(events):
    p = mage()
    p["weapon"] = "sword"
    p["ability_lock_until"] = 0
    cast(p, "arcane_bolt")
    assert not server.arrows
    p["weapon"] = "apprentice_staff"
    p["class"] = "warrior"
    p["ability_lock_until"] = 0
    cast(p, "arcane_bolt")
    assert not server.arrows


def test_mana_is_spent_instead_of_stamina(events):
    p = mage(mana=120)
    stamina = p["stamina"]
    cast(p, "chain_lightning")
    assert p["mana"] == 120 - server.ABILITY_CATALOG["chain_lightning"]["cost"]
    assert p["stamina"] == stamina


def test_not_enough_mana_blocks_the_cast(events):
    p = mage(mana=5)
    cast(p, "meteor_fall")
    assert p["mana"] == 5
    assert not [e for e in events if e.get("type") == "ability_cast"]
    assert any("маны" in str(e.get("text", "")) for e in events)


# ── effects ──────────────────────────────────────────────────────────────
def test_arcane_bolt_fires_an_elemental_projectile(events):
    p = mage()
    cast(p, "arcane_bolt")
    assert len(server.arrows) == 1
    bolt = server.arrows[0]
    assert bolt["element"] == "arcane" and bolt["spell_kind"] == "Аркана"
    assert bolt["owner"] == p["id"] and bolt["damage"] >= 1
    assert any(e.get("type") == "ability_cast" for e in events)


def test_frost_lance_carries_a_slow(events):
    p = mage()
    cast(p, "frost_lance")
    bolt = server.arrows[0]
    assert bolt["element"] == "ice"
    assert bolt["slow_duration"] == pytest.approx(3.5)
    assert bolt["slow_factor"] < 1


def test_flame_burst_damages_and_ignites_the_area(events):
    p = mage()
    near = add_mob("m", 40, 0)
    far = add_mob("m", 600, 0)
    cast(p, "flame_burst", target=(p["x"] + 40, p["y"]))
    assert near["hp"] < near["max_hp"]
    assert float(near.get("burn_until", 0)) > 0
    assert near["burn_owner"] == p["id"]
    assert far["hp"] == far["max_hp"]


def test_chain_lightning_jumps_three_times_with_falloff(events):
    p = mage()
    mobs = [add_mob("m", 60 + i * 25, 0) for i in range(5)]
    cast(p, "chain_lightning", target=(p["x"] + 80, p["y"]))
    hit = [m for m in mobs if m["hp"] < m["max_hp"]]
    assert len(hit) == 3
    damage = sorted((m["max_hp"] - m["hp"] for m in hit), reverse=True)
    assert damage[0] > damage[1] > damage[2]
    event = next(e for e in events if e.get("type") == "ability_cast")
    assert len(event["chain"]) == 3


def test_blink_moves_the_caster_forward(events):
    p = mage()
    start = (p["x"], p["y"])
    cast(p, "blink")
    moved = math.hypot(p["x"] - start[0], p["y"] - start[1])
    assert moved == pytest.approx(server.ABILITY_CATALOG["blink"]["distance"], abs=1.0)
    event = next(e for e in events if e.get("type") == "ability_cast")
    assert (event["from_x"], event["from_y"]) == (round(start[0], 1), round(start[1], 1))


def test_arcane_shield_adds_temporary_defense(events):
    p = mage()
    before = server.player_defense(p)
    cast(p, "arcane_shield")
    assert server.player_defense(p) == before + server.ABILITY_CATALOG["arcane_shield"]["armor"]
    assert any(e.get("kind") == "ward" for e in server.player_effects(p, time.monotonic()))
    p["ward_until"] = 0.0
    assert server.player_defense(p) == before


def test_mana_surge_refills_mana_and_never_overshoots(events):
    p = mage(mana=10)
    cast(p, "mana_surge")
    assert p["mana"] == 38
    p["mana"] = 95
    p["ability_cooldowns"] = {}
    cast(p, "mana_surge")
    assert p["mana"] == p["max_mana"]


def test_meteor_fall_hits_everything_in_the_blast(events):
    p = mage()
    near = [add_mob("m", 30 + i * 20, 10) for i in range(3)]
    outside = add_mob("m", 900, 0)
    cast(p, "meteor_fall", target=(p["x"] + 60, p["y"]))
    assert all(m["hp"] < m["max_hp"] for m in near)
    assert outside["hp"] == outside["max_hp"]


def test_abilities_view_reports_the_resource():
    p = mage()
    view = server.abilities_view(p, time.monotonic())
    assert view["arcane_bolt"]["resource"] == "mana"
    assert view["roar"]["resource"] == "stamina"
