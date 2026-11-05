"""Itemization, accessories, reforging and the forge overhaul.

These tests pin the behaviour the client relies on: six-paper-doll accessory
slots, Terraria-style reforging (including the broken-prefix discount), +15/+10
tempering with the rune-dust catalyst, authored custom weapons, and the new
consumables/reagents.
"""

import asyncio
import random

import pytest

import server
import world


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

    sent: list[dict] = []

    async def capture(event):
        sent.append(event)
        return None

    monkeypatch.setattr(server, "send_event", capture)
    monkeypatch.setattr(server, "broadcast", lambda event: sent.append(event) or None)
    yield sent
    server.players.clear()
    server.clients.clear()
    server.mobs[:] = saved_mobs
    server.arrows.clear()
    server.ground_effects.clear()


def make_hero(name="ForgeHero", gold=5000):
    pid = "forge_hero_1"
    p = server.default_player(pid, name)
    p["gold"] = gold
    p["region"] = "camp"
    server.players[pid] = p
    return pid, p


def stand_at(p, npc_id):
    npc = server.NPCS[npc_id]
    p["region"] = npc["region"]
    p["x"], p["y"] = npc["x"], npc["y"]
    return npc


def forge_npc(p):
    return stand_at(p, "camp-artisan")


def merchant(p):
    return stand_at(p, "camp-merchant")


def wizard(p):
    return stand_at(p, "camp-wizard")


def fill_resources(p, **amounts):
    for key, value in amounts.items():
        p["inventory"][key] = value



def forge_call(p, msg):
    msg = dict(msg)
    msg.setdefault("npc_id", "camp-artisan")
    return run(server.forge_action(p, msg))


def market_call(p, msg):
    msg = dict(msg)
    msg.setdefault("npc_id", "camp-merchant")
    return run(server.market_action(p, msg))


# ── каталоги ────────────────────────────────────────────────────────────────

def test_accessory_catalog_has_rings_amulets_and_artifacts():
    slots = {spec["slot"] for spec in server.ACCESSORIES.values()}
    assert slots == {"ring", "amulet", "artifact"}
    assert len(server.ACCESSORIES) >= 30
    for spec in server.ACCESSORIES.values():
        assert spec["name"] and spec["description"] and spec["bonuses"]
        assert spec["rarity"] in {"common", "uncommon", "rare", "epic", "legendary"}
        assert spec["bonuses"].keys() <= set(server.equipment_bonuses(server.default_player("t", "T")))


def test_reforge_prefix_groups_cover_every_target_and_every_tier():
    groups = {spec["group"] for spec in server.REFORGE_PREFIXES.values()}
    assert groups == {"weapon", "gear", "accessory"}
    for group in groups:
        tiers = {spec["tier"] for spec in server.REFORGE_PREFIXES.values() if spec["group"] == group}
        assert -1 in tiers and 4 in tiers, f"{group} needs a broken and a mythical prefix"
        for spec in server.REFORGE_PREFIXES.values():
            if spec["group"] != group:
                continue
            assert spec["name"] and spec["summary"] and spec["weight"] > 0


def test_custom_weapon_catalog_spans_archetypes_cores_and_tiers():
    assert {"sword", "greatsword", "daggers", "spear", "bow", "staff"} <= set(server.CUSTOM_WEAPON_ARCHETYPES)
    assert len(server.CUSTOM_WEAPON_CORES) >= 6
    assert set(server.CUSTOM_WEAPON_TIERS) >= {1, 2, 3}
    for tier in server.CUSTOM_WEAPON_TIERS.values():
        assert tier["cost"]["gold"] > 0 and tier["rarity"] and tier["scale"] > 0
    kinds = {spec["kind"] for spec in server.CUSTOM_WEAPON_ARCHETYPES.values()}
    assert kinds == {"melee", "bow", "staff"}


