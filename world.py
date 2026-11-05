"""Authoritative region definitions for Les Echo.

Every region owns a local coordinate system, population, resource nodes,
NPCs, shop and waystones.  The renderer derives its terrain from the same
public region metadata; it never decides whether a transition is legal.
"""
from __future__ import annotations

import math
import random
from typing import Any

MAP_W, MAP_H = 2000, 1500
SPAWN = (350.0, 840.0)
SAFE_CENTER = (390.0, 800.0)
SAFE_RADIUS = 275.0
NPC_RADIUS = 125.0
PORTAL_RADIUS = 145.0
COMBAT_LOCK = 6.0

_REGION_DATA = [
    dict(id="camp", name="Лагерь Следопытов", short="Тихая гавань", chapter="I", min_level=1, danger=0,
         level="Безопасная зона", accent="#e7c77d", ground="#536b45", dark="#344b35", light="#81945b",
         description="Тёплый костёр, знакомые лица и первая тропа в большой мир. Здесь начинается каждая история.",
         lore="Пока горит костёр, лес помнит дорогу домой.", landmark="Костёр следопытов", weather="fireflies",
         guide=("Егор Хранитель", "keeper", "Лес стал громче. Пройди тропы от опушки до Первозданного сада — и узнай, что будит эхо."),
         merchant=("Марта · припасы", "Лагерь «Тёплый костёр»", ["bandage", "potion", "arrows", "leather_vest", "scout_tunic", "acolyte_robe", "mace", "crystal_wand", "copper_band", "wolf_tooth_amulet", "wolf_cloak"]),
         artisan=("Борис Ковач", "Кузница у костра", "forge"),
         quest=("Огонь очага", "wood", 6, "herb", 3, "", 0),
         stock_note="Припасы, первое оружие, кольца и броня"),
    dict(id="forest", name="Шепчущий лес", short="Там, где шепчут листья", chapter="II", min_level=1, danger=1,
         level="Уровень 1–3", accent="#b7d98a", ground="#496344", dark="#263f34", light="#78945a",
         description="Солнечные поляны скрывают волчьи тропы. За старым мостом лес уже не узнаёт чужаков.",
         lore="Не каждый шёпот принадлежит ветру.", landmark="Сердце древнего леса", weather="leaves",
         guide=("Лесана Следопыт", "ranger", "Слизни расползлись по опушке, а волки не дают собрать лунную траву. Помоги лесу снова задышать."),
         merchant=("Тихон · лесной торг", "Лавка «Лисий хвост»", ["potion", "arrows", "haste_potion", "claws", "twinblades", "hunter_crossbow", "forest_bow", "chain_shirt", "emerald_ring", "hermes_boots", "mana_potion"]),
         artisan=("Ярь · резчик рун", "Мастерская лесных рун", "wizard"),
         quest=("Шёпот под корнями", "herb", 5, "slime", 0, "slime", 5),
         stock_note="Луки, арбалеты, сапоги ветра и перстни следопыта"),
    dict(id="marsh", name="Затонувшие топи", short="Огни над чёрной водой", chapter="III", min_level=4, danger=2,
         level="Уровень 4–6", accent="#83d8c2", ground="#3e6259", dark="#243f40", light="#6c8c70",
         description="Деревянные мостки связывают острова среди тумана. Болотные огни обещают сокровища — и ведут в трясину.",
         lore="Вода хранит имена тех, кто не вернулся.", landmark="Затонувший маяк", weather="mist",
         guide=("Ведана Травница", "herbalist", "Огоньки заманивают путников в трясину. Погаси их и принеси кристаллы со дна — я поставлю оберег."),
         merchant=("Шрам · болотный торг", "Лавка «Чёрная вода»", ["potion", "stamina_potion", "ironskin_potion", "iron_sword", "marsh_armor", "iron_cuirass", "bark_plate", "sapphire_mana_ring", "moon_dew_pendant", "bog_amber_torc", "throwing_knife", "rune_dust_pack"]),
         artisan=("Рудобор · топь", "Плавучая кузница", "forge"),
         quest=("Огни обманщики", "crystal", 5, "herb", 0, "wisp", 5),
         stock_note="Болотная сталь, кирасы, рунная пыль и кулоны"),
    dict(id="ruins", name="Пепельные руины", short="Город, который не погас", chapter="IV", min_level=7, danger=3,
         level="Уровень 7–10", accent="#efad78", ground="#6b5b4c", dark="#403b38", light="#9c8264",
         description="Под сводами разрушенных башен всё ещё тлеет огонь. Пепельный колосс охраняет сердце последней кузни.",
         lore="Камень остыл. Клятва стражей — нет.", landmark="Пепельная кузня", weather="embers",
         guide=("Игнат Летописец", "scholar", "Стражи забыли, кого охраняют. Останови колосса и собери осколки старой печати."),
         merchant=("Фрида · руины", "Лавка «Последний жар»", ["potion", "rage_potion", "ember_staff", "flamberge", "thunder_fists", "runic_claymore", "ember_mail", "runic_vestments", "warhammer", "ruby_fang_ring", "pyre_talisman", "feral_claws_art", "mana_potion", "rune_dust_pack"]),
         artisan=("Эскель · пепел", "Кузница последнего жара", "forge"),
         quest=("Печать пепла", "shard", 5, "ore", 0, "colossus", 1),
         stock_note="Огненные посохи, двуручники, рубиновые перстни и артефакты"),
    dict(id="glacier", name="Хребет Синего Пламени", short="По ту сторону инея", chapter="V", min_level=11, danger=4,
         level="Уровень 11–14", accent="#a5e5f2", ground="#718e98", dark="#3b5869", light="#b5d4d6",
         description="Ледяные шпили поют на ветру. Синее пламя не греет, но не даёт погаснуть последней надежде.",
         lore="Даже у холода есть сердце.", landmark="Кристалл синего пламени", weather="snow",
         guide=("Сэйра Льдинка", "mage", "Ледяные змеи спускаются к перевалу. Их чешуя остудит жар разлома — если добудешь её."),
         merchant=("Ниве · север", "Лавка «Синий иней»", ["potion", "mana_potion", "arcane_tonic", "crystal_bow", "frost_spear", "frostguard_plate", "hunter_brigandine", "moon_staff", "frost_band", "glacier_heart_amulet", "mana_flower", "magic_quiver", "elixir", "essence_pack"]),
         artisan=("Хальд · иней", "Мастерская вечного льда", "wizard"),
         quest=("Песня ледяных шпилей", "crystal", 8, "ore", 0, "frost_wyrm", 4),
         stock_note="Морозные пики, луки, артефакты маны и колчаны"),
    dict(id="rift", name="Разлом Эха", short="Трещина в памяти мира", chapter="VI", min_level=15, danger=5,
         level="Уровень 15–19", accent="#caa6f4", ground="#514665", dark="#302c46", light="#8971a2",
         description="Острова парят над пустотой, а дорожные камни помнят другие миры. В глубине разлома дышит дракон.",
         lore="Эхо отвечает раньше, чем прозвучит вопрос.", landmark="Алтарь эха", weather="runes",
         guide=("Орин Разломщик", "mage", "Дракон Пустого Эха питается страхом. Собери осколки и разорви круг, пока разлом не поглотил лес."),
         merchant=("Нокс · межмирье", "Лавка «Седьмая грань»", ["rift_shard", "mana_potion", "rage_potion", "daggers", "katana", "storm_bow", "storm_scepter", "spear", "void_cloak", "shadow_garb", "stormweaver_coat", "stormbrand", "void_signet", "dragon_fang_necklace", "storm_mirror", "mithril_pack"]),
         artisan=("Вейл · осколки", "Рунная мастерская разлома", "wizard"),
         quest=("Сердце разлома", "shard", 10, "crystal", 0, "echo_dragon", 1),
         stock_note="Катаны, штормовые луки, перстни разлома и зеркала бури"),
    dict(id="abyss", name="Астральная Бездна", short="Между звёздами и тишиной", chapter="VII", min_level=20, danger=6,
         level="Уровень 20–25", accent="#91c9f5", ground="#343d59", dark="#20283e", light="#657ba0",
         description="Созвездия отражаются в каменных кругах. Титан Бездны стережёт дорогу к краю ночного неба.",
         lore="Здесь звезды смотрят в ответ.", landmark="Обсерватория без стен", weather="stars",
         guide=("Астра Ночная", "scholar", "Титан сдвигает созвездия. Верни осколки неба на место, иначе дорога в сад исчезнет."),
         merchant=("Элиан · звёзды", "Лавка «Падающая звезда»", ["elixir", "mana_potion", "arcane_tonic", "astral_blade", "shadow_repeater", "blood_tome", "archon_staff", "scythe", "halberd", "phantom_shroud", "archmage_regalia", "astral_compass_amulet", "chrono_hourglass", "prism_core", "mithril_pack"]),
         artisan=("Соляр · эфир", "Обсерватория эфира", "wizard"),
         quest=("Упавшее созвездие", "crystal", 12, "shard", 0, "astral_titan", 1),
         stock_note="Астральное оружие, регалии архонта и часы вечности"),
    dict(id="obsidian", name="Обсидиановый край", short="На границе чёрного стекла", chapter="VIII", min_level=26, danger=7,
         level="Уровень 26–30", accent="#d5a4cf", ground="#4e4054", dark="#2c2735", light="#806783",
         description="Вулканическое стекло режет горизонт. Под алыми прожилками скал куётся оружие для последнего пути.",
         lore="Стекло помнит форму огня.", landmark="Осколок чёрного стекла", weather="embers",
         guide=("Карн Страж", "warrior", "Стражи чёрного стекла закрывают перевал. Добудь руду из их брони и открой путь к саду."),
         merchant=("Мора · обсидиан", "Лавка «Чёрное зеркало»", ["elixir", "rage_potion", "ironskin_potion", "obsidian_axe", "blood_reaper", "dragonbone_bow", "war_maul", "glaive", "crimson_plate", "dragonscale_mail", "void_cloak", "obsidian_bastion_ring", "reaper_choker", "blood_chalice", "titan_gauntlet", "rift_shard"]),
         artisan=("Торн · стекло", "Кузница чёрного стекла", "forge"),
         quest=("Ключ из чёрного стекла", "ore", 16, "shard", 0, "obsidian_sentinel", 5),
         stock_note="Кровавые косы, драконья чешуя, граали и рукавицы титанов"),
    dict(id="garden", name="Первозданный сад", short="Там, где мир был первым", chapter="IX", min_level=31, danger=8,
         level="Уровень 31–35", accent="#d4e6a0", ground="#52734d", dark="#2d4939", light="#91ad6c",
         description="Гигантские корни держат остатки первого леса. Под цветами спит хранитель, которому снятся все девять земель.",
         lore="Конец тропы — начало нового семени.", landmark="Сердце Первозданного сада", weather="petals",
         guide=("Ива Безмолвная", "herbalist", "Сад болен. Звёздочёты крадут его сны, а древний хранитель не может проснуться. Исцели корни."),
         merchant=("Элль · семена", "Лавка «Первый рассвет»", ["elixir", "rage_potion", "arcane_tonic", "elder_staff", "cosmos_staff", "sunfall_bow", "zenith_bow", "solar_halberd", "eclipse_katana", "sunforged_aegis", "celestial_raiment", "celestial_band", "eden_seed_amulet", "ankh_shield", "shadow_cloak_art", "mana_potion", "stamina_potion", "rift_shard"]),
         artisan=("Корень · память", "Мастерская живых корней", "wizard"),
         quest=("Сны первого леса", "herb", 18, "crystal", 0, "ancient_warden", 1),
         stock_note="Мифические реликвии, созвездия, кольца и реликвии несокрушимости"),
]

