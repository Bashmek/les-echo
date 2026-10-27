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
WORLD_W, WORLD_H = 6400, 3200
TICK = 0.05
MAX_PLAYERS = 8

ZONES = [
    {"id": "camp", "name": "Лагерь Следопытов", "x0": 0, "x1": 800, "level": "Безопасная зона", "danger": 0},
    {"id": "forest", "name": "Шепчущий лес", "x0": 800, "x1": 1600, "level": "Уровень 1–3", "danger": 1},
    {"id": "marsh", "name": "Затонувшие топи", "x0": 1600, "x1": 2400, "level": "Уровень 4–6", "danger": 2},
    {"id": "ruins", "name": "Пепельные руины", "x0": 2400, "x1": 3200, "level": "Уровень 7–10", "danger": 3},
    {"id": "glacier", "name": "Хребет Синего Пламени", "x0": 3200, "x1": 4000, "level": "Уровень 11–14", "danger": 4},
    {"id": "rift", "name": "Разлом Эха", "x0": 4000, "x1": 4800, "level": "Уровень 15–20", "danger": 5},
    {"id": "echo_wastes", "name": "Пустоши отголосков", "x0": 4800, "x1": 5600, "level": "Уровень 21–24", "danger": 6},
    {"id": "starfall", "name": "Берег звёздного падения", "x0": 5600, "x1": 6400, "level": "Уровень 25–30", "danger": 7},
]

WEAPONS = {
    "sword": {"name": "Меч дозорного", "kind": "melee", "damage": 18, "bonus": 22, "charge": .62, "stamina": 13, "range": 82, "arc": .28, "cooldown": .30, "color": "#f2d17d"},
    "axe": {"name": "Лесной колун", "kind": "melee", "damage": 22, "bonus": 28, "charge": .82, "stamina": 19, "range": 88, "arc": .12, "cooldown": .48, "color": "#d9a66d"},
    "bow": {"name": "Тисовый лук", "kind": "bow", "damage": 14, "bonus": 28, "charge": .90, "stamina": 10, "cooldown": .18, "color": "#a8d982"},
    "forest_bow": {"name": "Лук следопыта", "kind": "bow", "damage": 21, "bonus": 35, "charge": .82, "stamina": 11, "cooldown": .18, "color": "#9be39d", "rarity": "uncommon"},
    "apprentice_staff": {"name": "Посох ученика", "kind": "staff", "damage": 13, "bonus": 18, "charge": .72, "stamina": 10, "range": 94, "arc": .22, "cooldown": .38, "color": "#91d8df", "rarity": "uncommon", "spell_power": .12},
    "thorn_staff": {"name": "Посох живых терний", "kind": "staff", "damage": 21, "bonus": 27, "charge": .68, "stamina": 11, "range": 104, "arc": .24, "cooldown": .34, "color": "#a2df86", "rarity": "rare", "spell_power": .20},
    "iron_sword": {"name": "Клинок из болотной стали", "kind": "melee", "damage": 27, "bonus": 33, "charge": .66, "stamina": 15, "range": 90, "arc": .30, "cooldown": .31, "color": "#b8d8df", "rarity": "rare"},
    "moonblade": {"name": "Лунный резец", "kind": "melee", "damage": 31, "bonus": 39, "charge": .58, "stamina": 16, "range": 96, "arc": .34, "cooldown": .27, "color": "#b9e9d8", "rarity": "epic"},
    "ember_greatsword": {"name": "Клинок последнего зарева", "kind": "melee", "damage": 43, "bonus": 52, "charge": .78, "stamina": 22, "range": 108, "arc": .22, "cooldown": .44, "color": "#ff9b59", "rarity": "legendary"},
    "starfall_bow": {"name": "Лук звёздного падения", "kind": "bow", "damage": 25, "bonus": 47, "charge": .82, "stamina": 12, "cooldown": .15, "color": "#a8e6db", "rarity": "epic"},
    "frostfang": {"name": "Клык Ледяного змея", "kind": "melee", "damage": 47, "bonus": 58, "charge": .63, "stamina": 20, "range": 106, "arc": .28, "cooldown": .32, "color": "#a9f5ff", "rarity": "legendary"},
    "void_edge": {"name": "Рассекающий разлом", "kind": "melee", "damage": 62, "bonus": 76, "charge": .72, "stamina": 24, "range": 122, "arc": .24, "cooldown": .40, "color": "#d99aff", "rarity": "legendary"},
    "astral_staff": {"name": "Посох звёздного прилива", "kind": "staff", "damage": 32, "bonus": 44, "charge": .66, "stamina": 12, "range": 110, "arc": .24, "cooldown": .34, "color": "#ffd783", "rarity": "legendary", "spell_power": .32},
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
    "starweave": {"name": "Мантия звёздного прилива", "defense": 34, "color": "#e5c778", "rarity": "legendary", "lore": "Ткань помнит свет далёких миров."},
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
    "echo_stalker": {"name": "Охотник Пустошей", "hp": 1040, "speed": 62, "damage": 66, "range": 82, "cooldown": 1.55, "xp": 900, "color": "#d3a3ef", "zone": 6},
    "star_warden": {"name": "Страж звёздного берега", "hp": 1680, "speed": 41, "damage": 92, "range": 104, "cooldown": 2.0, "xp": 1450, "color": "#f1d47d", "zone": 7},
    "astral_tyrant": {"name": "Астральный тиран", "hp": 5600, "speed": 34, "damage": 118, "range": 148, "cooldown": 2.2, "xp": 9200, "color": "#ff799b", "zone": 7},
}