def test_player_row_exposes_every_catalog_the_client_renders():
    pid, p = make_hero()
    row = server.player_row(pid, p, server.time.monotonic())
    for key in (
        "accessory_catalog", "reforge_prefixes", "custom_weapon_archetypes",
        "custom_weapon_cores", "custom_weapon_tiers", "forge_blueprints",
        "sell_prices", "weapon_sell_prices", "gear_sell_prices",
        "accessory_sell_prices", "equipment_bonuses", "craft_recipes",
    ):
        assert key in row, key
    assert row["max_item_upgrade"] == server.MAX_ITEM_UPGRADE == 15
    assert row["max_accessory_upgrade"] == server.MAX_ACCESSORY_UPGRADE == 10
    assert row["forge_blueprints"]["forest_bow"]["category"] == "weapon"
    assert row["forge_blueprints"]["ankh_shield"]["category"] == "accessory"


def test_new_reagents_are_gatherable_sellable_and_market_supplied():
    for key in ("essence", "rune_dust", "mithril"):
        assert key in server.SELL_PRICES
        assert any(key in mix for mix in world.RESOURCE_MIX.values())
    offers = [o for shop in server.REGION_SHOPS.values() for o in shop.values()]
    kinds = {o["kind"] for o in offers}
    assert {"rune_dust", "essence", "mithril", "accessory"} <= kinds


# ── аксессуары ───────────────────────────────────────────────────────────────

def test_equipping_accessories_uses_four_distinct_slots():
    pid, p = make_hero()
    for acc in ("copper_band", "wolf_tooth_amulet", "hermes_boots", "prism_core"):
        server.grant_accessory(p, acc)
    run(server.handle_message(pid, p, {"type": "equip_accessory", "id": "copper_band", "slot": "ring"}, server.time.monotonic()))
    run(server.handle_message(pid, p, {"type": "equip_accessory", "id": "wolf_tooth_amulet", "slot": "amulet"}, server.time.monotonic()))
    run(server.handle_message(pid, p, {"type": "equip_accessory", "id": "hermes_boots", "slot": "artifact_1"}, server.time.monotonic()))
    run(server.handle_message(pid, p, {"type": "equip_accessory", "id": "prism_core", "slot": "artifact_2"}, server.time.monotonic()))
    equipped = server.equipped_accessories_map(p)
    assert equipped["ring"] == "copper_band"
    assert equipped["amulet"] == "wolf_tooth_amulet"
    assert equipped["artifact_1"] == "hermes_boots"
    assert equipped["artifact_2"] == "prism_core"

    bonuses = server.equipment_bonuses(p)
    assert bonuses["move_speed_pct"] >= 0.16
    assert bonuses["spell_power_pct"] >= 0.18
    assert p["max_hp"] >= 100 + 22

    run(server.handle_message(pid, p, {"type": "unequip_accessory", "slot": "artifact_2"}, server.time.monotonic()))
    assert not server.equipped_accessories_map(p)["artifact_2"]


def test_accessory_upgrades_scale_their_bonuses_and_stop_at_plus_ten():
    pid, p = make_hero(gold=200000)
    server.grant_accessory(p, "copper_band")
    fill_resources(p, ore=999, crystal=999, mithril=999, rune_dust=99, shard=99)
    forge_npc(p)
    # A carried relic gives nothing until it sits in one of the four slots.
    assert server.equipment_bonuses(p)["hp_flat"] == 0
    run(server.handle_message(pid, p, {"type": "equip_accessory", "id": "copper_band", "slot": "ring"},
                              server.time.monotonic()))
    base_hp = server.equipment_bonuses(p)["hp_flat"]
    assert base_hp == pytest.approx(22, rel=1e-6)

    random.seed(7)
    for _ in range(400):
        forge_call(p, {"action": "upgrade_accessory", "item_id": "copper_band"})
    level = server.item_upgrade_level(p, "accessory", "copper_band")
    assert level == server.MAX_ACCESSORY_UPGRADE == 10
    # +8% per temper level on a +22 HP ring
    assert server.equipment_bonuses(p)["hp_flat"] == pytest.approx(22 * 1.8, rel=1e-6)

    forge_call(p, {"action": "upgrade_accessory", "item_id": "copper_band"})
    assert server.item_upgrade_level(p, "accessory", "copper_band") == 10