REGIONS: dict[str, dict[str, Any]] = {}
NPCS: dict[str, dict[str, Any]] = {}
PORTALS: dict[str, dict[str, Any]] = {}
POWER_SITES: list[dict[str, Any]] = []
REGION_QUESTS: dict[str, dict[str, Any]] = {}

for _i, _data in enumerate(_REGION_DATA):
    _r = dict(_data)
    _r.update(width=MAP_W, height=MAP_H, seed=241 + _i * 97,
              spawn=list(SPAWN), safe_center=list(SAFE_CENTER), safe_radius=SAFE_RADIUS,
              neighbors=[_REGION_DATA[_j]["id"] for _j in (_i - 1, _i + 1) if 0 <= _j < len(_REGION_DATA)],
              landmark_pos=[1480, 390], boss_arena=[1560, 1130])
    REGIONS[_r["id"]] = _r
    _guide, _merchant, _artisan = _data["guide"], _data["merchant"], _data["artisan"]
    _npcs = [
        dict(id=f"{_r['id']}-guide", name=_guide[0], role=_guide[1], title="Хранитель истории" if _r["id"] == "camp" else "Местный житель",
             x=350, y=650, color=_r["accent"], services=["quest"], dialogue=_guide[2]),
        dict(id=f"{_r['id']}-merchant", name=_merchant[0], role="merchant", title=_merchant[1],
             x=615, y=705, color="#e7c77d", services=["shop"], stock=list(_merchant[2]),
             dialogue="Хорошая вещь в дороге дороже золота. Посмотри товар — я не обману своего."),
        dict(id=f"{_r['id']}-artisan", name=_artisan[0], role=_artisan[2], title=_artisan[1],
             x=590, y=955, color="#9ccbd8" if _artisan[2] == "wizard" else "#e6a879",
             services=["forge", "wizard"], dialogue="Принеси материалы — вместе заставим их служить тебе."),
    ]
    if _r["id"] == "camp":
        _npcs.append(dict(id="camp-wizard", name="Альвин Чародей", role="wizard", title="Святилище первых чар",
                          x=800, y=650, color="#9ccbd8", services=["wizard"],
                          dialogue="Магия растёт, когда ею делятся. Твой первый посох уже ждёт."))
    _r["npcs"] = _npcs
    NPCS.update({n["id"]: {**n, "region": _r["id"]} for n in _npcs})
    for _side, _x in (("west", 110), ("east", 1890)):
        _target = _r["neighbors"][0 if _side == "west" else -1] if _r["neighbors"] else None
        if _target and ((_side == "west" and _i > 0) or (_side == "east" and _i < len(_REGION_DATA) - 1)):
            _p = dict(id=f"{_r['id']}-{_side}", region=_r["id"], target=_target, x=_x, y=820, side=_side)
            PORTALS[_p["id"]] = _p
    _title, _res, _n, _res2, _n2, _mob, _mob_n = _data["quest"]
    REGION_QUESTS[_r["id"]] = dict(id=f"region-{_r['id']}", title=_title, resource=_res, count=_n,
                                  resource2=_res2, count2=_n2, mob=_mob, mob_count=_mob_n,
                                  gold=60 + _r["danger"] * 95, xp=100 + _r["danger"] * 240,
                                  description=_guide[2])
    POWER_SITES.append(dict(id=f"site-{_r['id']}", region=_r["id"], name=_r["landmark"],
                            x=1050, y=430, radius=170, buff="Здоровье, мана и выносливость +2/с"))

