from __future__ import annotations

import asyncio
import json
import math
import random
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "echo_saves.sqlite3"
WORLD_W, WORLD_H = 4800, 3200
TICK = 0.05
MAX_PLAYERS = 8

ZONES = [
    {"id": "camp", "name": "Лагерь Следопытов", "x0": 0, "x1": 800, "level": "Безопасная зона", "danger": 0},
    {"id": "forest", "name": "Шепчущий лес", "x0": 800, "x1": 1600, "level": "Уровень 1–3", "danger": 1},
    {"id": "marsh", "name": "Затонувшие топи", "x0": 1600, "x1": 2400, "level": "Уровень 4–6", "danger": 2},
    {"id": "ruins", "name": "Пепельные руины", "x0": 2400, "x1": 3200, "level": "Уровень 7–10", "danger": 3},
    {"id": "glacier", "name": "Хребет Синего Пламени", "x0": 3200, "x1": 4000, "level": "Уровень 11–14", "danger": 4},
    {"id": "rift", "name": "Разлом Эха", "x0": 4000, "x1": 4800, "level": "Уровень 15–20", "danger": 5},
]

WEAPONS = {
    "sword": {"name": "Меч дозорного", "kind": "melee", "damage": 18, "bonus": 22, "charge": .62, "stamina": 13, "range": 82, "arc": .28, "cooldown": .30, "color": "#f2d17d"},
    "axe": {"name": "Лесной колун", "kind": "melee", "damage": 22, "bonus": 28, "charge": .82, "stamina": 19, "range": 88, "arc": .12, "cooldown": .48, "color": "#d9a66d"},
    "bow": {"name": "Тисовый лук", "kind": "bow", "damage": 14, "bonus": 28, "charge": .90, "stamina": 10, "cooldown": .18, "color": "#a8d982"},
    "iron_sword": {"name": "Клинок из болотной стали", "kind": "melee", "damage": 27, "bonus": 33, "charge": .66, "stamina": 15, "range": 90, "arc": .30, "cooldown": .31, "color": "#b8d8df", "rarity": "rare"},
    "moonblade": {"name": "Лунный резец", "kind": "melee", "damage": 31, "bonus": 39, "charge": .58, "stamina": 16, "range": 96, "arc": .34, "cooldown": .27, "color": "#b9e9d8", "rarity": "epic"},
    "ember_greatsword": {"name": "Клинок последнего зарева", "kind": "melee", "damage": 43, "bonus": 52, "charge": .78, "stamina": 22, "range": 108, "arc": .22, "cooldown": .44, "color": "#ff9b59", "rarity": "legendary"},
    "starfall_bow": {"name": "Лук звёздного падения", "kind": "bow", "damage": 25, "bonus": 47, "charge": .82, "stamina": 12, "cooldown": .15, "color": "#a8e6db", "rarity": "epic"},
    "frostfang": {"name": "Клык Ледяного змея", "kind": "melee", "damage": 47, "bonus": 58, "charge": .63, "stamina": 20, "range": 106, "arc": .28, "cooldown": .32, "color": "#a9f5ff", "rarity": "legendary"},
    "void_edge": {"name": "Рассекающий разлом", "kind": "melee", "damage": 62, "bonus": 76, "charge": .72, "stamina": 24, "range": 122, "arc": .24, "cooldown": .40, "color": "#d99aff", "rarity": "legendary"},
}
GEAR = {
    "traveler": {"name": "Куртка путника", "defense": 2, "color": "#547c50", "rarity": "common", "lore": "Простая одежда для долгой дороги."},
    "wolf_cloak": {"name": "Плащ туманного волка", "defense": 5, "color": "#778d8d", "rarity": "uncommon", "lore": "Шерсть гасит звук шагов."},
    "moss_guard": {"name": "Живой моховой панцирь", "defense": 6, "color": "#8bb56b", "rarity": "uncommon", "lore": "Мох впитывает часть удара."},
    "marsh_armor": {"name": "Болотная броня", "defense": 8, "color": "#9c815e", "rarity": "rare", "lore": "Креплёная кожа и пластины из топкой руды."},
    "moonweave": {"name": "Мантия лунного ткача", "defense": 9, "color": "#9bc8bd", "rarity": "epic", "lore": "Нити мерцают в сумерках затонувших топей."},
    "ash_plate": {"name": "Пепельный панцирь", "defense": 12, "color": "#a8aaa4", "rarity": "epic", "lore": "Тяжёлые пластины стражей руин."},
    "colossus_core": {"name": "Сердце Колосса", "defense": 18, "color": "#f49a60", "rarity": "legendary", "lore": "Остывшая броня всё ещё хранит жар древнего титана."},
    "glacier_mantle": {"name": "Мантия Синего Пламени", "defense": 21, "color": "#8ee8f2", "rarity": "legendary", "lore": "Ледяные пластины звенят, будто далёкие колокола."},
    "rift_plate": {"name": "Доспех Пустого Эха", "defense": 27, "color": "#bd85ed", "rarity": "legendary", "lore": "Собран из осколков, переживших разлом между мирами."},
}
MONSTERS = {
    "slime": {"name": "Моховой слизень", "hp": 48, "speed": 42, "damage": 7, "range": 36, "cooldown": 1.35, "xp": 20, "color": "#8fce73", "zone": 1},
    "wolf": {"name": "Туманный волк", "hp": 70, "speed": 72, "damage": 12, "range": 40, "cooldown": 1.15, "xp": 34, "color": "#b7c7b5", "zone": 1},
    "boar": {"name": "Топкий вепрь", "hp": 125, "speed": 48, "damage": 18, "range": 48, "cooldown": 1.65, "xp": 56, "color": "#a7805b", "zone": 2},
    "wisp": {"name": "Болотный огонёк", "hp": 88, "speed": 58, "damage": 15, "range": 52, "cooldown": 1.45, "xp": 62, "color": "#7bd8cf", "zone": 2},
    "stone": {"name": "Каменный дозорный", "hp": 215, "speed": 29, "damage": 25, "range": 58, "cooldown": 2.0, "xp": 105, "color": "#b39c7b", "zone": 2},
    "ashling": {"name": "Пепельный искатель", "hp": 165, "speed": 55, "damage": 23, "range": 46, "cooldown": 1.3, "xp": 110, "color": "#d38e67", "zone": 3},
    "ashguard": {"name": "Страж руин", "hp": 330, "speed": 34, "damage": 34, "range": 66, "cooldown": 2.15, "xp": 190, "color": "#c6ad86", "zone": 3},
    "colossus": {"name": "Пепельный колосс", "hp": 920, "speed": 22, "damage": 48, "range": 94, "cooldown": 2.6, "xp": 700, "color": "#e2a26c", "zone": 3},
    "frost_wyrm": {"name": "Ледяной змей", "hp": 560, "speed": 59, "damage": 38, "range": 76, "cooldown": 1.65, "xp": 410, "color": "#8ee8f2", "zone": 4},
    "rift_knight": {"name": "Рыцарь разлома", "hp": 760, "speed": 45, "damage": 52, "range": 82, "cooldown": 1.9, "xp": 580, "color": "#bd85ed", "zone": 5},
    "echo_dragon": {"name": "Дракон Пустого Эха", "hp": 2600, "speed": 31, "damage": 74, "range": 126, "cooldown": 2.45, "xp": 2400, "color": "#ff637e", "zone": 5},
    "thorn_stalker": {"name": "Терновый охотник", "hp": 105, "speed": 68, "damage": 17, "range": 42, "cooldown": 1.2, "xp": 58, "color": "#9fc66e", "zone": 1},
    "bog_mother": {"name": "Матерь топи", "hp": 1450, "speed": 25, "damage": 43, "range": 104, "cooldown": 2.2, "xp": 900, "color": "#76c7a0", "zone": 2},
    "echo_wraith": {"name": "Зеркальный призрак", "hp": 690, "speed": 77, "damage": 49, "range": 64, "cooldown": 1.35, "xp": 520, "color": "#b8a0ff", "zone": 5},
    "void_titan": {"name": "Титан Междумирья", "hp": 3200, "speed": 27, "damage": 82, "range": 138, "cooldown": 2.5, "xp": 3000, "color": "#ef8acb", "zone": 5},
}


