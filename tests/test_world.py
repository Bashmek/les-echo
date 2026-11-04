import asyncio
import time

import pytest

import server
from world import REGIONS, NPCS, PORTALS, migrate_position, SPAWN


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "test.sqlite3")
    server.init_database()
    server.players.clear()
    server.clients.clear()
    server.arrows.clear()
    server.thorn_fields.clear()
    server.ground_effects.clear()
    yield
    server.players.clear()
    server.clients.clear()
    server.arrows.clear()
    server.thorn_fields.clear()
    server.ground_effects.clear()


@pytest.fixture
def events(monkeypatch):
    captured = []

    async def capture(event):
        captured.append(event)

    monkeypatch.setattr(server, "send_event", capture)
    return captured


def make_player(pid="p1", name="Hero", region="camp", **kw):
    p = server.default_player(pid, name)
    p["region"] = region
    p["zone"] = region
    p["market_starter_grant"] = True
    p.update(kw)
    server.players[pid] = p
    return p


def run(coro):
    return asyncio.run(coro)


def test_every_region_has_own_map_npcs_shop_and_population():
    assert len(REGIONS) == 9
    for rid, r in REGIONS.items():
        assert r["width"] == 2000 and r["height"] == 1500
        roles = [n["role"] for n in r["npcs"]]
        assert "merchant" in roles and "quest" in [s for n in r["npcs"] for s in n["services"]]
        assert rid in server.REGION_SHOPS and len(server.REGION_SHOPS[rid]) >= 5
        assert any(n["region"] == rid for n in server.nodes)
        if rid != "camp":
            assert any(m["region"] == rid for m in server.mobs)
    assert not any(m["region"] == "camp" for m in server.mobs)
    # Waystones form a bidirectional chain.
    for portal in PORTALS.values():
        back = [p for p in PORTALS.values() if p["region"] == portal["target"] and p["target"] == portal["region"]]
        assert back


def test_legacy_save_migration_keeps_region_and_uses_safe_spawn():
    rid, x, y = migrate_position({"x": 3500, "y": 900})
    assert rid == "marsh" and (x, y) == SPAWN
    rid, x, y = migrate_position({"region": "forest", "x": 500, "y": 600})
    assert rid == "forest" and (x, y) == (500, 600)


def test_snapshot_is_scoped_and_hides_other_players_inventory(events):
    a = make_player("a", "Alice", "camp", gold=500)
    b = make_player("b", "Bob", "forest", gold=900)
    snap = server.snapshot("a")
    assert snap["world"]["region"] == "camp"
    # The client receives full public metadata here, not just the region id.
    assert snap["region"]["id"] == "camp"
    assert [p["id"] for p in snap["players"]] == ["a"]
    assert all(m["region"] == "camp" for m in snap["mobs"])
    assert all(n["region"] == "camp" for n in snap["nodes"])
    server.players["b"]["region"] = "camp"
    snap = server.snapshot("a")
    other = next(p for p in snap["players"] if p["id"] == "b")
    assert "gold" not in other and "inventory" not in other


def test_travel_requires_nearby_portal_and_changes_map(events):
    p = make_player(region="camp", level=1)
    portal = next(v for v in PORTALS.values() if v["id"] == "camp-east")
    p["x"], p["y"] = portal["x"], portal["y"]
    server.arrows.append({"region": "camp", "owner": p["id"], "x": 0, "y": 0, "vx": 1, "vy": 0, "life": 1})
    run(server.travel_action(p, {"portal_id": portal["id"]}))
    assert p["region"] == "forest"
    assert "forest" in p["visited_regions"]
    assert not server.arrows
    assert any(e.get("type") == "region_changed" for e in events)


def test_travel_blocked_in_combat(events):
    p = make_player(region="camp", level=1)
    portal = next(v for v in PORTALS.values() if v["id"] == "camp-east")
    p["x"], p["y"] = portal["x"], portal["y"]
    p["last_combat"] = time.monotonic()
    run(server.travel_action(p, {"portal_id": portal["id"]}))
    assert p["region"] == "camp"


def test_recall_blocked_in_combat(events):
    p = make_player(region="forest")
    p["last_combat"] = time.monotonic()
    run(server.recall_action(p))
    assert p["region"] == "forest"


def test_shop_is_local_and_requires_merchant(events):
    p = make_player(region="camp", gold=200)
    merchant = next(n for n in REGIONS["camp"]["npcs"] if n["role"] == "merchant")
    p["x"], p["y"] = merchant["x"], merchant["y"]
    run(server.market_action(p, {"action": "buy", "id": "astral_blade", "npc_id": merchant["id"]}))
    assert p["gold"] == 200 and "astral_blade" not in p["weapons"]
    run(server.market_action(p, {"action": "buy", "id": "potion", "npc_id": merchant["id"]}))
    assert p["gold"] == 168 and p["inventory"]["potion"] == 3
    # Walking away blocks further purchases.
    p["x"] = 1500
    run(server.market_action(p, {"action": "buy", "id": "potion", "npc_id": merchant["id"]}))
    assert p["inventory"]["potion"] == 3


def test_region_quest_accept_progress_claim(events):
    p = make_player(region="forest", gold=0)
    guide = next(n for n in REGIONS["forest"]["npcs"] if "quest" in n["services"])
    p["x"], p["y"] = guide["x"], guide["y"]
    run(server.npc_quest_action(p, {"npc_id": guide["id"], "action": "accept"}))
    assert p["region_quests"]["forest"]["active"]
    server.record_region_progress(p, "herb", 5)
    server.record_region_progress(p, "slime", 5, kill=True)
    p["inventory"]["herb"] = 5
    gold, xp = p["gold"], p["xp"]
    run(server.npc_quest_action(p, {"npc_id": guide["id"], "action": "claim"}))
    assert p["region_quests"]["forest"]["done"]
    assert p["gold"] > gold and p["xp"] > xp
    assert p["inventory"]["herb"] == 0
    # Cannot claim twice.
    gold = p["gold"]
    run(server.npc_quest_action(p, {"npc_id": guide["id"], "action": "claim"}))
    assert p["gold"] == gold


def test_damage_cannot_cross_regions(events):
    p = make_player(region="camp")
    mob = next(m for m in server.mobs if m["region"] == "forest")
    mob["x"], mob["y"] = p["x"], p["y"]
    hp = mob["hp"]
    server.spell_damage(p, mob, 999, time.monotonic())
    assert mob["hp"] == hp


def test_safe_zone_blocks_pvp(events):
    a = make_player("a", region="camp")
    b = make_player("b", region="camp", x=a["x"] + 10, y=a["y"])
    hp = b["hp"]
    server._damage_players_around(a, time.monotonic(), a["x"], a["y"], 100, 50)
    assert b["hp"] == hp


def test_region_persists_through_save_load(events):
    p = make_player(region="glacier", level=12, gold=321)
    p["visited_regions"] = ["camp", "forest", "marsh", "ruins", "glacier"]
    server.save_character(p)
    loaded = server.load_character(p["name"])
    assert loaded["region"] == "glacier"
    assert loaded["gold"] == 321
    assert "glacier" in loaded["visited_regions"]