ZONES = list(REGIONS.values())

# ---------------------------------------------------------------------------
# Solid scenery
# ---------------------------------------------------------------------------
# The client draws these props from the same list, so a tree you can see is a
# tree you cannot walk through.  Placement is deterministic (region seed), is
# kept off the roads, the hub plaza, waystones, the power site and the boss
# arena, and leaves enough room to fight around every prop.
OBSTACLE_KINDS: dict[str, dict[str, Any]] = {
    "tree": {"r": 17.0, "block": 13.0, "h": 46.0},
    "bush": {"r": 11.0, "block": 8.0, "h": 16.0},
    "rock": {"r": 15.0, "block": 12.0, "h": 18.0},
    "pillar": {"r": 13.0, "block": 10.0, "h": 58.0},
    "crystal": {"r": 14.0, "block": 11.0, "h": 34.0},
    "reed": {"r": 9.0, "block": 6.0, "h": 22.0},
    "stump": {"r": 12.0, "block": 9.0, "h": 14.0},
}

_REGION_OBSTACLE_MIX = {
    "camp": [("tree", 46), ("bush", 14), ("rock", 8), ("stump", 4)],
    "forest": [("tree", 58), ("bush", 16), ("rock", 8), ("stump", 5)],
    "marsh": [("tree", 30), ("reed", 30), ("rock", 10), ("bush", 8)],
    "ruins": [("pillar", 26), ("rock", 26), ("bush", 12), ("stump", 6)],
    "glacier": [("crystal", 30), ("rock", 28), ("tree", 14)],
    "rift": [("crystal", 34), ("pillar", 24), ("rock", 14)],
    "abyss": [("crystal", 38), ("pillar", 22), ("rock", 12)],
    "obsidian": [("crystal", 34), ("rock", 30), ("pillar", 14)],
    "garden": [("tree", 40), ("bush", 24), ("rock", 10), ("crystal", 12)],
}