SHOP_BUYS = {
    "potion": {"name": "Настойка восстановления", "price": 35, "kind": "resource", "item": "potion", "amount": 1},
    "arrows": {"name": "Колчан стрел · 12 шт.", "price": 24, "kind": "resource", "item": "arrows", "amount": 12},
    "wood": {"name": "Сухая древесина · 3 шт.", "price": 18, "kind": "resource", "item": "wood", "amount": 3},
    "crystal": {"name": "Эхо-кристалл", "price": 70, "kind": "resource", "item": "crystal", "amount": 1},
}
SELL_PRICES = {"wood": 3, "herb": 4, "ore": 7, "hide": 6, "slime": 3,
               "crystal": 18, "shard": 28, "potion": 12, "arrows": 1}
ENCHANTS = {
    "sharpness": {"name": "Острота", "max": 5, "base_gold": 45, "crystals": 1, "target": "weapon"},
    "slayer": {"name": "Поборник боссов", "max": 3, "base_gold": 70, "crystals": 2, "target": "weapon"},
    "vampirism": {"name": "Похищение жизни", "max": 3, "base_gold": 85, "crystals": 2, "target": "weapon"},
    "protection": {"name": "Защита", "max": 4, "base_gold": 45, "crystals": 1, "target": "gear"},
}
PORTALS = [
    {"id": "camp_mirror", "x": 600, "y": 1100, "name": "Зеркальный круг", "from": "waking", "to": "echo"},
    {"id": "rift_mirror", "x": 4180, "y": 1110, "name": "Разлом отражений", "from": "waking", "to": "echo"},
]

app = FastAPI(title="Лес Эхо: Пробуждение")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
players: dict[str, dict[str, Any]] = {}
clients: dict[str, WebSocket] = {}
mobs: list[dict[str, Any]] = []
nodes: list[dict[str, Any]] = []
arrows: list[dict[str, Any]] = []


def safe_name(value: Any) -> str:
    return " ".join(str(value).strip().split())[:18] or "Путник"


def zone_for_x(x: float) -> dict[str, Any]:
    for zone in ZONES:
        if zone["x0"] <= x < zone["x1"]:
            return zone
    return ZONES[-1]


def scaled_mob(kind: str, level: int, index: int, x: float, y: float) -> dict[str, Any]:
    spec = MONSTERS[kind]
    scale = 1 + max(0, level - spec["zone"]) * .16
    return {"id": f"{kind}-{index}", "kind": kind, "level": level,
            "x": float(x), "y": float(y), "spawn_x": float(x), "spawn_y": float(y),
            "hp": round(spec["hp"] * scale), "max_hp": round(spec["hp"] * scale),
            "speed": spec["speed"] * (1 + max(0, level - spec["zone"]) * .035),
            "wander_x": random.uniform(-1, 1), "wander_y": random.uniform(-1, 1),
            "wander_at": time.monotonic() + random.uniform(.5, 3), "attack_at": 0.0,
            "respawn_at": 0.0, "telegraph_until": 0.0, "alert_until": 0.0,
            "boss": kind in {"colossus", "bog_mother", "void_titan"}, "dimension": "waking"}


def grant_gear(p: dict[str, Any], gear_id: str) -> bool:
    if gear_id not in GEAR:
        return False
    if gear_id == p.get("gear") or gear_id in p.get("gear_inventory", []):
        p["gold"] += 18
        p.setdefault("inventory", {})["crystal"] = p.get("inventory", {}).get("crystal", 0) + 1
        try:
            asyncio.create_task(send_event({"type": "notice", "target": p["id"], "text": "Дубликат превращён в 18 монет и эхо-кристалл."}))
        except RuntimeError:
            pass
        return False
    p.setdefault("gear_inventory", []).append(gear_id)
    return True


def grant_weapon(p: dict[str, Any], weapon_id: str) -> bool:
    if weapon_id not in WEAPONS:
        return False
    if weapon_id in p.get("weapons", []):
        p["gold"] += 24
        p.setdefault("inventory", {})["crystal"] = p.get("inventory", {}).get("crystal", 0) + 2
        try:
            asyncio.create_task(send_event({"type": "notice", "target": p["id"], "text": "Дубликат оружия разобран: +24 монеты и 2 эхо-кристалла."}))
        except RuntimeError:
            pass
        return False
    p.setdefault("weapons", []).append(weapon_id)
    try:
        asyncio.create_task(send_event({"type": "notice", "target": p["id"], "text": f"Найдено оружие: {WEAPONS[weapon_id]['name']}!"}))
    except RuntimeError:
        pass
    return True


def init_world() -> None:
    if mobs:
        return
    random.seed(241)
    idx = 0
    population = {
        "forest": [("slime", 8, 1), ("wolf", 5, 2), ("thorn_stalker", 4, 2)],
        "marsh": [("boar", 6, 4), ("wisp", 5, 5), ("stone", 2, 6), ("bog_mother", 1, 8)],
        "ruins": [("ashling", 6, 7), ("ashguard", 4, 8), ("colossus", 1, 10)],
        "glacier": [("frost_wyrm", 7, 11), ("frost_wyrm", 4, 13)],
        "rift": [("rift_knight", 7, 15), ("echo_dragon", 1, 20)],
    }
    for zone_id, packs in population.items():
        zone = next(z for z in ZONES if z["id"] == zone_id)
        for kind, count, level in packs:
            for _ in range(count):
                idx += 1
                x = random.uniform(zone["x0"] + 90, zone["x1"] - 90)
                y = random.uniform(130, WORLD_H - 130)
                mobs.append(scaled_mob(kind, level + random.choice([0, 0, 1]), idx, x, y))
    for i in range(105):
        x = random.uniform(100, WORLD_W - 100)
        zone = zone_for_x(x)
        roll = random.random()
        if zone["id"] == "camp":
            kind = "herb" if roll < .6 else "wood"
        elif zone["id"] == "forest":
            kind = "wood" if roll < .42 else "herb" if roll < .78 else "ore"
        elif zone["id"] == "marsh":
            kind = "herb" if roll < .25 else "ore" if roll < .78 else "crystal"
        else:
            kind = "ore" if roll < .45 else "crystal" if roll < .88 else "wood"
        nodes.append({"id": f"node-{i}", "kind": kind, "x": x,
                      "y": random.uniform(100, WORLD_H - 100), "active": True,
                      "respawn_at": 0.0, "zone": zone["id"]})
    random.seed()