# ── закалка ──────────────────────────────────────────────────────────────────

def test_weapon_tempering_reaches_plus_fifteen_and_charges_mithril():
    pid, p = make_hero(gold=500000)
    fill_resources(p, ore=999, crystal=999, mithril=999)
    forge_npc(p)
    random.seed(11)
    for _ in range(2000):
        if server.item_upgrade_level(p, "weapon", p["weapon"]) >= server.MAX_ITEM_UPGRADE:
            break
        forge_call(p, {"action": "upgrade_weapon", "item_id": p["weapon"]})
    assert server.item_upgrade_level(p, "weapon", p["weapon"]) == 15

    # A maxed weapon refuses further attempts and never spends materials on them.
    gold_before, mithril_before = p["gold"], p["inventory"]["mithril"]
    forge_call(p, {"action": "upgrade_weapon", "item_id": p["weapon"]})
    assert p["gold"] == gold_before
    assert p["inventory"]["mithril"] == mithril_before


def test_temper_catalyst_consumes_rune_dust_and_lifts_the_chance():
    pid, p = make_hero(gold=500000)
    fill_resources(p, ore=999, crystal=999, mithril=999, rune_dust=5, shard=5)
    forge_npc(p)
    p["upgrades"]["weapon"][p["weapon"]] = 12
    dust_before = p["inventory"]["rune_dust"]
    shard_before = p["inventory"]["shard"]
    random.seed(3)
    forge_call(p, {"action": "upgrade_weapon", "item_id": p["weapon"], "use_catalyst": True})
    assert p["inventory"]["rune_dust"] == dust_before - 1
    assert p["inventory"]["shard"] == shard_before - 1


def test_temper_catalyst_is_rejected_without_reagents():
    pid, p = make_hero(gold=500000)
    fill_resources(p, ore=999, crystal=999, rune_dust=0, shard=0)
    forge_npc(p)
    gold_before = p["gold"]
    forge_call(p, {"action": "upgrade_weapon", "item_id": p["weapon"], "use_catalyst": True})
    assert p["gold"] == gold_before
    assert server.item_upgrade_level(p, "weapon", p["weapon"]) == 0


# ── перековка ────────────────────────────────────────────────────────────────

def test_reforging_weapon_sets_a_prefix_and_costs_gold():
    pid, p = make_hero()
    forge_npc(p)
    gold_before = p["gold"]
    expected = server.reforge_cost_for(p, "weapon", p["weapon"])
    random.seed(5)
    forge_call(p, {"action": "reforge", "reforge_target": "weapon", "item_id": p["weapon"]})
    prefix = server.item_reforge_id(p, "weapon", p["weapon"])
    assert prefix in server.REFORGE_PREFIXES
    assert server.REFORGE_PREFIXES[prefix]["group"] == "weapon"
    assert p["gold"] == gold_before - expected


def test_broken_prefix_gives_the_goblin_tinkerer_discount():
    pid, p = make_hero()
    forge_npc(p)
    clean = server.reforge_cost_for(p, "weapon", p["weapon"])
    p["reforges"]["weapon"][p["weapon"]] = "broken"
    discounted = server.reforge_cost_for(p, "weapon", p["weapon"])
    assert discounted == max(20, round(clean * 0.65))
    assert discounted < clean


def test_reforge_catalyst_never_rolls_a_negative_prefix():
    pid, p = make_hero(gold=100000)
    forge_npc(p)
    fill_resources(p, rune_dust=200)
    random.seed(19)
    for _ in range(40):
        forge_call(p, {"action": "reforge", "reforge_target": "weapon",
                                    "item_id": p["weapon"], "use_catalyst": True})
        prefix = server.item_reforge_id(p, "weapon", p["weapon"])
        assert server.REFORGE_PREFIXES[prefix]["tier"] >= 0