def _build_region_obstacles() -> None:
    for r in REGIONS.values():
        rng = random.Random(int(r["seed"]) * 31 + 7)
        mix = _REGION_OBSTACLE_MIX.get(r["id"], [("tree", 30), ("rock", 20)])
        weights = [w for _, w in mix]
        pool = [k for k, _ in mix]
        total = 96 if r["danger"] else 72
        portals = [p for p in PORTALS.values() if p["region"] == r["id"]]
        obstacles: list[dict[str, Any]] = []
        for attempt in range(total * 90):
            if len(obstacles) >= total:
                break
            x = round(rng.uniform(70, MAP_W - 70), 1)
            y = round(rng.uniform(90, MAP_H - 70), 1)
            # Main road corridor and the settlement need room to breathe.
            if 728 <= y <= 912:
                continue
            if x < 840 and 470 <= y <= 1130:
                continue
            if math.hypot(x - r["safe_center"][0], y - r["safe_center"][1]) < 360:
                continue
            if math.hypot(x - 1050, y - 430) < 245:
                continue
            if math.hypot(x - r["landmark_pos"][0], y - r["landmark_pos"][1]) < 205:
                continue
            if math.hypot(x - r["boss_arena"][0], y - r["boss_arena"][1]) < 195:
                continue
            if any(math.hypot(x - p["x"], y - p["y"]) < 155 for p in portals):
                continue
            if any(math.hypot(x - n["x"], y - n["y"]) < 128 for n in r["npcs"]):
                continue
            if any(math.hypot(x - o["x"], y - o["y"]) < 84 for o in obstacles):
                continue
            kind = rng.choices(pool, weights=weights, k=1)[0]
            spec = OBSTACLE_KINDS[kind]
            scale = round(rng.uniform(.82, 1.22) * (1.0 if kind in ("bush", "reed") else rng.uniform(.9, 1.08)), 2)
            obstacles.append({
                "id": f"{r['id']}-ob-{len(obstacles)}",
                "kind": kind,
                "x": x, "y": y,
                "r": round(spec["block"] * scale, 1),
                "h": round(spec["h"] * scale, 1),
                "variant": round(rng.random(), 3),
                "scale": scale,
            })
        r["obstacles"] = obstacles