init_world()
# A mirrored layer uses the same map coordinates but a separate population and player instance.
for _kind, _level, _idx, _x, _y in [
    ("echo_wraith", 16, 901, 620, 1600), ("echo_wraith", 17, 902, 910, 1980),
    ("rift_knight", 16, 903, 1320, 1280), ("void_titan", 22, 904, 1580, 1700),
    ("echo_wraith", 18, 905, 4250, 1850),
]:
    _mob = scaled_mob(_kind, _level, _idx, _x, _y)
    _mob["dimension"] = "echo"
    mobs.append(_mob)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


def quest_data(p: dict[str, Any]) -> dict[str, Any]:
    return {"stage": p["quest_stage"], "active": p["quest_active"],
            "kills": dict(p["quest_kills"]), "gather": dict(p["quest_gather"])}


def player_row(pid: str, p: dict[str, Any], now: float) -> dict[str, Any]:
    action = None
    if p["attack"]:
        a = p["attack"]
        spec = WEAPONS[a["weapon"]]
        action = {"weapon": a["weapon"], "kind": spec["kind"],
                  "charge": min(1.0, max(0.0, (now - a["started"]) / spec["charge"])),
                  "aim_x": a["aim_x"], "aim_y": a["aim_y"]}
    zone = zone_for_x(p["x"])
    return {"id": pid, "name": p["name"], "x": round(p["x"], 1), "y": round(p["y"], 1),
            "dimension": p.get("dimension", "waking"), "enchantments": p.get("enchantments", {"weapon": {}, "gear": {}}),
            "face_x": p["face_x"], "face_y": p["face_y"], "hp": p["hp"], "max_hp": p["max_hp"],
            "stamina": round(p["stamina"], 1), "max_stamina": p["max_stamina"], "xp": p["xp"],
            "level": p["level"], "skill_points": p["skill_points"], "stats": dict(p["stats"]),
            "gold": p["gold"], "kills": p["kills"], "quest": quest_data(p),
            "respawning": p["respawn_at"] > now, "weapons": list(p["weapons"]), "weapon": p["weapon"],
            "gear": p["gear"], "gear_inventory": list(p["gear_inventory"]),
            "gear_catalog": GEAR,
            "weapon_catalog": {key: {"name": value["name"], "rarity": value.get("rarity", "common"),
                                     "damage": value["damage"], "kind": value["kind"]}
                               for key, value in WEAPONS.items()},
            "inventory": dict(p["inventory"]), "attack": action,
            "gathering": p["gathering"] is not None, "gather_progress": (p["gathering"]["progress"] / 1.15 if p["gathering"] else 0), "zone": zone["id"],
            "dodge_ready": now >= p["dodge_at"]}


def snapshot(for_id: str) -> dict[str, Any]:
    now = time.monotonic()
    dimension = players.get(for_id, {}).get("dimension", "waking")
    return {"type": "state", "you": for_id, "world": {"w": WORLD_W, "h": WORLD_H},
            "dimension": dimension, "portals": PORTALS, "zones": ZONES,
            "players": [player_row(pid, p, now) for pid, p in players.items()
                        if p.get("dimension", "waking") == dimension],
            "mobs": [{**{k: mob[k] for k in ("id", "kind", "level", "x", "y", "hp", "max_hp", "boss")},
                      "telegraphing": mob["telegraph_until"] > now}
                     for mob in mobs if mob["hp"] > 0 and mob.get("dimension", "waking") == dimension],
            "nodes": [{k: n[k] for k in ("id", "kind", "x", "y", "active", "zone")} for n in nodes],
            "arrows": [{k: a[k] for k in ("x", "y", "vx", "vy", "life", "kind")} for a in arrows
                       if a.get("dimension", "waking") == dimension]}


async def send_event(event: dict[str, Any]) -> None:
    payload = json.dumps(event, ensure_ascii=False)
    for pid, socket in list(clients.items()):
        try:
            await socket.send_text(payload)
        except Exception:
            clients.pop(pid, None)
            players.pop(pid, None)


async def tell(pid: str, text: str) -> None:
    await send_event({"type": "notice", "target": pid, "text": text})


def update_derived(p: dict[str, Any], heal: bool = False) -> None:
    old_hp = p["max_hp"]
    old_stamina = p["max_stamina"]
    p["max_hp"] = 100 + (p["level"] - 1) * 7 + (p["stats"]["vitality"] - 1) * 12
    p["max_stamina"] = 100 + (p["stats"]["agility"] - 1) * 5 + (p["stats"]["might"] - 1) * 2
    if heal:
        p["hp"] = p["max_hp"]
        p["stamina"] = p["max_stamina"]
    else:
        p["hp"] = min(p["hp"] + max(0, p["max_hp"] - old_hp), p["max_hp"])
        p["stamina"] = min(p["stamina"] + max(0, p["max_stamina"] - old_stamina), p["max_stamina"])


def add_xp(p: dict[str, Any], amount: int) -> None:
    p["xp"] += amount
    changed = False
    while p["xp"] >= p["level"] * 120:
        p["xp"] -= p["level"] * 120
        p["level"] += 1
        p["skill_points"] += 1
        update_derived(p)
        p["hp"] = min(p["max_hp"], p["hp"] + 24)
        changed = True
    if changed:
        asyncio.create_task(send_event({"type": "notice", "text": f"{p['name']} достиг(ла) {p['level']} уровня — доступно очко развития"}))


def quest_requirements(stage: int) -> tuple[str, int, str, int, str]:
    return [
        ("slime", 4, "herb", 3, "Очистить опушку"),
        ("wolf", 3, "ore", 4, "Следы в топи"),
        ("boar", 3, "crystal", 3, "Свет под водой"),
        ("colossus", 1, "", 0, "Пепельный колосс"),
        ("frost_wyrm", 4, "crystal", 6, "Синий хребет"),
        ("echo_dragon", 1, "shard", 8, "Разлом Эха"),
    ][min(stage, 5)]


def quest_complete(p: dict[str, Any]) -> bool:
    mob, mob_n, resource, resource_n, _ = quest_requirements(p["quest_stage"])
    return p["quest_kills"].get(mob, 0) >= mob_n and (not resource or p["quest_gather"].get(resource, 0) >= resource_n)


def near_keeper(p: dict[str, Any]) -> bool:
    return math.hypot(p["x"] - 330, p["y"] - 1100) < 105