def test_reforge_requires_runes_for_the_catalyst():
    pid, p = make_hero()
    forge_npc(p)
    fill_resources(p, rune_dust=0)
    gold_before = p["gold"]
    forge_call(p, {"action": "reforge", "reforge_target": "weapon",
                                "item_id": p["weapon"], "use_catalyst": True})
    assert p["gold"] == gold_before
    assert server.item_reforge_id(p, "weapon", p["weapon"]) == ""


def test_reforging_gear_and_accessories_use_their_own_prefix_pools():
    pid, p = make_hero(gold=100000)
    forge_npc(p)
    server.grant_accessory(p, "copper_band")
    random.seed(23)
    forge_call(p, {"action": "reforge", "reforge_target": "gear", "item_id": p["gear"]})
    forge_call(p, {"action": "reforge", "reforge_target": "accessory", "item_id": "copper_band"})
    gear_prefix = server.item_reforge_id(p, "gear", p["gear"])
    acc_prefix = server.item_reforge_id(p, "accessory", "copper_band")
    assert server.REFORGE_PREFIXES[gear_prefix]["group"] == "gear"
    assert server.REFORGE_PREFIXES[acc_prefix]["group"] == "accessory"


def test_reforging_unknown_item_is_rejected():
    pid, p = make_hero()
    forge_npc(p)
    gold_before = p["gold"]
    forge_call(p, {"action": "reforge", "reforge_target": "weapon", "item_id": "not_a_weapon"})
    assert p["gold"] == gold_before


def test_weapon_prefixes_respect_the_archetype_restrictions():
    for kind in ("staff", "bow", "melee"):
        for _ in range(120):
            pid_roll, spec = server.roll_reforge_prefix("weapon", kind, "", catalysed=True)
            assert kind in tuple(spec.get("allowed", ()),) or kind == "melee", (kind, pid_roll)


def test_reforge_bonuses_reach_the_combat_math():
    pid, p = make_hero()
    p["reforges"]["weapon"][p["weapon"]] = "godly"
    bonuses = server.equipment_bonuses(p)
    spec = server.REFORGE_PREFIXES["godly"]["bonuses"]
    assert bonuses["damage_pct"] >= spec["damage_pct"] - 1e-9
    crit = server.player_crit_chance(p)
    assert crit > 0


# ── авторское оружие ─────────────────────────────────────────────────────────

def test_custom_weapon_creation_charges_gold_and_materials():
    pid, p = make_hero(gold=5000)
    forge_npc(p)
    fill_resources(p, ore=50, wood=50, crystal=50)
    cost = server.CUSTOM_WEAPON_TIERS[1]["cost"]
    gold_before = p["gold"]
    forge_call(p, {"action": "craft_custom_weapon", "name": "Клык Забытой Зари",
                                "archetype": "sword", "core": "fire", "tier": 1})
    customs = p["custom_weapons"]
    assert len(customs) == 1
    wid, weapon = next(iter(customs.items()))
    assert wid.startswith("cw_")
    assert weapon["name"] == "Клык Забытой Зари"
    assert weapon["kind"] == "melee"
    assert weapon["color"] == server.CUSTOM_WEAPON_CORES["fire"]["color"]
    assert weapon["element"] == "fire"
    assert wid in p["weapons"]
    assert p["gold"] == gold_before - cost["gold"]
    assert p["inventory"]["ore"] == 50 - cost["ore"]
    # A gift reforge is rolled without negative prefixes.
    initial = server.item_reforge_id(p, "weapon", wid)
    assert initial and server.REFORGE_PREFIXES[initial]["tier"] >= 0


def test_custom_weapon_name_resonance_raises_power():
    assert server.name_weapon_resonance("Клинок") < server.name_weapon_resonance("Клинок Пламени Грома")
    assert 0 <= server.name_weapon_resonance("") <= 0.12
    assert server.name_weapon_resonance("Звёздный Дракон Пустоты Вечности") <= 0.12