_build_region_obstacles()


def obstacles_for(region_id: str) -> list[dict[str, Any]]:
    return REGIONS.get(region_id, REGIONS["camp"]).get("obstacles", [])


def resolve_collision(region_id: str, x: float, y: float, radius: float = 15.0) -> tuple[float, float]:
    """Push a circle out of the solid scenery of one region.

    Three relaxation passes are enough for the sparse prop layout and keep the
    result stable when a player is squeezed between a tree and the map border.
    """
    x = max(25.0, min(MAP_W - 25.0, float(x)))
    y = max(25.0, min(MAP_H - 25.0, float(y)))
    for _ in range(3):
        moved = False
        for ob in obstacles_for(region_id):
            dx, dy = x - ob["x"], y - ob["y"]
            min_d = radius + float(ob["r"])
            if abs(dx) > min_d or abs(dy) > min_d:
                continue
            d = math.hypot(dx, dy)
            if d >= min_d:
                continue
            if d < 0.001:
                dx, dy, d = 1.0, 0.0, 1.0
            x = ob["x"] + dx / d * min_d
            y = ob["y"] + dy / d * min_d
            moved = True
        if not moved:
            break
    return max(25.0, min(MAP_W - 25.0, x)), max(25.0, min(MAP_H - 25.0, y))