async def interact_keeper(p: dict[str, Any]) -> None:
    if not near_keeper(p):
        await tell(p["id"], "Хранитель ждёт в лагере Следопытов, на западе карты.")
        return
    if p["quest_active"] and quest_complete(p):
        stage = p["quest_stage"]
        p["quest_active"] = False
        p["quest_stage"] += 1
        gold = [45, 90, 145, 260][stage]
        xp = [100, 220, 360, 700][stage]
        p["gold"] += gold
        add_xp(p, xp)
        if stage == 0:
            p["inventory"]["potion"] += 2
        elif stage == 1:
            grant_gear(p, "wolf_cloak")
        elif stage == 2:
            grant_gear(p, "marsh_armor")
        else:
            grant_gear(p, "ash_plate")
        await tell(p["id"], f"Поручение завершено. Получено {gold} монет, {xp} опыта и награда следопыту.")
    elif p["quest_active"]:
        await tell(p["id"], "Поручение ещё не выполнено. Загляни в журнал.")
    elif p["quest_stage"] >= 4:
        await tell(p["id"], "Ты прошёл путь до Пепельного колосса. Но даже легендам нужен отдых.")
    else:
        p["quest_active"] = True
        p["quest_kills"] = {}
        p["quest_gather"] = {}
        _, _, _, _, title = quest_requirements(p["quest_stage"])
        await tell(p["id"], f"Новое поручение: {title}. Цели отмечены в журнале.")


def award_drop(p: dict[str, Any], mob: dict[str, Any]) -> None:
    kind = mob["kind"]
    inv = p["inventory"]
    p["kills"] += 1
    add_xp(p, MONSTERS[kind]["xp"] + max(0, mob["level"] - MONSTERS[kind]["zone"]) * 7)
    p["gold"] += random.randint(4, 11) + mob["level"]
    if p["quest_active"]:
        p["quest_kills"][kind] = p["quest_kills"].get(kind, 0) + 1
    if kind == "thorn_stalker":
        inv["hide"] += 1; inv["wood"] += 1
        if random.random() < .22: inv["herb"] += 2
    elif kind == "bog_mother":
        inv["crystal"] += 8; inv["shard"] += 5; inv["herb"] += 8
        if random.random() < .7: grant_gear(p, "moonweave")
    elif kind == "echo_wraith":
        inv["shard"] += random.randint(2, 4); inv["crystal"] += 2
        if random.random() < .08: grant_weapon(p, "void_edge")
    elif kind == "void_titan":
        inv["crystal"] += 24; inv["shard"] += 20
        grant_gear(p, "rift_plate"); grant_weapon(p, "void_edge")
    elif kind == "slime":
        inv["slime"] += 1
        if random.random() < .45: inv["herb"] += 1
    elif kind == "wolf":
        inv["hide"] += random.randint(1, 2)
        if random.random() < .12: grant_gear(p, random.choice(["wolf_cloak", "moss_guard"]))
        if random.random() < .025: grant_weapon(p, "moonblade")
    elif kind == "boar":
        inv["hide"] += 2; inv["ore"] += 1
    elif kind == "wisp":
        inv["crystal"] += random.randint(1, 2); inv["herb"] += 1
    elif kind == "stone":
        inv["ore"] += random.randint(2, 4)
        if random.random() < .18: grant_gear(p, random.choice(["marsh_armor", "moonweave"]))
        if random.random() < .035: grant_weapon(p, random.choice(["moonblade", "starfall_bow"]))
    elif kind == "ashling":
        inv["crystal"] += random.randint(1, 2); inv["ore"] += 1
        if random.random() < .18: inv["shard"] += 1
    elif kind == "ashguard":
        inv["crystal"] += 3; inv["ore"] += 3; inv["shard"] += random.randint(1, 2)
        if random.random() < .35: grant_gear(p, random.choice(["ash_plate", "colossus_core"]))
        if random.random() < .08: grant_weapon(p, random.choice(["ember_greatsword", "starfall_bow"]))
    elif kind == "colossus":
        inv["crystal"] += 12; inv["ore"] += 10; inv["shard"] += 10
        grant_gear(p, "colossus_core")
        grant_weapon(p, "ember_greatsword")
    elif kind == "frost_wyrm":
        inv["crystal"] += 4; inv["shard"] += random.randint(2, 4)
        if random.random() < .12: grant_gear(p, "glacier_mantle")
        if random.random() < .045: grant_weapon(p, "frostfang")
    elif kind == "rift_knight":
        inv["crystal"] += 6; inv["shard"] += random.randint(3, 5)
        if random.random() < .20: grant_gear(p, "rift_plate")
        if random.random() < .06: grant_weapon(p, "void_edge")
    elif kind == "echo_dragon":
        inv["crystal"] += 30; inv["shard"] += 24
        grant_gear(p, "rift_plate")
        grant_weapon(p, "void_edge")
    asyncio.create_task(send_event({"type": "notice", "target": p["id"], "text": f"Победа над {MONSTERS[kind]['name']}: добыча собрана."}))