SHOP_CATALOG = {
    "potion": {"name": "Настойка следопыта", "description": "+48 здоровья", "price": 32, "kind": "potion"},
    "arrows": {"name": "Колчан стрел", "description": "8 стрел", "price": 20, "kind": "arrows"},
    "echo_crystal": {"name": "Эхо-кристаллы", "description": "3 кристалла", "price": 48, "kind": "crystal"},
    "rift_shard": {"name": "Осколок разлома", "description": "1 осколок", "price": 55, "kind": "shard"},
    "apprentice_staff": {"name": "Посох ученика", "description": "Посох · сила заклинаний +12%", "price": 135, "kind": "weapon"},
    "iron_sword": {"name": "Клинок из болотной стали", "description": "Редкое оружие", "price": 230, "kind": "weapon"},
    "wolf_cloak": {"name": "Плащ туманного волка", "description": "Броня · защита 5", "price": 145, "kind": "gear"},
    "marsh_armor": {"name": "Болотная броня", "description": "Броня · защита 8", "price": 270, "kind": "gear"},
}
SELL_PRICES = {"wood": 3, "herb": 4, "ore": 6, "hide": 8, "slime": 5, "crystal": 10, "shard": 14, "potion": 12, "arrows": 1}
ENCHANT_CATALOG = {
    "sharpness": {"name": "Острота", "target": "weapon", "description": "+8 урона за уровень"},
    "vampirism": {"name": "Похищение жизни", "target": "weapon", "description": "Лечит на 6% урона за уровень"},
    "protection": {"name": "Защита", "target": "gear", "description": "+2 к защите за уровень"},
}
ENCHANT_MAX_LEVEL = 3

def gear_sell_price(item_id: str) -> int:
    return {"common": 18, "uncommon": 34, "rare": 58, "epic": 92, "legendary": 150}.get(GEAR.get(item_id, {}).get("rarity", "common"), 18)

def weapon_sell_price(item_id: str) -> int:
    return {"common": 22, "uncommon": 36, "rare": 64, "epic": 105, "legendary": 165}.get(WEAPONS.get(item_id, {}).get("rarity", "common"), 22)

app = FastAPI(title="Лес Эхо: Пробуждение")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
players: dict[str, dict[str, Any]] = {}
clients: dict[str, WebSocket] = {}
mobs: list[dict[str, Any]] = []
nodes: list[dict[str, Any]] = []
arrows: list[dict[str, Any]] = []
thorn_fields: list[dict[str, Any]] = []
SPELLS = {
    "fireball": {"name": "Огненный шар", "mana": 18, "cooldown": 2.8, "damage": 48, "radius": 100},
    "lightning": {"name": "Молния", "mana": 26, "cooldown": 4.5, "damage": 58, "radius": 125},
    "thorns": {"name": "Колючие терни", "mana": 23, "cooldown": 6.5, "damage": 17, "radius": 112},
    "heal": {"name": "Исцеление", "mana": 24, "cooldown": 7.0, "heal": 52, "radius": 125, "unlock_spent": 0, "unlock_level": 1},
    "ice_lance": {"name": "Ледяное копьё", "mana": 30, "cooldown": 4.2, "damage": 72, "radius": 76, "unlock_spent": 90, "unlock_level": 3},
    "arcane_burst": {"name": "Всплеск маны", "mana": 38, "cooldown": 7.0, "damage": 92, "radius": 148, "unlock_spent": 240, "unlock_level": 5},
    "meteor": {"name": "Метеоритный дождь", "mana": 58, "cooldown": 12.0, "damage": 132, "radius": 172, "unlock_spent": 500, "unlock_level": 8},
    "frost_nova": {"name": "Ледяная волна", "mana": 44, "cooldown": 8.5, "damage": 112, "radius": 162, "unlock_spent": 700, "unlock_level": 10},
    "soul_lance": {"name": "Копьё душ", "mana": 48, "cooldown": 6.8, "damage": 168, "radius": 82, "unlock_spent": 900, "unlock_level": 12},
    "starfall": {"name": "Звёздный обвал", "mana": 76, "cooldown": 15.0, "damage": 238, "radius": 210, "unlock_spent": 1300, "unlock_level": 16},
}


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
            "boss": kind in {"colossus", "astral_tyrant"}}


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
        "forest": [("slime", 8, 1), ("wolf", 5, 2)],
        "marsh": [("boar", 6, 4), ("wisp", 5, 5), ("stone", 2, 6)],
        "ruins": [("ashling", 6, 7), ("ashguard", 4, 8), ("colossus", 1, 10)],
        "glacier": [("frost_wyrm", 7, 11), ("frost_wyrm", 4, 13)],
        "rift": [("rift_knight", 7, 15), ("echo_dragon", 1, 20)],
        "echo_wastes": [("echo_stalker", 7, 21), ("echo_stalker", 3, 23)],
        "starfall": [("star_warden", 6, 25), ("astral_tyrant", 1, 30)],
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
        elif zone["id"] in {"rift", "echo_wastes", "starfall"}:
            kind = "shard" if roll < .55 else "crystal" if roll < .84 else "ore"
        else:
            kind = "ore" if roll < .45 else "crystal" if roll < .88 else "wood"
        nodes.append({"id": f"node-{i}", "kind": kind, "x": x,
                      "y": random.uniform(100, WORLD_H - 100), "active": True,
                      "respawn_at": 0.0, "zone": zone["id"]})
    random.seed()