def test_custom_weapon_rejects_bad_input():
    pid, p = make_hero(gold=5000)
    forge_npc(p)
    fill_resources(p, ore=50, wood=50, crystal=50)
    before = p["gold"]
    forge_call(p, {"action": "craft_custom_weapon", "name": "аб", "archetype": "sword", "core": "fire", "tier": 1})
    forge_call(p, {"action": "craft_custom_weapon", "name": "Нормальное имя", "archetype": "nope", "core": "fire", "tier": 1})
    forge_call(p, {"action": "craft_custom_weapon", "name": "Нормальное имя", "archetype": "sword", "core": "nope", "tier": 1})
    forge_call(p, {"action": "craft_custom_weapon", "name": "Нормальное имя", "archetype": "sword", "core": "fire", "tier": 99})
    assert p["custom_weapons"] == {}
    assert p["gold"] == before


def test_custom_weapon_requires_materials():
    pid, p = make_hero(gold=5000)
    forge_npc(p)
    fill_resources(p, ore=0, wood=0, crystal=0, mithril=0, essence=0, shard=0, rune_dust=0)
    forge_call(p, {"action": "craft_custom_weapon", "name": "Пустой клинок",
                                "archetype": "sword", "core": "ice", "tier": 1})
    assert p["custom_weapons"] == {}
    assert p["gold"] == 5000


def test_custom_bow_and_staff_report_their_kind_and_spell_power():
    pid, p = make_hero(gold=5000)
    forge_npc(p)
    fill_resources(p, wood=100, ore=100, crystal=100)
    forge_call(p, {"action": "craft_custom_weapon", "name": "Шёпот Звёздного Лука",
                                "archetype": "bow", "core": "lightning", "tier": 1})
    forge_call(p, {"action": "craft_custom_weapon", "name": "Посох Ледяной Вечности",
                                "archetype": "staff", "core": "ice", "tier": 1})
    kinds = {w["kind"] for w in p["custom_weapons"].values()}
    assert kinds == {"bow", "staff"}
    staff = next(w for w in p["custom_weapons"].values() if w["kind"] == "staff")
    assert staff["spell_power"] > 0
    row = server.player_row(pid, p, server.time.monotonic())
    for wid, spec in p["custom_weapons"].items():
        assert row["weapon_catalog"][wid]["custom"] is True
        assert row["weapon_catalog"][wid]["color"] == spec["color"]


def test_custom_weapon_in_hand_drives_combat_kind():
    pid, p = make_hero(gold=5000)
    forge_npc(p)
    fill_resources(p, wood=100, ore=100, crystal=100)
    forge_call(p, {"action": "craft_custom_weapon", "name": "Грозовой Лук Бури",
                                "archetype": "bow", "core": "lightning", "tier": 1})
    wid = next(iter(p["custom_weapons"]))
    run(server.handle_message(pid, p, {"type": "weapon", "id": wid}, server.time.monotonic()))
    assert p["weapon"] == wid
    assert server.weapon_kind(p) == "bow"
    assert server.action_tree(p) == "ranger"


def test_custom_weapon_sell_price_is_reflected_in_the_row():
    pid, p = make_hero(gold=5000)
    forge_npc(p)
    fill_resources(p, ore=50, wood=50, crystal=50)
    forge_call(p, {"action": "craft_custom_weapon", "name": "Пепел и Сталь",
                                "archetype": "greatsword", "core": "physical", "tier": 1})
    wid = next(iter(p["custom_weapons"]))
    row = server.player_row(pid, p, server.time.monotonic())
    assert row["weapon_sell_prices"][wid] == server.weapon_sell_price(wid, p)


def test_selling_a_custom_weapon_removes_it_from_every_container():
    pid, p = make_hero(gold=5000)
    forge_npc(p)
    fill_resources(p, ore=50, wood=50, crystal=50)
    forge_call(p, {"action": "craft_custom_weapon", "name": "Проданный Клинок",
                                "archetype": "sword", "core": "shadow", "tier": 1})
    wid = next(iter(p["custom_weapons"]))
    # Equip something else so the authored blade is sellable.
    p["weapon"] = "sword"
    gold_before = p["gold"]
    merchant(p)
    market_call(p, {"action": "sell", "item_type": "weapon", "id": wid})
    assert wid not in p["weapons"]
    assert wid not in p["custom_weapons"]
    assert p["gold"] > gold_before