def attack_release(p: dict[str, Any], now: float, ax: float, ay: float) -> None:
    attack = p.get("attack")
    if not attack:
        return
    weapon_id = attack["weapon"]
    spec = WEAPONS[weapon_id]
    elapsed = now - attack["started"]
    charge = min(1.0, max(0.0, elapsed / spec["charge"]))
    p["attack"] = None
    p["last_attack"] = now
    length = math.hypot(ax, ay)
    if length > .01:
        ax, ay = ax / length, ay / length
        p["face_x"], p["face_y"] = ax, ay
    else:
        ax, ay = p["face_x"], p["face_y"]
    if elapsed < .14:
        return
    cost = spec["stamina"] * (.62 + .38 * charge)
    if p["stamina"] < cost:
        asyncio.create_task(tell(p["id"], "Слишком мало выносливости — отступи на мгновение."))
        return
    p["stamina"] -= cost
    power_bonus = (p["stats"]["might"] - 1) * 2.2
    weapon_enchants = p.get("enchantments", {}).get("weapon", {}).get(weapon_id, {})
    damage = spec["damage"] + spec["bonus"] * charge + power_bonus + int(weapon_enchants.get("sharpness", 0)) * 2.4
    if spec["kind"] == "bow":
        if p["inventory"]["arrows"] <= 0:
            asyncio.create_task(tell(p["id"], "Колчан пуст. Стрелы можно изготовить из дерева и руды."))
            return
        p["inventory"]["arrows"] -= 1
        speed = 390 + 240 * charge + (p["stats"]["agility"] - 1) * 8
        arrows.append({"x": p["x"] + ax * 18, "y": p["y"] + ay * 18,
                       "vx": ax * speed, "vy": ay * speed, "damage": damage,
                       "owner": p["id"], "life": 1.45, "kind": "arrow", "dimension": p.get("dimension", "waking")})
        return
    reach = spec["range"] + 12 * charge
    hits = []
    for mob in mobs:
        if mob["hp"] <= 0 or mob.get("dimension", "waking") != p.get("dimension", "waking"): continue
        dx, dy = mob["x"] - p["x"], mob["y"] - p["y"]
        dist = math.hypot(dx, dy)
        if dist <= reach and dist > .01 and (dx * ax + dy * ay) / dist >= spec["arc"]:
            hits.append((dist, mob))
    hits.sort(key=lambda row: row[0])
    max_hits = 3 if weapon_id == "axe" else 2 if weapon_id == "iron_sword" else 1
    for _, mob in hits[:max_hits]:
        dealt = damage + (int(weapon_enchants.get("slayer", 0)) * 6 if mob.get("boss") else 0)
        mob["hp"] -= dealt
        mob["alert_until"] = now + 4
        vamp = int(weapon_enchants.get("vampirism", 0))
        if vamp:
            p["hp"] = min(p["max_hp"], p["hp"] + max(1, round(dealt * .025 * vamp)))
        if mob["hp"] <= 0:
            mob["hp"] = 0
            mob["respawn_at"] = now + random.uniform(24, 40)
            award_drop(p, mob)
        asyncio.create_task(send_event({"type": "hit", "mob": mob["id"], "x": mob["x"], "y": mob["y"], "damage": round(dealt)}))
    # Player-versus-player combat is enabled outside the safe camp.
    if zone_for_x(p["x"])["danger"] > 0:
        candidates = []
        for other in players.values():
            if other["id"] == p["id"] or other["respawn_at"] > now or other.get("dimension", "waking") != p.get("dimension", "waking"):
                continue
            if zone_for_x(other["x"])["danger"] == 0:
                continue
            dx, dy = other["x"] - p["x"], other["y"] - p["y"]
            dist = math.hypot(dx, dy)
            if dist <= reach + 10 and dist > .01 and (dx * ax + dy * ay) / dist >= spec["arc"]:
                candidates.append((dist, other))
        candidates.sort(key=lambda row: row[0])
        for _, other in candidates[:max_hits]:
            defense = GEAR.get(other.get("gear"), GEAR["traveler"])["defense"] + int(other.get("enchantments", {}).get("gear", {}).get(other.get("gear"), {}).get("protection", 0)) * 2
            actual = max(1, round(damage * .72) - defense)
            other["hp"] = max(0, other["hp"] - actual)
            asyncio.create_task(send_event({"type": "pvp_hit", "attacker": p["id"], "id": other["id"],
                                            "damage": actual, "x": other["x"], "y": other["y"]}))
            if other["hp"] <= 0:
                other["respawn_at"] = now + 5
                other["attack"] = None
                other["gathering"] = None
                asyncio.create_task(tell(other["id"], f"Ты пал в дуэли с {p['name']}. Через несколько секунд вернёшься в лагерь."))
                asyncio.create_task(tell(p["id"], f"Победа в дуэли над {other['name']}!"))


def start_attack(p: dict[str, Any], now: float, ax: float, ay: float) -> None:
    if p["attack"] or p["respawn_at"] > now or now - p["last_attack"] < WEAPONS[p["weapon"]]["cooldown"]:
        return
    if p["stamina"] < 5: return
    if math.hypot(ax, ay) > .01:
        length = math.hypot(ax, ay)
        p["face_x"], p["face_y"] = ax / length, ay / length
    p["gathering"] = None
    p["attack"] = {"weapon": p["weapon"], "started": now,
                    "aim_x": p["face_x"], "aim_y": p["face_y"]}


def start_gather(p: dict[str, Any], now: float) -> None:
    if p["gathering"] is not None or p["attack"] or p["respawn_at"] > now:
        return
    nearest = min((n for n in nodes if n["active"] and math.hypot(n["x"] - p["x"], n["y"] - p["y"]) < 64),
                  key=lambda n: math.hypot(n["x"] - p["x"], n["y"] - p["y"]), default=None)
    if nearest:
        p["gathering"] = {"node": nearest["id"], "started": now, "progress": 0.0}


def do_craft(p: dict[str, Any], recipe: str) -> str:
    inv = p["inventory"]
    if recipe == "arrows" and inv["wood"] >= 2 and inv["ore"] >= 1:
        inv["wood"] -= 2; inv["ore"] -= 1; inv["arrows"] += 8
        return "Изготовлено 8 стрел."
    if recipe == "potion" and inv["herb"] >= 3 and inv["slime"] >= 1:
        inv["herb"] -= 3; inv["slime"] -= 1; inv["potion"] += 1
        return "Сварена настойка восстановления."
    if recipe == "iron_sword" and inv["ore"] >= 6 and inv["wood"] >= 4 and "iron_sword" not in p["weapons"]:
        inv["ore"] -= 6; inv["wood"] -= 4; p["weapons"].append("iron_sword")
        return "Скован болотностальной клинок."
    if recipe == "armor" and inv["hide"] >= 4 and inv["ore"] >= 3 and "marsh_armor" not in p["gear_inventory"] and p["gear"] != "marsh_armor":
        inv["hide"] -= 4; inv["ore"] -= 3; grant_gear(p, "marsh_armor")
        return "Собрана болотная броня. Открой инвентарь, чтобы надеть её."
    return "Не хватает материалов или предмет уже изготовлен."


def near_shop(p: dict[str, Any]) -> bool:
    return p.get("dimension", "waking") == "waking" and math.hypot(p["x"] - 330, p["y"] - 1100) <= 145