def collision_blocked(region_id: str, x: float, y: float, radius: float = 15.0) -> bool:
    return any(math.hypot(x - ob["x"], y - ob["y"]) < radius + float(ob["r"])
               for ob in obstacles_for(region_id))
POPULATION = {
    "forest": [("slime", 8, 1), ("wolf", 5, 2)],
    "marsh": [("boar", 6, 4), ("wisp", 5, 5), ("stone", 2, 6)],
    "ruins": [("ashling", 6, 7), ("ashguard", 4, 8), ("colossus", 1, 10)],
    "glacier": [("frost_wyrm", 7, 11), ("frost_wyrm", 4, 13)],
    "rift": [("rift_knight", 7, 15), ("echo_dragon", 1, 20)],
    "abyss": [("void_wraith", 8, 21), ("astral_titan", 1, 25)],
    "obsidian": [("obsidian_sentinel", 7, 27), ("void_wraith", 5, 28), ("obsidian_sentinel", 1, 30)],
    "garden": [("starseer", 7, 31), ("ancient_warden", 1, 35), ("starseer", 5, 33)],
}
RESOURCE_MIX = {
    "camp": ["wood", "wood", "herb", "herb", "ore"],
    "forest": ["wood", "herb", "herb", "ore", "slime", "essence"],
    "marsh": ["herb", "ore", "ore", "crystal", "crystal", "essence"],
    "ruins": ["ore", "ore", "crystal", "shard", "wood", "rune_dust", "mithril"],
    "glacier": ["ore", "crystal", "crystal", "wood", "herb", "essence", "mithril"],
    "rift": ["shard", "shard", "crystal", "ore", "rune_dust", "mithril", "essence"],
    "abyss": ["crystal", "shard", "crystal", "mithril", "rune_dust", "essence"],
    "obsidian": ["ore", "shard", "crystal", "mithril", "mithril", "rune_dust"],
    "garden": ["herb", "herb", "crystal", "shard", "essence", "mithril", "rune_dust"],
}


def region_for(entity: dict[str, Any]) -> dict[str, Any]:
    return REGIONS.get(str(entity.get("region", "camp")), REGIONS["camp"])


def is_safe(entity: dict[str, Any]) -> bool:
    r = region_for(entity)
    if r["danger"] == 0:
        return True
    x, y = float(entity.get("x", 0)), float(entity.get("y", 0))
    cx, cy = r["safe_center"]
    return math.hypot(x - cx, y - cy) <= r["safe_radius"] or any(
        p["region"] == r["id"] and math.hypot(x - p["x"], y - p["y"]) < 115 for p in PORTALS.values())