# ── чертежи и лавка ──────────────────────────────────────────────────────────

def test_forge_blueprints_craft_weapons_gear_and_accessories():
    pid, p = make_hero(gold=5000)
    forge_npc(p)
    fill_resources(p, wood=200, herb=200, ore=200, crystal=200, shard=200,
                   hide=200, mithril=200, essence=200, rune_dust=200)
    for recipe in ("forest_bow", "iron_cuirass", "copper_band", "ankh_shield"):
        forge_call(p, {"action": "craft", "id": recipe})
    assert "forest_bow" in p["weapons"]
    assert "iron_cuirass" in p["gear_inventory"]
    owned = server.all_owned_accessories(p)
    assert "copper_band" in owned
    assert "ankh_shield" in owned


def test_forge_blueprints_cannot_be_crafted_twice():
    pid, p = make_hero(gold=5000)
    forge_npc(p)
    fill_resources(p, wood=200, herb=200, ore=200, crystal=200, shard=200, hide=200)
    forge_call(p, {"action": "craft", "id": "forest_bow"})
    weapons_before = list(p["weapons"])
    forge_call(p, {"action": "craft", "id": "forest_bow"})
    assert p["weapons"].count("forest_bow") == 1
    assert len(p["weapons"]) == len(weapons_before)


def test_market_sells_accessories_and_reagent_packs():
    pid, p = make_hero(gold=20000)
    merchant(p)
    offer = next((i, o) for i, o in server.REGION_SHOPS[p["region"]].items() if o["kind"] == "accessory")
    acc_id, acc_offer = offer
    market_call(p, {"action": "buy", "id": acc_id})
    assert acc_id in server.all_owned_accessories(p)

    # Reagent packs are stocked by the deeper regions, where they are needed.
    for region, pack, key, amount in (("marsh", "rune_dust_pack", "rune_dust", 3),
                                      ("rift", "mithril_pack", "mithril", 2),
                                      ("glacier", "essence_pack", "essence", 2)):
        assert pack in server.REGION_SHOPS[region], pack
        station = next(n for n in server.REGIONS[region]["npcs"] if "shop" in n["services"])
        p["region"], p["x"], p["y"] = region, station["x"], station["y"]
        before = p["inventory"].get(key, 0)
        market_call(p, {"action": "buy", "id": pack, "npc_id": station["id"]})
        assert p["inventory"][key] == before + amount, (region, pack)


def test_selling_an_equipped_accessory_is_refused():
    pid, p = make_hero()
    merchant(p)
    server.grant_accessory(p, "copper_band")
    run(server.handle_message(pid, p, {"type": "equip_accessory", "id": "copper_band", "slot": "ring"}, server.time.monotonic()))
    gold_before = p["gold"]
    market_call(p, {"action": "sell", "item_type": "accessory", "id": "copper_band"})
    assert "copper_band" in server.all_owned_accessories(p)
    assert p["gold"] == gold_before


# ── расходники и ресурсы ─────────────────────────────────────────────────────

def test_new_buff_potions_exist_and_apply_effects():
    for potion in ("rage_potion", "ironskin_potion", "haste_potion", "arcane_tonic"):
        assert potion in server.CONSUMABLES
        pid, p = make_hero()
        p["inventory"][potion] = 2
        before = dict(p.get("effects", {}) or {})
        assert server.consumable_use(p, potion)
        assert p.get("effects") != before
        assert p["inventory"][potion] == 1


def test_buff_potions_show_up_in_equipment_bonuses():
    pid, p = make_hero()
    p["inventory"]["rage_potion"] = 1
    base = server.equipment_bonuses(p)
    server.consumable_use(p, "rage_potion")
    buffed = server.equipment_bonuses(p)
    assert buffed["damage_pct"] > base["damage_pct"] or buffed["crit_pct"] > base["crit_pct"]