async def shop_action(pid: str, p: dict[str, Any], msg: dict[str, Any]) -> None:
    if not near_shop(p):
        await tell(pid, "Торговец и мастер чар ждут у костра в Лагере Следопытов.")
        return
    action = str(msg.get("action", ""))
    if action == "buy":
        offer = SHOP_BUYS.get(str(msg.get("id", "")))
        if not offer:
            await tell(pid, "Такого товара нет в лавке."); return
        if p["gold"] < offer["price"]:
            await tell(pid, f"Не хватает монет: нужно {offer['price']}."); return
        p["gold"] -= offer["price"]
        p["inventory"][offer["item"]] = p["inventory"].get(offer["item"], 0) + offer["amount"]
        await tell(pid, f"Куплено: {offer['name']}.")
        return
    if action == "sell":
        item_id = str(msg.get("id", "")); category = str(msg.get("category", ""))
        try:
            amount = max(1, min(99, int(msg.get("amount", 1))))
        except (TypeError, ValueError):
            amount = 1
        if category == "resource" and item_id in SELL_PRICES:
            owned = int(p["inventory"].get(item_id, 0)); sold = min(owned, amount)
            if sold <= 0:
                await tell(pid, "Такого предмета больше нет в сумке."); return
            p["inventory"][item_id] -= sold
            earned = sold * SELL_PRICES[item_id]
        elif category == "weapon" and item_id in p["weapons"] and item_id in WEAPONS:
            if item_id == p["weapon"]:
                await tell(pid, "Сначала выбери другое оружие."); return
            if len(p["weapons"]) <= 1:
                await tell(pid, "Оставь себе хотя бы одно оружие."); return
            p["weapons"].remove(item_id)
            p.get("enchantments", {}).get("weapon", {}).pop(item_id, None)
            earned = 45 + WEAPONS[item_id]["damage"] * 2
        elif category == "gear" and item_id in p.get("gear_inventory", []) and item_id in GEAR:
            p["gear_inventory"].remove(item_id)
            p.get("enchantments", {}).get("gear", {}).pop(item_id, None)
            earned = 35 + GEAR[item_id]["defense"] * 5
        else:
            await tell(pid, "Продать можно только предметы из рюкзака; надетое снаряжение защищено от продажи."); return
        p["gold"] += earned
        await tell(pid, f"Продано. Получено {earned} монет.")
        return
    if action == "enchant":
        category = str(msg.get("category", "")); item_id = str(msg.get("id", ""))
        enchant_id = str(msg.get("enchant", "")); spec = ENCHANTS.get(enchant_id)
        owned = (item_id in p.get("weapons", []) and item_id in WEAPONS) if category == "weapon" else (
            item_id in ([p.get("gear")] + p.get("gear_inventory", [])) and item_id in GEAR)
        if not spec or spec["target"] != category or not owned:
            await tell(pid, "Этот предмет нельзя зачаровать выбранной руной."); return
        levels = p.setdefault("enchantments", {"weapon": {}, "gear": {}}).setdefault(category, {}).setdefault(item_id, {})
        current = int(levels.get(enchant_id, 0))
        if current >= spec["max"]:
            await tell(pid, "Зачарование уже достигло максимального уровня."); return
        next_level = current + 1
        gold_cost = spec["base_gold"] * next_level
        crystal_cost = spec["crystals"] * next_level
        if p["gold"] < gold_cost or p["inventory"].get("crystal", 0) < crystal_cost:
            await tell(pid, f"Нужно {gold_cost} монет и {crystal_cost} эхо-кристалл(ов)."); return
        p["gold"] -= gold_cost
        p["inventory"]["crystal"] -= crystal_cost
        levels[enchant_id] = next_level
        await tell(pid, f"Зачарование «{spec['name']}» повышено до {next_level} уровня.")
        return
    await tell(pid, "Неизвестная операция лавки.")


async def handle_message(pid: str, p: dict[str, Any], msg: dict[str, Any], now: float) -> None:
    kind = msg.get("type")
    if kind == "input":
        try:
            mx = max(-1.0, min(1.0, float(msg.get("x", 0))))
            my = max(-1.0, min(1.0, float(msg.get("y", 0))))
            ax = max(-1.0, min(1.0, float(msg.get("aim_x", 0))))
            ay = max(-1.0, min(1.0, float(msg.get("aim_y", 0))))
        except (TypeError, ValueError):
            mx = my = 0.0; ax, ay = p["face_x"], p["face_y"]
        length = math.hypot(mx, my)
        if length > 1: mx, my = mx / length, my / length
        p["mx"], p["my"] = mx, my
        if math.hypot(ax, ay) > .01:
            length = math.hypot(ax, ay)
            p["face_x"], p["face_y"] = ax / length, ay / length
            if p["attack"]: p["attack"]["aim_x"], p["attack"]["aim_y"] = p["face_x"], p["face_y"]
    elif kind == "attack_start":
        try: start_attack(p, now, float(msg.get("aim_x", 0)), float(msg.get("aim_y", 0)))
        except (TypeError, ValueError): start_attack(p, now, 0, 0)
    elif kind == "attack_release":
        try: attack_release(p, now, float(msg.get("aim_x", p["face_x"])), float(msg.get("aim_y", p["face_y"])))
        except (TypeError, ValueError): attack_release(p, now, p["face_x"], p["face_y"])
    elif kind == "weapon":
        weapon = str(msg.get("id", ""))
        if weapon in p["weapons"] and weapon in WEAPONS: p["weapon"] = weapon
    elif kind == "gather_start": start_gather(p, now)
    elif kind == "gather_stop": p["gathering"] = None
    elif kind == "interact": await interact_keeper(p)
    elif kind == "shop_open":
        if near_shop(p):
            socket = clients.get(pid)
            if socket:
                await socket.send_text(json.dumps({"type": "market_open", "target": pid,
                                                  "offers": SHOP_BUYS, "sell_prices": SELL_PRICES,
                                                  "enchantments": ENCHANTS}, ensure_ascii=False))
        else:
            await tell(pid, "Лавка находится у костра в Лагере Следопытов.")
    elif kind == "shop": await shop_action(pid, p, msg)
    elif kind == "portal":
        portal = min(PORTALS, key=lambda item: math.hypot(item["x"]-p["x"], item["y"]-p["y"]))
        if math.hypot(portal["x"]-p["x"], portal["y"]-p["y"]) > 90:
            await tell(pid, "Подойди ближе к портальному кругу.")
        else:
            old = p.get("dimension", "waking")
            p["dimension"] = "echo" if old == "waking" else "waking"
            p["mx"] = p["my"] = 0.0
            p["attack"] = None; p["gathering"] = None
            await tell(pid, "Мир перелистнулся: " + ("ты вошёл в Зеркальный Предел." if p["dimension"] == "echo" else "ты вернулся в Явь."))
    elif kind == "craft": await tell(pid, do_craft(p, str(msg.get("recipe", ""))))
    elif kind == "equip_gear":
        gear_id = str(msg.get("id", ""))
        if gear_id not in GEAR:
            await tell(pid, "Такой предмет экипировки не найден.")
        elif gear_id == p.get("gear"):
            await tell(pid, f"Уже надето: {GEAR[gear_id]['name']}.")
        elif gear_id in p["gear_inventory"] and gear_id in GEAR:
            p["gear_inventory"].remove(gear_id)
            if p["gear"] in GEAR and p["gear"] != "traveler":
                p["gear_inventory"].append(p["gear"])
            elif p["gear"] == "traveler":
                # Keep the starter jacket in the collection so it can be re-equipped later.
                p["gear_inventory"].append("traveler")
            p["gear"] = gear_id
            await tell(pid, f"Экипировано: {GEAR[gear_id]['name']} · защита {GEAR[gear_id]['defense']}.")
        else:
            await tell(pid, "Предмет не найден в рюкзаке. Обнови инвентарь и попробуй снова.")
    elif kind == "use_potion":
        if p["inventory"]["potion"] > 0 and p["hp"] < p["max_hp"]:
            p["inventory"]["potion"] -= 1; p["hp"] = min(p["max_hp"], p["hp"] + 48)
            await tell(pid, "Настойка восстановила здоровье.")
    elif kind == "upgrade":
        stat = str(msg.get("stat", ""))
        if stat in p["stats"] and p["skill_points"] > 0:
            p["stats"][stat] += 1; p["skill_points"] -= 1
            update_derived(p, heal=stat == "vitality")
            await tell(pid, f"Развитие улучшено: {stat_names[stat]}.")
    elif kind == "dodge":
        if now >= p["dodge_at"] and p["stamina"] >= 24 and p["respawn_at"] <= now:
            dx, dy = p["mx"], p["my"]
            if math.hypot(dx, dy) < .1: dx, dy = p["face_x"], p["face_y"]
            length = max(.01, math.hypot(dx, dy)); dx /= length; dy /= length
            p["x"] = max(25, min(WORLD_W - 25, p["x"] + dx * 125))
            p["y"] = max(25, min(WORLD_H - 25, p["y"] + dy * 125))
            p["stamina"] -= 24; p["dodge_at"] = now + .85; p["dodge_until"] = now + .18
    elif kind == "chat":
        text = " ".join(str(msg.get("text", "")).split())[:180]
        if text and now - p["last_chat"] > .7:
            p["last_chat"] = now
            await send_event({"type": "chat", "name": p["name"], "text": text})