init_world()


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
            "face_x": p["face_x"], "face_y": p["face_y"], "hp": p["hp"], "max_hp": p["max_hp"],
            "stamina": round(p["stamina"], 1), "max_stamina": p["max_stamina"],
            "mana": round(p.get("mana", 0), 1), "max_mana": p.get("max_mana", 0), "xp": p["xp"],
            "level": p["level"], "skill_points": p["skill_points"], "stats": dict(p["stats"]),
            "gold": p["gold"], "kills": p["kills"], "quest": quest_data(p),
            "respawning": p["respawn_at"] > now, "weapons": list(p["weapons"]), "weapon": p["weapon"],
            "gear": p["gear"], "gear_inventory": list(p["gear_inventory"]),
            "enchantments": p.get("enchantments", {"weapon": {}, "gear": {}}),
            "mana": round(p.get("mana", 0), 1), "max_mana": p.get("max_mana", 0),
            "shop_catalog": SHOP_CATALOG, "sell_prices": SELL_PRICES, "enchant_catalog": ENCHANT_CATALOG,
            "spell_catalog": SPELLS, "spells_unlocked": [sid for sid in SPELLS if spell_unlocked(p, sid)],
            "magic_mana_spent": int(p.get("magic_mana_spent", 0)),
            "upgrades": p.get("upgrades", {"weapon": {}, "gear": {}}),
            "weapon_sell_prices": {key: weapon_sell_price(key) for key in p["weapons"]},
            "gear_sell_prices": {key: gear_sell_price(key) for key in [p["gear"], *p["gear_inventory"]]},
            "gear_catalog": GEAR,
            "weapon_catalog": {key: {"name": value["name"], "rarity": value.get("rarity", "common"),
                                     "damage": value["damage"], "kind": value["kind"]}
                               for key, value in WEAPONS.items()},
            "inventory": dict(p["inventory"]), "attack": action,
            "gathering": p["gathering"] is not None, "gather_progress": (p["gathering"]["progress"] / 1.15 if p["gathering"] else 0), "zone": zone["id"],
            "dodge_ready": now >= p["dodge_at"]}