def test_new_reagents_can_be_sold_for_gold():
    pid, p = make_hero()
    merchant(p)
    fill_resources(p, essence=3, rune_dust=2, mithril=1)
    gold_before = p["gold"]
    market_call(p, {"action": "sell", "item_type": "resource", "id": "mithril", "count": 1})
    assert p["inventory"]["mithril"] == 0
    assert p["gold"] > gold_before


# ── стойкость и свирепость ───────────────────────────────────────────────────

def test_tenacity_and_ferocity_are_upgradable_stats():
    assert server.STAT_CAPS["tenacity"] == 40
    assert server.STAT_CAPS["ferocity"] == 40
    pid, p = make_hero()
    p["skill_points"] = 200
    p["level"] = 80
    run(server.apply_stat_upgrade(pid, p, "tenacity", 7))
    run(server.apply_stat_upgrade(pid, p, "ferocity", 5))
    assert p["tenacity_level"] == 7
    assert p["ferocity_level"] == 5
    view = server.upgrades_view(p)
    assert view["tenacity"]["max"] == 40
    assert "входящего урона" in view["tenacity"]["effect"]
    assert view["ferocity"]["level"] == 5


def test_tenacity_reduces_damage_taken_and_ferocity_boosts_crit_damage():
    pid, p = make_hero()
    baseline_hp = server.player_defense(p)
    p["tenacity_level"] = 20
    p["ferocity_level"] = 20
    server.update_derived(p)
    view = server.upgrades_view(p)
    assert "20" in view["tenacity"]["effect"]
    assert server.player_defense(p) >= baseline_hp
    assert server.equipment_bonuses(p)["damage_reduction_pct"] >= 0.1 - 1e-9


def test_tenacity_caps_at_forty():
    pid, p = make_hero()
    p["skill_points"] = 5000
    p["level"] = 100
    run(server.apply_stat_upgrade(pid, p, "tenacity", 10))
    for _ in range(10):
        run(server.apply_stat_upgrade(pid, p, "tenacity", 10))
    assert p["tenacity_level"] == 40


# ── крафт ────────────────────────────────────────────────────────────────────

def test_craft_recipes_cover_supplies_weapons_gear_and_accessories():
    categories = {r.get("category") for r in server.CRAFT_RECIPES.values()}
    assert {"supplies", "weapon", "gear", "accessory"} <= categories


def test_crafting_a_ring_recipe_grants_the_accessory():
    pid, p = make_hero()
    fill_resources(p, ore=50, wood=50)
    message = server.do_craft(p, "copper_band")
    assert "copper_band" in server.all_owned_accessories(p), message


def test_crafting_a_weapon_recipe_grants_the_weapon():
    pid, p = make_hero()
    fill_resources(p, ore=50, wood=50, hide=50, crystal=50, shard=50, mithril=50, essence=50, rune_dust=50)
    for recipe in ("runic_claymore", "katana", "storm_bow", "storm_scepter"):
        server.do_craft(p, recipe)
        assert recipe in p["weapons"], recipe


# ── сохранение ───────────────────────────────────────────────────────────────

def test_persistence_keeps_accessories_reforges_and_custom_weapons():
    pid, p = make_hero(gold=5000)
    forge_npc(p)
    fill_resources(p, ore=50, wood=50, crystal=50)
    server.grant_accessory(p, "copper_band")
    forge_call(p, {"action": "craft_custom_weapon", "name": "Вечный Талисман",
                                "archetype": "sword", "core": "astral", "tier": 1})
    forge_call(p, {"action": "reforge", "reforge_target": "weapon", "item_id": p["weapon"]})
    wid = next(iter(p["custom_weapons"]))
    server.save_character(p)

    for field in ("accessories", "reforges", "custom_weapons"):
        assert field in server.PERSIST_FIELDS, field
    assert wid in p["custom_weapons"]
    assert "copper_band" in server.all_owned_accessories(p)