stat_names = {"might": "Сила", "vitality": "Живучесть", "agility": "Ловкость"}
PERSIST_FIELDS = (
    "x", "y", "hp", "stamina", "xp", "level", "skill_points", "stats",
    "gold", "kills", "weapon", "weapons", "gear", "gear_inventory",
    "inventory", "quest_stage", "quest_active", "quest_kills", "quest_gather", "dimension", "enchantments",
)


def init_database() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS character_saves ("
            "name TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at INTEGER NOT NULL)"
        )


def load_character(name: str) -> dict[str, Any]:
    try:
        with sqlite3.connect(DB_PATH) as connection:
            row = connection.execute(
                "SELECT data FROM character_saves WHERE name = ?", (name.casefold(),)
            ).fetchone()
        if row:
            data = json.loads(row[0])
            return {key: data[key] for key in PERSIST_FIELDS if key in data}
    except (sqlite3.Error, json.JSONDecodeError, TypeError):
        pass
    return {}


def save_character(p: dict[str, Any]) -> None:
    data = {key: p[key] for key in PERSIST_FIELDS}
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            "INSERT INTO character_saves(name, data, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
            (p["name"].casefold(), json.dumps(data, ensure_ascii=False), int(time.time())),
        )


async def world_tick() -> None:
    last_saved = time.monotonic()
    while True:
        now = time.monotonic()
        dt = TICK
        for pid, p in list(players.items()):
            if p["respawn_at"] and p["respawn_at"] <= now:
                p["respawn_at"] = 0.0; p["x"], p["y"] = 330.0, 1100.0
                p["hp"] = p["max_hp"]; p["stamina"] = p["max_stamina"]
                await tell(pid, "Ты вернулся в лагерь. Потеряно немного времени, но не добыча.")
            if p["respawn_at"] > now: continue
            speed = 178 + (p["stats"]["agility"] - 1) * 3.2
            p["x"] = max(25, min(WORLD_W - 25, p["x"] + p["mx"] * speed * dt))
            p["y"] = max(25, min(WORLD_H - 25, p["y"] + p["my"] * speed * dt))
            p["stamina"] = min(p["max_stamina"], p["stamina"] + (15 + p["stats"]["agility"] * .35) * dt)
            if p["gathering"]:
                g = p["gathering"]
                node = next((n for n in nodes if n["id"] == g["node"] and n["active"]), None)
                if not node or math.hypot(node["x"] - p["x"], node["y"] - p["y"]) > 75 or math.hypot(p["mx"], p["my"]) > .1:
                    p["gathering"] = None
                else:
                    g["progress"] += dt
                    if g["progress"] >= 1.15:
                        node["active"] = False; node["respawn_at"] = now + 28
                        amount = random.randint(2, 3)
                        p["inventory"][node["kind"]] += amount
                        if p["quest_active"]: p["quest_gather"][node["kind"]] = p["quest_gather"].get(node["kind"], 0) + amount
                        p["gathering"] = None
                        await tell(pid, f"Собрано: {amount} — {node['kind']}.")
        for node in nodes:
            if not node["active"] and node["respawn_at"] <= now: node["active"] = True
        for mob in mobs:
            if mob["hp"] <= 0:
                if mob["respawn_at"] <= now:
                    realm = mob.get("dimension", "waking")
                    mob.update(scaled_mob(mob["kind"], mob["level"], int(mob["id"].split("-")[-1]), mob["spawn_x"], mob["spawn_y"]))
                    mob["dimension"] = realm
                continue
            target = min((p for p in players.values() if p["respawn_at"] <= now and
                          p.get("dimension", "waking") == mob.get("dimension", "waking") and
                          (zone_for_x(p["x"])["danger"] > 0 or p.get("dimension") == "echo") and
                          (zone_for_x(p["x"])["id"] == zone_for_x(mob["x"])["id"] or
                           p.get("dimension") == "echo")),
                         key=lambda p: math.hypot(p["x"] - mob["x"], p["y"] - mob["y"]), default=None)
            if target is None:
                if now > mob["wander_at"]:
                    mob["wander_x"], mob["wander_y"] = random.uniform(-1, 1), random.uniform(-1, 1)
                    mob["wander_at"] = now + random.uniform(1.2, 3.3)
                mob["x"] += mob["wander_x"] * mob["speed"] * .16 * dt
                mob["y"] += mob["wander_y"] * mob["speed"] * .16 * dt
                continue
            dx, dy = target["x"] - mob["x"], target["y"] - mob["y"]
            dist = math.hypot(dx, dy)
            if dist > 300 and now > mob["wander_at"]:
                mob["wander_x"], mob["wander_y"] = random.uniform(-1, 1), random.uniform(-1, 1)
                mob["wander_at"] = now + 2
            elif dist < 260 and dist > MONSTERS[mob["kind"]]["range"] * .72:
                mob["x"] += dx / max(1, dist) * mob["speed"] * dt
                mob["y"] += dy / max(1, dist) * mob["speed"] * dt
            if dist <= MONSTERS[mob["kind"]]["range"] and mob["attack_at"] <= now:
                if mob["telegraph_until"] <= now:
                    mob["telegraph_until"] = now + .72
                else:
                    if now < target["dodge_until"]:
                        mob["telegraph_until"] = 0.0
                        mob["attack_at"] = now + MONSTERS[mob["kind"]]["cooldown"]
                        continue
                    defense = GEAR.get(target["gear"], GEAR["traveler"])["defense"] + int(target.get("enchantments", {}).get("gear", {}).get(target["gear"], {}).get("protection", 0)) * 2
                    raw_damage = MONSTERS[mob["kind"]]["damage"] + max(0, mob["level"] - MONSTERS[mob["kind"]]["zone"]) * 2
                    actual = max(1, raw_damage - defense)
                    target["hp"] = max(0, target["hp"] - actual)
                    mob["telegraph_until"] = 0.0
                    mob["attack_at"] = now + MONSTERS[mob["kind"]]["cooldown"]
                    await send_event({"type": "hit_player", "id": target["id"], "damage": actual, "mob": mob["kind"]})
                    if target["hp"] <= 0:
                        target["respawn_at"] = now + 5
                        target["attack"] = None; target["gathering"] = None
                        await tell(target["id"], "Ты пал в бою. Через несколько секунд вернёшься в лагерь.")
        for arrow in list(arrows):
            arrow["x"] += arrow["vx"] * dt; arrow["y"] += arrow["vy"] * dt
            arrow["life"] -= dt
            shooter = players.get(arrow.get("owner"))
            player_target = next((p for p in players.values()
                                  if p["id"] != arrow.get("owner") and p["respawn_at"] <= now
                                  and p.get("dimension", "waking") == arrow.get("dimension", "waking")
                                  and zone_for_x(p["x"])["danger"] > 0
                                  and math.hypot(p["x"] - arrow["x"], p["y"] - arrow["y"]) < 28), None)
            if player_target and shooter and zone_for_x(shooter["x"])["danger"] > 0:
                defense = GEAR.get(player_target.get("gear"), GEAR["traveler"])["defense"]
                actual = max(1, round(arrow["damage"] * .72) - defense)
                player_target["hp"] = max(0, player_target["hp"] - actual)
                await send_event({"type": "pvp_hit", "attacker": shooter["id"], "id": player_target["id"],
                                  "damage": actual, "x": player_target["x"], "y": player_target["y"]})
                if player_target["hp"] <= 0:
                    player_target["respawn_at"] = now + 5
                    player_target["attack"] = None
                    player_target["gathering"] = None
                    await tell(player_target["id"], f"Ты пал в дуэли с {shooter['name']}. Через несколько секунд вернёшься в лагерь.")
                    await tell(shooter["id"], f"Победа в дуэли над {player_target['name']}!")
                arrows.remove(arrow)
                continue
            safe_player = next((p for p in players.values() if p["id"] != arrow.get("owner")
                                and zone_for_x(p["x"])["danger"] == 0
                                and math.hypot(p["x"] - arrow["x"], p["y"] - arrow["y"]) < 28), None)
            if safe_player:
                arrows.remove(arrow)
                continue
            target = next((m for m in mobs if m["hp"] > 0 and math.hypot(m["x"] - arrow["x"], m["y"] - arrow["y"]) < (52 if m["boss"] else 30)), None)
            if target:
                target["hp"] -= arrow["damage"]; target["alert_until"] = now + 4
                if target["hp"] <= 0:
                    target["hp"] = 0; target["respawn_at"] = now + random.uniform(24, 40)
                    owner = players.get(arrow["owner"])
                    if owner: award_drop(owner, target)
                asyncio.create_task(send_event({"type": "hit", "mob": target["id"], "x": target["x"], "y": target["y"], "damage": round(arrow["damage"])}))
                arrows.remove(arrow)
            elif arrow["life"] <= 0 or not (0 <= arrow["x"] <= WORLD_W and 0 <= arrow["y"] <= WORLD_H):
                arrows.remove(arrow)
        if now - last_saved >= 10:
            for saved_player in players.values():
                try:
                    save_character(saved_player)
                except sqlite3.Error:
                    pass
            last_saved = now
        if clients:
            for pid, ws in list(clients.items()):
                try: await ws.send_text(json.dumps(snapshot(pid), ensure_ascii=False))
                except Exception: pass
        await asyncio.sleep(TICK)