def same_region(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a.get("region", "camp") == b.get("region", "camp")


def near_npc(p: dict[str, Any], npc_id: str, service: str | None = None) -> dict[str, Any] | None:
    npc = NPCS.get(npc_id)
    if not npc or not same_region(p, npc) or (service and service not in npc["services"]):
        return None
    return npc if math.hypot(p["x"] - npc["x"], p["y"] - npc["y"]) <= NPC_RADIUS else None


def nearest_npc(p: dict[str, Any]) -> dict[str, Any] | None:
    return min((n for n in region_for(p)["npcs"] if math.hypot(p["x"] - n["x"], p["y"] - n["y"]) <= NPC_RADIUS),
               key=lambda n: math.hypot(p["x"] - n["x"], p["y"] - n["y"]), default=None)


def build_shops(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rid: {item: catalog[item] for item in r["npcs"][1]["stock"]} for rid, r in REGIONS.items()}


def public_region(r: dict[str, Any]) -> dict[str, Any]:
    return {k: r[k] for k in ("id", "name", "short", "chapter", "min_level", "danger", "level", "accent",
                              "ground", "dark", "light", "description", "lore", "landmark", "weather", "width",
                              "height", "seed", "spawn", "safe_center", "safe_radius", "neighbors", "landmark_pos",
                              "boss_arena", "npcs", "stock_note", "obstacles")}


def atlas_view() -> list[dict[str, Any]]:
    return [{k: r[k] for k in ("id", "name", "short", "chapter", "min_level", "danger", "level", "accent",
                               "description", "neighbors", "stock_note", "npcs")} |
            {"merchant": r["npcs"][1]["name"], "shop": r["npcs"][1]["title"]} for r in REGIONS.values()]


def migrate_position(data: dict[str, Any]) -> tuple[str, float, float]:
    """Map the old 12600×7200 strip into a safe arrival point, once per save."""
    rid = str(data.get("region", ""))
    if rid in REGIONS:
        r = REGIONS[rid]
        return rid, max(30.0, min(r["width"] - 30.0, float(data.get("x", SPAWN[0])))), max(30.0, min(r["height"] - 30.0, float(data.get("y", SPAWN[1]))))
    x = float(data.get("x", 330))
    index = max(0, min(len(REGIONS) - 1, int(x // 1400)))
    return list(REGIONS)[index], *SPAWN


def populate(mob_factory: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mobs, nodes = [], []
    for rid, r in REGIONS.items():
        rng = random.Random(r["seed"])
        index = 0
        for kind, count, level in POPULATION.get(rid, []):
            for _ in range(count):
                index += 1
                boss = kind in {"colossus", "echo_dragon", "astral_titan", "ancient_warden"}
                if boss:
                    x, y = r["boss_arena"]
                else:
                    x, y = rng.uniform(820, 1770), rng.uniform(180, 1320)
                    if math.hypot(x - 1050, y - 430) < 240:
                        y = max(650, y)
                mob = mob_factory(kind, level + (0 if boss else rng.choice([0, 0, 1])), index, x, y)
                mob["region"] = rid
                mob["id"] = f"{rid}-{mob['id']}"
                mobs.append(mob)
        mix = RESOURCE_MIX[rid]
        # Guarantee that every local commission can be completed on its own map.
        quest = REGION_QUESTS[rid]
        guaranteed = [quest["resource"]] * 4 + ([quest["resource2"]] * 3 if quest["resource2"] else [])
        for i in range(30 if r["danger"] else 18):
            kind = guaranteed[i] if i < len(guaranteed) else rng.choice(mix)
            for _attempt in range(100):
                x, y = rng.uniform(120, 1880), rng.uniform(140, 1360)
                if any(math.hypot(x - n["x"], y - n["y"]) < 125 for n in r["npcs"]):
                    continue
                if any(math.hypot(x - p["x"], y - p["y"]) < 90 for p in PORTALS.values() if p["region"] == rid):
                    continue
                if any(math.hypot(x - n["x"], y - n["y"]) < 55 for n in nodes if n["region"] == rid):
                    continue
                break
            nodes.append(dict(id=f"{rid}-node-{i}", region=rid, kind=kind, x=round(x, 1), y=round(y, 1),
                              active=True, respawn_at=0.0, zone=rid))
    return mobs, nodes