def snapshot(for_id: str) -> dict[str, Any]:
    now = time.monotonic()
    return {"type": "state", "you": for_id, "world": {"w": WORLD_W, "h": WORLD_H},
            "zones": ZONES, "players": [player_row(pid, p, now) for pid, p in players.items()],
            "mobs": [{**{k: mob[k] for k in ("id", "kind", "level", "x", "y", "hp", "max_hp", "boss")},
                      "telegraphing": mob["telegraph_until"] > now}
                     for mob in mobs if mob["hp"] > 0],
            "nodes": [{k: n[k] for k in ("id", "kind", "x", "y", "active", "zone")} for n in nodes],
            "arrows": [{k: a[k] for k in ("x", "y", "vx", "vy", "life", "kind", "radius") if k in a} for a in arrows],
            "thorn_fields": [{k: field[k] for k in ("x", "y", "radius", "until", "owner")} for field in thorn_fields]}


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
    previous_max_mana = p.get("max_mana", 60)
    p["max_mana"] = (60 + (p["level"] - 1) * 5 + (p["stats"]["vitality"] - 1) * 3
                     + (p["stats"].get("wisdom", 1) - 1) * 12
                     + (p.get("magic_mana_spent", 0) // 100) * 6)
    p["mana"] = min(p.get("mana", p["max_mana"]), p["max_mana"])
    if p["max_mana"] > previous_max_mana:
        p["mana"] = min(p["max_mana"], p["mana"] + p["max_mana"] - previous_max_mana)
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
    missions = [
        ("slime", 4, "herb", 3, "Очистить опушку"),
        ("wolf", 3, "ore", 4, "Следы в топи"),
        ("boar", 3, "crystal", 3, "Свет под водой"),
        ("colossus", 1, "", 0, "Пепельный колосс"),
        ("frost_wyrm", 4, "crystal", 6, "Синий хребет"),
        ("echo_dragon", 1, "shard", 8, "Разлом Эха"),
        ("rift_knight", 5, "shard", 10, "Осколки на ветру"),
        ("echo_stalker", 6, "crystal", 12, "Охотники Пустошей"),
        ("star_warden", 5, "shard", 18, "Стражи звёздного берега"),
        ("astral_tyrant", 1, "shard", 24, "Последний свет"),
    ]
    return missions[min(max(0, stage), len(missions) - 1)]


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
        gold_rewards = [45, 90, 145, 260, 420, 650, 900, 1250, 1800, 3200]
        xp_rewards = [100, 220, 360, 700, 1100, 1800, 2400, 3300, 4800, 10000]
        gold = gold_rewards[stage]
        xp = xp_rewards[stage]
        p["gold"] += gold
        add_xp(p, xp)
        if stage == 0:
            p["inventory"]["potion"] += 2
        elif stage == 1:
            grant_gear(p, "wolf_cloak")
        elif stage == 2:
            grant_gear(p, "marsh_armor")
        elif stage == 3:
            grant_gear(p, "ash_plate")
        elif stage == 4:
            grant_gear(p, "glacier_mantle")
        elif stage == 5:
            grant_gear(p, "rift_plate")
        elif stage == 6:
            grant_gear(p, "starweave")
        elif stage == 7:
            grant_weapon(p, "astral_staff")
        elif stage >= 8:
            grant_weapon(p, "astral_staff")
            p["inventory"]["shard"] += 8
        await tell(p["id"], f"Поручение завершено. Получено {gold} монет, {xp} опыта и награда следопыту.")
    elif p["quest_active"]:
        await tell(p["id"], "Поручение ещё не выполнено. Загляни в журнал.")
    elif p["quest_stage"] >= 10:
        await tell(p["id"], "Ты прошёл всю цепь поручений и остановил Астрального тирана. Мир открыт для свободного исследования.")
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
    if kind == "slime":
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
        inv["shard"] += 1
    elif kind == "ashguard":
        inv["crystal"] += 3; inv["ore"] += 3; inv["shard"] += random.randint(2, 3)
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
    elif kind == "echo_stalker":
        inv["crystal"] += 6; inv["shard"] += random.randint(4, 7)
        if random.random() < .22: grant_gear(p, "starweave")
    elif kind == "star_warden":
        inv["crystal"] += 10; inv["shard"] += random.randint(8, 12)
        if random.random() < .16: grant_weapon(p, "astral_staff")
    elif kind == "astral_tyrant":
        inv["crystal"] += 40; inv["shard"] += 36
        grant_gear(p, "starweave")
        grant_weapon(p, "astral_staff")
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
    damage = (spec["damage"] + spec["bonus"] * charge + power_bonus
              + 8 * enchant_level(p, "weapon", weapon_id, "sharpness")
              + 6 * item_upgrade_level(p, "weapon", weapon_id))
    if spec["kind"] == "bow":
        if p["inventory"]["arrows"] <= 0:
            asyncio.create_task(tell(p["id"], "Колчан пуст. Стрелы можно изготовить из дерева и руды."))
            return
        p["inventory"]["arrows"] -= 1
        speed = 390 + 240 * charge + (p["stats"]["agility"] - 1) * 8
        arrows.append({"x": p["x"] + ax * 18, "y": p["y"] + ay * 18,
                       "vx": ax * speed, "vy": ay * speed, "damage": damage,
                       "owner": p["id"], "life": 1.45, "kind": "arrow"})
        return
    reach = spec["range"] + 12 * charge
    hits = []
    for mob in mobs:
        if mob["hp"] <= 0: continue
        dx, dy = mob["x"] - p["x"], mob["y"] - p["y"]
        dist = math.hypot(dx, dy)
        if dist <= reach and dist > .01 and (dx * ax + dy * ay) / dist >= spec["arc"]:
            hits.append((dist, mob))
    hits.sort(key=lambda row: row[0])
    max_hits = 3 if weapon_id == "axe" else 2 if weapon_id == "iron_sword" else 1
    for _, mob in hits[:max_hits]:
        mob["hp"] -= damage
        vampirism = enchant_level(p, "weapon", weapon_id, "vampirism")
        if vampirism: p["hp"] = min(p["max_hp"], p["hp"] + round(damage * .06 * vampirism))
        mob["alert_until"] = now + 4
        if mob["hp"] <= 0:
            mob["hp"] = 0
            mob["respawn_at"] = now + random.uniform(24, 40)
            award_drop(p, mob)
        asyncio.create_task(send_event({"type": "hit", "mob": mob["id"], "x": mob["x"], "y": mob["y"], "damage": round(damage)}))
    # Player-versus-player combat is enabled outside the safe camp.
    if zone_for_x(p["x"])["danger"] > 0:
        candidates = []
        for other in players.values():
            if other["id"] == p["id"] or other["respawn_at"] > now:
                continue
            if zone_for_x(other["x"])["danger"] == 0:
                continue
            dx, dy = other["x"] - p["x"], other["y"] - p["y"]
            dist = math.hypot(dx, dy)
            if dist <= reach + 10 and dist > .01 and (dx * ax + dy * ay) / dist >= spec["arc"]:
                candidates.append((dist, other))
        candidates.sort(key=lambda row: row[0])
        for _, other in candidates[:max_hits]:
            defense = player_defense(other)
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


def enchant_level(p: dict[str, Any], target: str, item_id: str, enchant_id: str) -> int:
    return int(p.get("enchantments", {}).get(target, {}).get(item_id, {}).get(enchant_id, 0))


WIZARD_X, WIZARD_Y = 470.0, 1100.0
FORGE_X, FORGE_Y = 625.0, 1100.0
MAX_ITEM_UPGRADE = 5


def spell_unlocked(p: dict[str, Any], spell_id: str) -> bool:
    spec = SPELLS.get(spell_id)
    return bool(spec and p.get("level", 1) >= spec.get("unlock_level", 1)
                and p.get("magic_mana_spent", 0) >= spec.get("unlock_spent", 0))


def item_upgrade_level(p: dict[str, Any], target: str, item_id: str) -> int:
    return max(0, min(MAX_ITEM_UPGRADE,
                      int(p.get("upgrades", {}).get(target, {}).get(item_id, 0))))


def player_defense(p: dict[str, Any]) -> int:
    gear_id = p.get("gear", "traveler")
    base = GEAR.get(gear_id, GEAR["traveler"])["defense"]
    return base + 3 * item_upgrade_level(p, "gear", gear_id) + 2 * enchant_level(p, "gear", gear_id, "protection")


def near_wizard(p: dict[str, Any]) -> bool:
    return math.hypot(p["x"] - WIZARD_X, p["y"] - WIZARD_Y) <= 112


def near_forge(p: dict[str, Any]) -> bool:
    return math.hypot(p["x"] - FORGE_X, p["y"] - FORGE_Y) <= 112

async def market_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    action, item_id = str(msg.get("action", "")), str(msg.get("id", ""))
    inv = p["inventory"]
    if action == "buy":
        offer = SHOP_CATALOG.get(item_id)
        if not offer:
            await tell(p["id"], "Такого товара нет в каталоге лавки."); return
        if p["gold"] < offer["price"]:
            await tell(p["id"], f"Не хватает монет: нужно {offer['price']}, у тебя {p['gold']}."); return
        kind = offer["kind"]
        if kind == "weapon" and item_id in p["weapons"]:
            await tell(p["id"], "Это оружие уже есть в сумке."); return
        if kind == "gear" and (item_id == p["gear"] or item_id in p["gear_inventory"]):
            await tell(p["id"], "Эта броня уже есть в сумке."); return
        p["gold"] -= offer["price"]
        if kind == "potion": inv["potion"] += 1
        elif kind == "arrows": inv["arrows"] += 8
        elif kind == "crystal": inv["crystal"] += 3
        elif kind == "shard": inv["shard"] += 1
        elif kind == "weapon":
            p["weapons"].append(item_id)
            if item_id == "apprentice_staff": p["weapon"] = item_id
        elif kind == "gear": p["gear_inventory"].append(item_id)
        await tell(p["id"], f"Куплено: {offer['name']} за {offer['price']} монет.")
        return
    if action == "sell":
        item_type = str(msg.get("item_type", ""))
        if item_type == "resource":
            if item_id not in SELL_PRICES or inv.get(item_id, 0) < 1:
                await tell(p["id"], "Такого предмета нет в рюкзаке для продажи."); return
            try: count = max(1, min(int(msg.get("count", 1)), int(inv[item_id])))
            except (TypeError, ValueError): count = 1
            earnings = SELL_PRICES[item_id] * count
            inv[item_id] -= count; p["gold"] += earnings
            await tell(p["id"], f"Продано: {count} × {item_id} за {earnings} монет."); return
        if item_type == "weapon":
            if item_id not in WEAPONS or item_id not in p["weapons"]:
                await tell(p["id"], "Оружие не найдено в сумке."); return
            if item_id == p["weapon"]:
                await tell(p["id"], "Сначала экипируй другое оружие."); return
            if len(p["weapons"]) <= 1:
                await tell(p["id"], "Нельзя продать последнее оружие."); return
            p["weapons"].remove(item_id); p.get("enchantments", {}).get("weapon", {}).pop(item_id, None)
            earnings = weapon_sell_price(item_id); p["gold"] += earnings
            await tell(p["id"], f"Продано: {WEAPONS[item_id]['name']} за {earnings} монет."); return
        if item_type == "gear":
            if item_id not in GEAR or item_id not in p["gear_inventory"]:
                await tell(p["id"], "Надетую броню или отсутствующий предмет продать нельзя."); return
            p["gear_inventory"].remove(item_id); p.get("enchantments", {}).get("gear", {}).pop(item_id, None)
            earnings = gear_sell_price(item_id); p["gold"] += earnings
            await tell(p["id"], f"Продано: {GEAR[item_id]['name']} за {earnings} монет."); return
        await tell(p["id"], "Не удалось определить предмет для продажи."); return
    if action == "enchant":
        if not near_wizard(p):
            await tell(p["id"], "Зачарования накладывает волшебник у святилища в лагере. Подойди к нему и нажми G."); return
        enchant_id = item_id; spec = ENCHANT_CATALOG.get(enchant_id)
        if not spec:
            await tell(p["id"], "Такого зачарования нет."); return
        target = spec["target"]
        equipped_id = p.get("weapon") if target == "weapon" else p.get("gear")
        catalog = WEAPONS if target == "weapon" else GEAR
        if equipped_id not in catalog:
            await tell(p["id"], "Надень подходящий предмет, затем повтори зачарование."); return
        current = enchant_level(p, target, equipped_id, enchant_id)
        if current >= ENCHANT_MAX_LEVEL:
            await tell(p["id"], "Это зачарование уже достигло максимального уровня."); return
        price = 70 + current * 85
        if p["gold"] < price:
            await tell(p["id"], f"Не хватает монет: зачарование стоит {price}."); return
        p["gold"] -= price
        p.setdefault("enchantments", {}).setdefault(target, {}).setdefault(equipped_id, {})[enchant_id] = current + 1
        await tell(p["id"], f"Наложено зачарование «{spec['name']}» {current + 1}-го уровня на {catalog[equipped_id]['name']} за {price} монет.")
        return
    await tell(p["id"], "Неизвестная операция лавки.")

async def forge_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    if not near_forge(p):
        await tell(p["id"], "Подойди к кузнице у восточной тропы в лагере и нажми H.")
        return
    action, item_id = str(msg.get("action", "")), str(msg.get("id", ""))
    inv = p["inventory"]
    if action == "craft":
        if item_id == "forest_bow":
            cost = {"wood": 8, "hide": 3, "ore": 2}
            if item_id in p["weapons"]:
                await tell(p["id"], "Лук следопыта уже изготовлен."); return
            if any(inv.get(k, 0) < v for k, v in cost.items()):
                await tell(p["id"], "Нужны 8 дерева, 3 шкуры и 2 руды."); return
            for key, value in cost.items(): inv[key] -= value
            p["weapons"].append(item_id)
            await tell(p["id"], "Лук следопыта скован и добавлен в рюкзак."); return
        if item_id == "thorn_staff":
            cost = {"wood": 6, "crystal": 5, "herb": 4}
            if item_id in p["weapons"]:
                await tell(p["id"], "Посох живых терний уже изготовлен."); return
            if any(inv.get(k, 0) < v for k, v in cost.items()):
                await tell(p["id"], "Нужны 6 дерева, 5 эхо-кристаллов и 4 лунные травы."); return
            for key, value in cost.items(): inv[key] -= value
            p["weapons"].append(item_id)
            await tell(p["id"], "Посох живых терний выкован и добавлен в рюкзак."); return
        await tell(p["id"], "Такого чертежа в кузнице нет."); return
    target = "weapon" if action == "upgrade_weapon" else "gear" if action == "upgrade_armor" else ""
    if target:
        item_id = p.get("weapon") if target == "weapon" else p.get("gear")
        catalog = WEAPONS if target == "weapon" else GEAR
        if item_id not in catalog:
            await tell(p["id"], "Сначала выбери подходящее снаряжение."); return
        level = item_upgrade_level(p, target, item_id)
        if level >= MAX_ITEM_UPGRADE:
            await tell(p["id"], "Предмет уже достиг предела +5."); return
        gold_cost = (75 if target == "weapon" else 65) + level * (55 if target == "weapon" else 50)
        ore_cost = 2 + level
        crystal_cost = 0 if level < 2 else 1 + level // 2
        if p["gold"] < gold_cost or inv.get("ore", 0) < ore_cost or inv.get("crystal", 0) < crystal_cost:
            await tell(p["id"], f"Нужно {gold_cost} монет, {ore_cost} руды и {crystal_cost} эхо-кристаллов."); return
        p["gold"] -= gold_cost; inv["ore"] -= ore_cost; inv["crystal"] -= crystal_cost
        p.setdefault("upgrades", {}).setdefault(target, {})[item_id] = level + 1
        benefit = "+6 базового урона" if target == "weapon" else "+3 защиты"
        await tell(p["id"], f"Улучшение +{level+1}: {catalog[item_id]['name']} · {benefit}."); return
    await tell(p["id"], "Неизвестная операция кузницы.")


async def wizard_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    if not near_wizard(p):
        await tell(p["id"], "Подойди к синему святилищу волшебника у костра и нажми G.")
        return
    action, item_id = str(msg.get("action", "")), str(msg.get("id", ""))
    if action == "buy_staff":
        offer_price = SHOP_CATALOG["apprentice_staff"]["price"]
        if "apprentice_staff" in p["weapons"]:
            await tell(p["id"], "Посох ученика уже у тебя."); return
        if p["gold"] < offer_price:
            await tell(p["id"], f"Посох стоит {offer_price} монет. Сейчас у тебя {p['gold']}."); return
        p["gold"] -= offer_price; p["weapons"].append("apprentice_staff"); p["weapon"] = "apprentice_staff"
        await tell(p["id"], "Куплен и экипирован посох ученика. Он усиливает заклинания на 12%."); return
    if action == "enchant":
        await market_action(p, {"action": "enchant", "id": item_id})
        return
    await tell(p["id"], "Неизвестная операция волшебника.")


def spell_damage(p: dict[str, Any], mob: dict[str, Any], damage: float, now: float) -> None:
    if mob["hp"] <= 0: return
    dealt = max(1, round(damage)); mob["hp"] -= dealt; mob["alert_until"] = now + 4
    if mob["hp"] <= 0:
        mob["hp"] = 0; mob["respawn_at"] = now + random.uniform(24, 40); award_drop(p, mob)
    try: asyncio.create_task(send_event({"type": "hit", "mob": mob["id"], "x": mob["x"], "y": mob["y"], "damage": dealt}))
    except RuntimeError: pass

async def cast_spell(p: dict[str, Any], now: float, spell_id: str, aim_x: float, aim_y: float,
                     target_x: float | None = None, target_y: float | None = None) -> None:
    spec = SPELLS.get(spell_id)
    if not spec: await tell(p["id"], "Неизвестное заклинание."); return
    if not spell_unlocked(p, spell_id):
        await tell(p["id"], f"Заклинание откроется на уровне {spec['unlock_level']} после расхода {spec['unlock_spent']} маны. Потрачено: {int(p.get('magic_mana_spent', 0))}."); return
    if p.get("respawn_at", 0) > now: await tell(p["id"], "Нельзя колдовать во время возвращения в лагерь."); return
    cooldowns = p.setdefault("spell_cooldowns", {})
    if cooldowns.get(spell_id, 0) > now: await tell(p["id"], f"Заклинание перезаряжается: {cooldowns[spell_id] - now:.1f} с."); return
    if p.get("mana", 0) < spec["mana"]: await tell(p["id"], f"Мало маны: нужно {spec['mana']}, сейчас {int(p.get('mana', 0))}."); return
    length = math.hypot(aim_x, aim_y)
    if length < .01: aim_x, aim_y = p.get("face_x", 1), p.get("face_y", 0); length = max(.01, math.hypot(aim_x, aim_y))
    aim_x, aim_y = aim_x / length, aim_y / length
    tx = float(target_x) if target_x is not None else p["x"] + aim_x * 180
    ty = float(target_y) if target_y is not None else p["y"] + aim_y * 180
    dx, dy = tx - p["x"], ty - p["y"]; dist = math.hypot(dx, dy)
    if dist > 420: tx, ty = p["x"] + dx / dist * 420, p["y"] + dy / dist * 420
    tx, ty = max(0.0, min(WORLD_W, tx)), max(0.0, min(WORLD_H, ty))
    p["mana"] -= spec["mana"]; cooldowns[spell_id] = now + spec["cooldown"]
    old_spent = int(p.get("magic_mana_spent", 0))
    p["magic_mana_spent"] = old_spent + int(spec["mana"])
    staff_power = float(WEAPONS.get(p.get("weapon", ""), {}).get("spell_power", 0))
    power = 1.0 + staff_power + (p.get("stats", {}).get("magic_power", 1) - 1) * 0.08
    update_derived(p)
    for unlocked_id, unlocked_spec in SPELLS.items():
        threshold = int(unlocked_spec.get("unlock_spent", 0))
        if threshold and old_spent < threshold <= p["magic_mana_spent"]:
            asyncio.create_task(tell(p["id"], f"Открыто заклинание «{unlocked_spec['name']}»! Требуется также уровень {unlocked_spec['unlock_level']}."))
    p["face_x"], p["face_y"] = aim_x, aim_y
    if spell_id in {"fireball", "ice_lance", "meteor", "soul_lance", "starfall"}:
        distance = max(1.0, math.hypot(tx - p["x"], ty - p["y"]))
        speed = 420 if spell_id == "fireball" else 500 if spell_id in {"ice_lance", "soul_lance"} else 250
        arrows.append({"x": p["x"] + aim_x * 18, "y": p["y"] + aim_y * 18,
                       "vx": (tx - p["x"]) / distance * speed, "vy": (ty - p["y"]) / distance * speed,
                       "damage": round(spec["damage"] * power), "owner": p["id"],
                       "life": min(1.6, distance / speed + .1), "kind": "spell_projectile",
                       "spell_id": spell_id, "radius": spec["radius"]})
    elif spell_id == "lightning":
        candidates = sorted((m for m in mobs if m["hp"] > 0 and math.hypot(m["x"] - tx, m["y"] - ty) <= spec["radius"]),
                           key=lambda m: math.hypot(m["x"] - tx, m["y"] - ty))
        for index, mob in enumerate(candidates[:4]): spell_damage(p, mob, spec["damage"] * power * (0.72 ** index), now)
        await send_event({"type": "spell_fx", "spell": spell_id, "x": tx, "y": ty, "radius": spec["radius"], "owner": p["id"]})
    elif spell_id in {"arcane_burst", "frost_nova"}:
        for mob in mobs:
            distance = math.hypot(mob["x"] - tx, mob["y"] - ty)
            if mob["hp"] > 0 and distance <= spec["radius"]:
                spell_damage(p, mob, spec["damage"] * power * max(.55, 1.0 - distance / (2 * spec["radius"])), now)
        await send_event({"type": "spell_fx", "spell": spell_id, "x": tx, "y": ty, "radius": spec["radius"], "owner": p["id"]})
    elif spell_id == "thorns":
        thorn_fields.append({"x": tx, "y": ty, "radius": spec["radius"], "damage": round(spec["damage"] * power),
                             "owner": p["id"], "until": now + 3.2, "next_hit": now})
        await send_event({"type": "spell_fx", "spell": spell_id, "x": tx, "y": ty, "radius": spec["radius"], "owner": p["id"]})
    elif spell_id == "heal":
        healed = 0
        for ally in players.values():
            if math.hypot(ally["x"] - p["x"], ally["y"] - p["y"]) <= spec["radius"] and ally.get("respawn_at", 0) <= now:
                before = ally["hp"]; ally["hp"] = min(ally["max_hp"], ally["hp"] + round(spec["heal"] * power)); healed += ally["hp"] - before
        await send_event({"type": "spell_fx", "spell": spell_id, "x": p["x"], "y": p["y"], "radius": spec["radius"], "owner": p["id"]})
        await tell(p["id"], f"Исцеление восстановило {healed} здоровья группе в радиусе {spec['radius']}."); return
    await tell(p["id"], f"Применено: {spec['name']} · область {spec['radius']} ед.")

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
    elif kind == "shop_action":
        await market_action(p, msg)
    elif kind == "forge_action":
        await forge_action(p, msg)
    elif kind == "wizard_action":
        await wizard_action(p, msg)
    elif kind == "spell":
        try:
            await cast_spell(p, now, str(msg.get("spell", "")), float(msg.get("aim_x", 0)), float(msg.get("aim_y", 0)),
                             float(msg["target_x"]) if msg.get("target_x") is not None else None,
                             float(msg["target_y"]) if msg.get("target_y") is not None else None)
        except (TypeError, ValueError): await tell(pid, "Не удалось прочитать направление заклинания.")
    elif kind == "weapon":
        weapon = str(msg.get("id", ""))
        if weapon in p["weapons"] and weapon in WEAPONS: p["weapon"] = weapon
    elif kind == "gather_start": start_gather(p, now)
    elif kind == "gather_stop": p["gathering"] = None
    elif kind == "interact": await interact_keeper(p)
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
        if stat in p["stats"] and p["skill_points"] > 0 and p["stats"][stat] < 30:
            p["stats"][stat] += 1; p["skill_points"] -= 1
            update_derived(p, heal=stat == "vitality")
            if stat == "wisdom":
                await tell(pid, f"Запас маны вырос до {p['max_mana']}; восстановление ускорено.")
            elif stat == "magic_power":
                await tell(pid, f"Сила магии выросла: +{(p['stats'][stat] - 1) * 8}% к урону заклинаний.")
            else:
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


stat_names = {"might": "Сила", "vitality": "Живучесть", "agility": "Ловкость",
              "wisdom": "Запас маны", "magic_power": "Сила магии"}
PERSIST_FIELDS = (
    "x", "y", "hp", "stamina", "xp", "level", "skill_points", "stats",
    "gold", "kills", "weapon", "weapons", "gear", "gear_inventory",
    "inventory", "quest_stage", "quest_active", "quest_kills", "quest_gather",
    "enchantments", "market_starter_grant", "magic_mana_spent", "upgrades", "mana",
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
            p["mana"] = min(p["max_mana"], p.get("mana", 0) + (9.0 + (p["stats"].get("wisdom", 1) - 1) * .65) * dt)
            if p["gathering"]:
                g = p["gathering"]
                node = next((n for n in nodes if n["id"] == g["node"] and n["active"]), None)
                if not node or math.hypot(node["x"] - p["x"], node["y"] - p["y"]) > 75 or math.hypot(p["mx"], p["my"]) > .1:
                    p["gathering"] = None
                else:
                    g["progress"] += dt
                    if g["progress"] >= 1.15:
                        node["active"] = False; node["respawn_at"] = now + 28
                        amount = random.randint(1, 2) if node["kind"] == "shard" else random.randint(2, 3)
                        p["inventory"][node["kind"]] += amount
                        if p["quest_active"]: p["quest_gather"][node["kind"]] = p["quest_gather"].get(node["kind"], 0) + amount
                        p["gathering"] = None
                        await tell(pid, f"Собрано: {amount} — {node['kind']}.")
        for node in nodes:
            if not node["active"] and node["respawn_at"] <= now: node["active"] = True
        for mob in mobs:
            if mob["hp"] <= 0:
                if mob["respawn_at"] <= now:
                    mob.update(scaled_mob(mob["kind"], mob["level"], int(mob["id"].split("-")[-1]), mob["spawn_x"], mob["spawn_y"]))
                continue
            target = min((p for p in players.values() if p["respawn_at"] <= now and
                          zone_for_x(p["x"])["danger"] > 0 and
                          zone_for_x(p["x"])["id"] == zone_for_x(mob["x"])["id"]),
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
                    defense = player_defense(target)
                    defense += 2 * enchant_level(target, "gear", target.get("gear", ""), "protection")
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
        for field in list(thorn_fields):
            if field["until"] <= now:
                thorn_fields.remove(field); continue
            if field["next_hit"] <= now:
                owner = players.get(field["owner"])
                if owner:
                    for mob in mobs:
                        if mob["hp"] > 0 and math.hypot(mob["x"] - field["x"], mob["y"] - field["y"]) <= field["radius"]:
                            spell_damage(owner, mob, field["damage"], now)
                field["next_hit"] = now + .65
        for arrow in list(arrows):
            arrow["x"] += arrow["vx"] * dt; arrow["y"] += arrow["vy"] * dt
            arrow["life"] -= dt
            shooter = players.get(arrow.get("owner"))
            player_target = next((p for p in players.values()
                                  if arrow.get("kind") != "spell_projectile"
                                  and p["id"] != arrow.get("owner") and p["respawn_at"] <= now
                                  and zone_for_x(p["x"])["danger"] > 0
                                  and math.hypot(p["x"] - arrow["x"], p["y"] - arrow["y"]) < 28), None)
            if player_target and shooter and zone_for_x(shooter["x"])["danger"] > 0:
                defense = player_defense(player_target)
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
            expired = arrow["life"] <= 0 or not (0 <= arrow["x"] <= WORLD_W and 0 <= arrow["y"] <= WORLD_H)
            if arrow.get("kind") == "spell_projectile" and (target or expired):
                owner = players.get(arrow.get("owner")); spell_id = arrow.get("spell_id", "fireball")
                if owner:
                    radius = arrow.get("radius", 100)
                    for mob in mobs:
                        d = math.hypot(mob["x"] - arrow["x"], mob["y"] - arrow["y"])
                        if mob["hp"] > 0 and d <= radius:
                            spell_damage(owner, mob, arrow["damage"] * max(.55, 1.0-d/max(1.0,2*radius)), now)
                await send_event({"type": "spell_fx", "spell": spell_id, "x": arrow["x"], "y": arrow["y"], "radius": arrow.get("radius", 100), "owner": arrow.get("owner")})
                if arrow in arrows: arrows.remove(arrow)
            elif target:
                target["hp"] -= arrow["damage"]; target["alert_until"] = now + 4
                if target["hp"] <= 0:
                    target["hp"] = 0; target["respawn_at"] = now + random.uniform(24, 40)
                    owner = players.get(arrow["owner"])
                    if owner: award_drop(owner, target)
                asyncio.create_task(send_event({"type": "hit", "mob": target["id"], "x": target["x"], "y": target["y"], "damage": round(arrow["damage"])}))
                arrows.remove(arrow)
            elif expired:
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
         "xp": 0, "level": 1, "skill_points": 0, "stats": {"might": 1, "vitality": 1, "agility": 1, "wisdom": 1, "magic_power": 1},
         "gold": 0, "kills": 0, "last_attack": 0.0, "attack": None, "respawn_at": 0.0,
         "mana": 60, "max_mana": 60, "spell_cooldowns": {},
         "enchantments": {"weapon": {}, "gear": {}}, "upgrades": {"weapon": {}, "gear": {}},
         "magic_mana_spent": 0, "market_starter_grant": False,
         "dodge_at": 0.0, "dodge_until": 0.0, "weapon": "sword", "weapons": ["sword", "axe", "bow"],
         "gear": "traveler", "gear_inventory": [],
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
    if p["gear"] not in GEAR:
        p["gear"] = "traveler"
    p["inventory"] = {key: max(0, min(999999, int(p.get("inventory", {}).get(key, 0))))
                       for key in p["inventory"]}
    for resource in ("wood", "herb", "ore", "hide", "slime", "crystal", "shard", "potion", "arrows"):
        p["inventory"].setdefault(resource, 0)
    if not isinstance(p.get("enchantments"), dict): p["enchantments"] = {"weapon": {}, "gear": {}}
    p["enchantments"].setdefault("weapon", {}); p["enchantments"].setdefault("gear", {})
    p["spell_cooldowns"] = {}
    p["magic_mana_spent"] = max(0, min(1000000, int(p.get("magic_mana_spent", 0))))
    if not isinstance(p.get("upgrades"), dict): p["upgrades"] = {"weapon": {}, "gear": {}}
    p["upgrades"].setdefault("weapon", {}); p["upgrades"].setdefault("gear", {})
    if not p.get("market_starter_grant", False):
        p["gold"] = max(0, int(p.get("gold", 0))) + 150
        p["market_starter_grant"] = True
    p["quest_stage"] = max(0, min(10, int(p["quest_stage"])))
    p["mana"] = max(0.0, min(100000.0, float(p.get("mana", 60))))
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