@app.on_event("startup")
async def startup() -> None:
    init_database()
    app.state.tick_task = asyncio.create_task(world_tick())


@app.on_event("shutdown")
async def shutdown() -> None:
    task = getattr(app.state, "tick_task", None)
    if task: task.cancel()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    if len(players) >= MAX_PLAYERS:
        await websocket.send_text(json.dumps({"type": "error", "message": "Мир полон. Максимум 8 следопытов."}, ensure_ascii=False))
        await websocket.close(code=1008); return
    pid = uuid.uuid4().hex[:8]
    name = safe_name(websocket.query_params.get("name", "Путник"))
    p = {"id": pid, "name": name, "x": 330.0, "y": 1100.0, "mx": 0.0, "my": 0.0,
         "face_x": 1.0, "face_y": 0.0, "hp": 100, "max_hp": 100, "stamina": 100.0, "max_stamina": 100,
         "xp": 0, "level": 1, "skill_points": 0, "stats": {"might": 1, "vitality": 1, "agility": 1},
         "gold": 0, "kills": 0, "last_attack": 0.0, "attack": None, "respawn_at": 0.0,
         "dodge_at": 0.0, "dodge_until": 0.0, "weapon": "sword", "weapons": ["sword", "axe", "bow"],
         "gear": "traveler", "gear_inventory": [], "dimension": "waking",
         "enchantments": {"weapon": {}, "gear": {}},
         "inventory": {"wood": 0, "herb": 0, "ore": 0, "hide": 0, "slime": 0, "crystal": 0, "shard": 0, "potion": 2, "arrows": 18},
         "quest_stage": 0, "quest_active": False, "quest_kills": {}, "quest_gather": {},
         "gathering": None, "last_chat": 0.0}
    saved = load_character(name)
    p.update(saved)
    p["x"] = max(25.0, min(WORLD_W - 25.0, float(p["x"])))
    p["y"] = max(25.0, min(WORLD_H - 25.0, float(p["y"])))
    p["stats"] = {key: max(1, min(30, int(p.get("stats", {}).get(key, 1))))
                  for key in stat_names}
    p["weapons"] = list(dict.fromkeys(weapon for weapon in p.get("weapons", []) if weapon in WEAPONS))
    if not p["weapons"]:
        p["weapons"] = ["sword", "axe", "bow"]
    if p["weapon"] not in p["weapons"]:
        p["weapon"] = "sword"
    p["gear_inventory"] = list(dict.fromkeys(gear for gear in p.get("gear_inventory", []) if gear in GEAR and gear != p.get("gear")))
    if p.get("dimension") not in {"waking", "echo"}: p["dimension"] = "waking"
    saved_enchants = p.get("enchantments") if isinstance(p.get("enchantments"), dict) else {}
    p["enchantments"] = {"weapon": saved_enchants.get("weapon", {}), "gear": saved_enchants.get("gear", {})}
    if p["gear"] not in GEAR:
        p["gear"] = "traveler"
    p["inventory"] = {key: max(0, min(999999, int(p.get("inventory", {}).get(key, 0))))
                       for key in p["inventory"]}
    p["inventory"].setdefault("shard", 0)
    p["quest_stage"] = max(0, min(6, int(p["quest_stage"])))
    update_derived(p)
    players[pid] = p; clients[pid] = websocket
    await websocket.send_text(json.dumps(snapshot(pid), ensure_ascii=False))
    await send_event({"type": "notice", "text": f"{name} прибыл(а) в Лес Эхо."})
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw) > 2048: continue
            try: message = json.loads(raw)
            except json.JSONDecodeError: continue
            if isinstance(message, dict): await handle_message(pid, p, message, time.monotonic())
    except WebSocketDisconnect:
        pass
    finally:
        if pid in players:
            try:
                save_character(players[pid])
            except sqlite3.Error:
                pass
        clients.pop(pid, None); players.pop(pid, None)
        await send_event({"type": "notice", "text": f"{name} покинул(а) мир."})


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
