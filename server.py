from __future__ import annotations

import asyncio
import json
import hashlib
import hmac
import secrets
import re
import math
import random
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "echo_saves.sqlite3"
WORLD_W, WORLD_H = 12600, 7200
TICK = 0.05
MAX_PLAYERS = 8

ZONES = [
    {"id": "camp", "name": "Лагерь Следопытов", "x0": 0, "x1": 1400, "level": "Безопасная зона", "danger": 0},
    {"id": "forest", "name": "Шепчущий лес", "x0": 1400, "x1": 2800, "level": "Уровень 1–3", "danger": 1},
    {"id": "marsh", "name": "Затонувшие топи", "x0": 2800, "x1": 4200, "level": "Уровень 4–6", "danger": 2},
    {"id": "ruins", "name": "Пепельные руины", "x0": 4200, "x1": 5600, "level": "Уровень 7–10", "danger": 3},
    {"id": "glacier", "name": "Хребет Синего Пламени", "x0": 5600, "x1": 7000, "level": "Уровень 11–14", "danger": 4},
    {"id": "rift", "name": "Разлом Эха", "x0": 7000, "x1": 8300, "level": "Уровень 15–19", "danger": 5},
    {"id": "abyss", "name": "Астральная Бездна", "x0": 8300, "x1": 9600, "level": "Уровень 20–25", "danger": 6},
    {"id": "obsidian", "name": "Обсидиановый край", "x0": 9600, "x1": 11100, "level": "Уровень 26–30", "danger": 7},
    {"id": "garden", "name": "Первозданный сад", "x0": 11100, "x1": 12600, "level": "Уровень 31–35", "danger": 8},
]

WEAPONS = {
    "sword": {"name": "Меч дозорного", "kind": "melee", "damage": 18, "bonus": 22, "charge": .62, "stamina": 13, "range": 44, "arc": .28, "cooldown": .30, "color": "#f2d17d"},
    "axe": {"name": "Лесной колун", "kind": "melee", "damage": 22, "bonus": 28, "charge": .82, "stamina": 19, "range": 48, "arc": .12, "cooldown": .48, "color": "#d9a66d"},
    "bow": {"name": "Тисовый лук", "kind": "bow", "damage": 14, "bonus": 28, "charge": .90, "stamina": 10, "cooldown": .18, "color": "#a8d982"},
    "forest_bow": {"name": "Лук следопыта", "kind": "bow", "damage": 21, "bonus": 35, "charge": .82, "stamina": 11, "cooldown": .18, "color": "#9be39d", "rarity": "uncommon"},
    "apprentice_staff": {"name": "Посох ученика", "kind": "staff", "damage": 13, "bonus": 18, "charge": .72, "stamina": 10, "range": 44, "arc": .22, "cooldown": .38, "color": "#91d8df", "rarity": "uncommon", "spell_power": .12},
    "thorn_staff": {"name": "Посох живых терний", "kind": "staff", "damage": 21, "bonus": 27, "charge": .68, "stamina": 11, "range": 46, "arc": .24, "cooldown": .34, "color": "#a2df86", "rarity": "rare", "spell_power": .20},
    "iron_sword": {"name": "Клинок из болотной стали", "kind": "melee", "damage": 27, "bonus": 33, "charge": .66, "stamina": 15, "range": 44, "arc": .30, "cooldown": .31, "color": "#b8d8df", "rarity": "rare"},
    "moonblade": {"name": "Лунный резец", "kind": "melee", "damage": 31, "bonus": 39, "charge": .58, "stamina": 16, "range": 46, "arc": .34, "cooldown": .27, "color": "#b9e9d8", "rarity": "epic"},
    "ember_greatsword": {"name": "Клинок последнего зарева", "kind": "melee", "damage": 43, "bonus": 52, "charge": .78, "stamina": 22, "range": 52, "arc": .22, "cooldown": .44, "color": "#ff9b59", "rarity": "legendary"},
    "starfall_bow": {"name": "Лук звёздного падения", "kind": "bow", "damage": 25, "bonus": 47, "charge": .82, "stamina": 12, "cooldown": .15, "color": "#a8e6db", "rarity": "epic"},
    "frostfang": {"name": "Клык Ледяного змея", "kind": "melee", "damage": 47, "bonus": 58, "charge": .63, "stamina": 20, "range": 50, "arc": .28, "cooldown": .32, "color": "#a9f5ff", "rarity": "legendary"},
    "void_edge": {"name": "Рассекающий разлом", "kind": "melee", "damage": 62, "bonus": 76, "charge": .72, "stamina": 24, "range": 54, "arc": .24, "cooldown": .40, "color": "#d99aff", "rarity": "legendary"},
    # Store weapons must exist in the combat/equipment catalogue as well.
    "daggers": {"name": "Парные клинки теней", "kind": "melee", "damage": 24, "bonus": 27, "charge": .42, "stamina": 12, "range": 36, "arc": .42, "cooldown": .20, "color": "#c5a6ed", "rarity": "rare"},
    "spear": {"name": "Копьё звёздного стража", "kind": "melee", "damage": 32, "bonus": 38, "charge": .74, "stamina": 17, "range": 76, "arc": .18, "cooldown": .37, "color": "#a9d9e8", "rarity": "epic"},
    "scythe": {"name": "Коса жнеца душ", "kind": "melee", "damage": 39, "bonus": 46, "charge": .82, "stamina": 22, "range": 48, "arc": .03, "cooldown": .46, "color": "#a8d7c5", "rarity": "epic"},
    "astral_blade": {"name": "Астральный клинок Вечности", "kind": "melee", "damage": 58, "bonus": 68, "charge": .70, "stamina": 24, "range": 52, "arc": .25, "cooldown": .38, "color": "#d6a7ff", "rarity": "legendary"},
    "archon_staff": {"name": "Посох Первородного Эфира", "kind": "staff", "damage": 34, "bonus": 40, "charge": .70, "stamina": 13, "range": 46, "arc": .22, "cooldown": .34, "color": "#9fe5eb", "rarity": "legendary", "spell_power": .35},
    "stormbrand": {"name": "Клинок Грозового кедра", "kind": "melee", "damage": 36, "bonus": 44, "charge": .60, "stamina": 17, "range": 48, "arc": .25, "cooldown": .28, "color": "#73d5ff", "rarity": "epic"},
    "obsidian_axe": {"name": "Топор Чёрного стекла", "kind": "melee", "damage": 52, "bonus": 65, "charge": .82, "stamina": 24, "range": 54, "arc": .18, "cooldown": .43, "color": "#d19aff", "rarity": "legendary"},
    "sunfall_bow": {"name": "Лук Солнцепада", "kind": "bow", "damage": 34, "bonus": 60, "charge": .78, "stamina": 13, "cooldown": .14, "color": "#ffd274", "rarity": "legendary"},
    "elder_staff": {"name": "Посох Первозданного корня", "kind": "staff", "damage": 42, "bonus": 50, "charge": .68, "stamina": 15, "range": 48, "arc": .22, "cooldown": .32, "color": "#8de29c", "rarity": "legendary", "spell_power": .42},
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
    "obsidian_shell": {"name": "Панцирь чёрного стекла", "defense": 30, "color": "#887090", "rarity": "legendary", "lore": "Осколки обсидиана глушат удары и мерцают в сумраке."},
    "starseer_robe": {"name": "Мантия звёздочёта", "defense": 32, "color": "#d2a4d7", "rarity": "legendary", "lore": "Ткань хранит холодный свет далёких созвездий."},
    "elder_mantle": {"name": "Плащ Первозданного сада", "defense": 36, "color": "#8ec884", "rarity": "legendary", "lore": "Живые корни вплетают в ткань силу древнего леса."},
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
    "void_wraith": {"name": "Призрак Бездны", "hp": 1400, "speed": 48, "damage": 55, "range": 85, "cooldown": 1.4, "xp": 1100, "color": "#7b2cbf", "zone": 6},
    "astral_titan": {"name": "Титан Астральной Бездны", "hp": 4800, "speed": 36, "damage": 95, "range": 140, "cooldown": 2.2, "xp": 4500, "color": "#00f0ff", "zone": 6, "boss": True},
    "obsidian_sentinel": {"name": "Страж чёрного стекла", "hp": 2100, "speed": 38, "damage": 70, "range": 94, "cooldown": 1.8, "xp": 1850, "color": "#86718f", "zone": 7},
    "starseer": {"name": "Звёздочёт Пустоты", "hp": 2650, "speed": 49, "damage": 82, "range": 76, "cooldown": 1.55, "xp": 3100, "color": "#d9a6ef", "zone": 8},
    "ancient_warden": {"name": "Хранитель Первозданного сада", "hp": 7200, "speed": 29, "damage": 108, "range": 148, "cooldown": 2.05, "xp": 7200, "color": "#91cb79", "zone": 8, "boss": True},
}


SHOP_CATALOG = {
    "potion": {"name": "Настойка следопыта", "description": "+48 здоровья", "price": 32, "kind": "potion"},
    "arrows": {"name": "Колчан стрел", "description": "8 стрел", "price": 20, "kind": "arrows"},
    "echo_crystal": {"name": "Эхо-кристаллы", "description": "3 кристалла", "price": 48, "kind": "crystal"},
    "rift_shard": {"name": "Осколок разлома", "description": "1 осколок", "price": 55, "kind": "shard"},
    "iron_sword": {"name": "Клинок из болотной стали", "description": "Редкое оружие", "price": 230, "kind": "weapon"},
    "daggers": {"name": "Парные клинки теней", "description": "Молниеносные парные кинжалы", "price": 310, "kind": "weapon"},
    "spear": {"name": "Копьё звёздного стража", "description": "Дальний выпад и бронебойность", "price": 420, "kind": "weapon"},
    "scythe": {"name": "Коса жнеца душ", "description": "Сокрушительный размах по толпе", "price": 540, "kind": "weapon"},
    "astral_blade": {"name": "Астральный клинок Вечности", "description": "Легендарный меч пустоты", "price": 780, "kind": "weapon"},
    "archon_staff": {"name": "Посох Первородного Эфира", "description": "Посох с усилением чар", "price": 650, "kind": "weapon"},
    "stormbrand": {"name": "Клинок Грозового кедра", "description": "Быстрый клинок с разрядом молнии", "price": 620, "kind": "weapon"},
    "sunfall_bow": {"name": "Лук Солнцепада", "description": "Легендарный лук дальней стражи", "price": 1750, "kind": "weapon"},
    "obsidian_axe": {"name": "Топор Чёрного стекла", "description": "Тяжёлое оружие окраины мира", "price": 2100, "kind": "weapon"},
    "elder_staff": {"name": "Посох Первозданного корня", "description": "Сильная магия и тяжёлый удар", "price": 2300, "kind": "weapon"},
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
    "fireball": {"name": "Огненный шар", "kind": "Огонь", "rarity": 1, "mana": 18, "cooldown": 2.8, "damage": 48, "radius": 100},
    "lightning": {"name": "Молния", "kind": "Молния", "rarity": 2, "mana": 26, "cooldown": 4.5, "damage": 58, "radius": 125},
    "thorns": {"name": "Колючие терни", "kind": "Терни", "rarity": 2, "mana": 23, "cooldown": 6.5, "damage": 17, "radius": 112},
    "heal": {"name": "Исцеление", "kind": "Исцеление", "rarity": 1, "mana": 24, "cooldown": 7.0, "heal": 52, "radius": 125, "unlock_spent": 0, "unlock_level": 1},
    "ice_lance": {"name": "Ледяное копьё", "kind": "Лёд", "rarity": 2, "mana": 30, "cooldown": 4.2, "damage": 72, "radius": 76, "unlock_spent": 90, "unlock_level": 3},
    "arcane_burst": {"name": "Всплеск маны", "kind": "Всплеск", "rarity": 3, "mana": 38, "cooldown": 7.0, "damage": 92, "radius": 148, "unlock_spent": 240, "unlock_level": 5},
    "meteor": {"name": "Метеоритный дождь", "kind": "Звёзды", "rarity": 4, "mana": 58, "cooldown": 12.0, "damage": 132, "radius": 172, "unlock_spent": 500, "unlock_level": 8},
    "frost_nova": {"name": "Кольцо инея", "kind": "Лёд", "rarity": 2, "mana": 32, "cooldown": 8.0, "damage": 65, "radius": 142, "unlock_spent": 320, "unlock_level": 6},
    "shadow_bolt": {"name": "Сумрачный снаряд", "kind": "Тень", "rarity": 2, "mana": 28, "cooldown": 3.2, "damage": 64, "radius": 62, "unlock_spent": 160, "unlock_level": 4},
}

MANA_GROWTH_COEF, MANA_GROWTH_CAP = 1.15, 90
ELEMENT_FX = {
    "Огонь": {"colors": ["#ff552e", "#ffb347", "#fff2a8"], "shape": "flame", "burst": "spiral"},
    "Лёд": {"colors": ["#40d9ff", "#a4f3ff", "#ffffff"], "shape": "crystal", "burst": "shards"},
    "Молния": {"colors": ["#fff05a", "#6beaff", "#ffffff"], "shape": "bolt", "burst": "fork"},
    "Исцеление": {"colors": ["#53dfa0", "#b4ffda", "#ffffff"], "shape": "petal", "burst": "bloom"},
    "Терни": {"colors": ["#61c953", "#b5ef7a", "#efffd0"], "shape": "thorn", "burst": "spikes"},
    "Яд": {"colors": ["#63e85b", "#caff72", "#ffffb4"], "shape": "droplet", "burst": "cloud"},
    "Звёзды": {"colors": ["#ff9940", "#ffe878", "#ffffff"], "shape": "star", "burst": "meteor"},
    "Тень": {"colors": ["#8e62ed", "#d1a4ff", "#fff0ff"], "shape": "orb", "burst": "eclipse"},
    "Эхо": {"colors": ["#4bd7d0", "#a8fff0", "#ffffff"], "shape": "ring", "burst": "wave"},
    "Душа": {"colors": ["#fa77c9", "#ffc5eb", "#ffffff"], "shape": "wisp", "burst": "bloom"},
    "Аркана": {"colors": ["#bd77ff", "#6edfff", "#fff1c8"], "shape": "rune", "burst": "runes"},
    "Всплеск": {"colors": ["#bd75ff", "#f09cff", "#fff0ff"], "shape": "pulse", "burst": "pulse"},
}
POWER_SITES = [
    {"id": "spring", "name": "Источник живой воды", "x": 2050, "y": 850, "radius": 170, "buff": "Восстановление здоровья +2/с"},
    {"id": "root", "name": "Сердце древнего леса", "x": 3300, "y": 1750, "radius": 180, "buff": "Восстановление маны +3/с"},
    {"id": "ember", "name": "Жар пепельной кузни", "x": 5000, "y": 900, "radius": 170, "buff": "Выносливость +4/с"},
    {"id": "glacier", "name": "Кристалл синего пламени", "x": 6400, "y": 3900, "radius": 170, "buff": "Здоровье и мана +1.5/с"},
    {"id": "echo", "name": "Алтарь эха", "x": 8800, "y": 2500, "radius": 190, "buff": "Все ресурсы восстанавливаются быстрее"},
    {"id": "obsidian", "name": "Осколок чёрного стекла", "x": 10350, "y": 5700, "radius": 200, "buff": "Все ресурсы восстанавливаются быстрее"},
    {"id": "garden", "name": "Сердце Первозданного сада", "x": 11800, "y": 1800, "radius": 210, "buff": "Здоровье, мана и выносливость +3/с"},
]



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
            "boss": bool(spec.get("boss") or kind == "colossus")}


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
        "abyss": [("void_wraith", 8, 21), ("astral_titan", 1, 25)],
        "obsidian": [("obsidian_sentinel", 7, 27), ("void_wraith", 5, 28), ("obsidian_sentinel", 1, 30)],
        "garden": [("starseer", 7, 31), ("ancient_warden", 1, 35), ("starseer", 5, 33)],
    }
    for zone_id, packs in population.items():
        zone = next(z for z in ZONES if z["id"] == zone_id)
        for kind, count, level in packs:
            for _ in range(count):
                idx += 1
                x = random.uniform(zone["x0"] + 90, zone["x1"] - 90)
                y = random.uniform(130, WORLD_H - 130)
                mobs.append(scaled_mob(kind, level + random.choice([0, 0, 1]), idx, x, y))
    for i in range(190):
        x = random.uniform(100, WORLD_W - 100)
        zone = zone_for_x(x)
        roll = random.random()
        if zone["id"] == "camp":
            kind = "herb" if roll < .6 else "wood"
        elif zone["id"] == "forest":
            kind = "wood" if roll < .42 else "herb" if roll < .78 else "ore"
        elif zone["id"] == "marsh":
            kind = "herb" if roll < .25 else "ore" if roll < .78 else "crystal"
        elif zone["id"] in {"rift", "abyss", "obsidian", "garden"}:
            kind = "shard" if roll < .48 else "crystal" if roll < .82 else "ore" if roll < .96 else "herb"
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


@app.get("/api/auth/me")
async def auth_me(request: Request) -> dict[str, Any]:
    account = _account_for_token(request.cookies.get("echo_session"))
    return {"authenticated": bool(account), "username": account["username"] if account else None}


@app.post("/api/auth/register")
async def auth_register(request: Request, response: Response) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Не удалось прочитать форму.")
    username, username_key, password = _credentials(payload)
    salt = secrets.token_bytes(16)
    digest = _password_hash(password, salt)
    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute(
                "INSERT INTO user_accounts(username_key, username, salt, password_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (username_key, username, salt.hex(), digest.hex(), int(time.time()))
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Это имя уже занято. Выберите другое или войдите.")
    _issue_session(username_key, request, response)
    return {"ok": True, "username": username}


@app.post("/api/auth/login")
async def auth_login(request: Request, response: Response) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Не удалось прочитать форму.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Некорректные данные формы.")
    username = str(payload.get("username", "")).strip()
    password = payload.get("password", "")
    if not username or not isinstance(password, str) or len(password) > 128:
        raise HTTPException(status_code=401, detail="Неверное имя пользователя или пароль.")
    username_key = username.casefold()
    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute(
            "SELECT salt, password_hash, username FROM user_accounts WHERE username_key=?",
            (username_key,)
        ).fetchone()
    if not row:
        # Match the password-hash cost to reduce username enumeration by timing.
        _password_hash(password or "invalid", bytes(16))
        raise HTTPException(status_code=401, detail="Неверное имя пользователя или пароль.")
    salt = bytes.fromhex(row[0])
    if not hmac.compare_digest(_password_hash(password, salt).hex(), row[1]):
        raise HTTPException(status_code=401, detail="Неверное имя пользователя или пароль.")
    _issue_session(username_key, request, response)
    return {"ok": True, "username": row[2]}


@app.post("/api/auth/logout")
async def auth_logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get("echo_session")
    if token:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute("DELETE FROM auth_sessions WHERE token_hash=?", (token_hash,))
    response.delete_cookie("echo_session", path="/", httponly=True, samesite="strict",
                           secure=request.url.scheme == "https")
    return {"ok": True}


def quest_data(p: dict[str, Any]) -> dict[str, Any]:
    return {"stage": p["quest_stage"], "total": len(QUESTS), "active": p["quest_active"],
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
            "stat_values": {key: int(p["stats"].get(key, 1)) for key in stat_names},
            "upgrades_view": upgrades_view(p),
            "mana_growth": mana_growth_bonus(p), "mana_growth_next": mana_growth_next(p),
            "stats_revision": int(p.get("stats_revision", 0)),
            "gold": p["gold"], "kills": p["kills"], "quest": quest_data(p),
            "respawning": p["respawn_at"] > now, "weapons": list(p["weapons"]), "weapon": p["weapon"],
            "gear": p["gear"], "gear_inventory": list(p["gear_inventory"]),
            "enchantments": p.get("enchantments", {"weapon": {}, "gear": {}}),
            "mana": round(p.get("mana", 0), 1), "max_mana": p.get("max_mana", 0),
            "mana_regen_level": int(p.get("mana_regen_level", 0)),
            "magic_damage_level": int(p.get("magic_damage_level", 0)),
            "magic_damage_bonus": int(p.get("magic_damage_level", 0)) * 8,
            "shop_catalog": SHOP_CATALOG, "sell_prices": SELL_PRICES, "enchant_catalog": ENCHANT_CATALOG,
            "spell_catalog": all_spells(p), "spells_unlocked": [sid for sid in all_spells(p) if spell_unlocked(p, sid)],
            "spell_uses": dict(p.get("spell_uses", {})),
            "spell_levels": {sid: spell_mastery_level(p, sid) for sid in all_spells(p)},
            "custom_spells": [{**spell, "id": spell_id, "spell_id": spell_id}
                              for spell_id, spell in p.get("custom_spells", {}).items()
                              if isinstance(spell, dict)],
            "spell_cooldowns": {sid: {"remaining": max(0.0, round(until - now, 2)), "total": spell_cooldown_seconds(p, sid)}
                                for sid, until in p.get("spell_cooldowns", {}).items()},
            "magic_mana_spent": int(p.get("magic_mana_spent", 0)),
            "upgrades": p.get("upgrades", {"weapon": {}, "gear": {}}),
            "weapon_sell_prices": {key: weapon_sell_price(key) for key in p["weapons"]},
            "gear_sell_prices": {key: gear_sell_price(key) for key in [p["gear"], *p["gear_inventory"]]},
            "gear_catalog": GEAR,
            "weapon_catalog": {key: {"name": value["name"], "rarity": value.get("rarity", "common"),
                                     "damage": value["damage"], "bonus": value.get("bonus", 0),
                                     "kind": value["kind"], "charge": value.get("charge", .7), "range": value.get("range", 420),
                                     "arc": value.get("arc", .28), "spell_power": value.get("spell_power", 0),
                                     "upgrade": item_upgrade_level(p, "weapon", key)}
                               for key, value in WEAPONS.items()},
            "inventory": dict(p["inventory"]), "attack": action,
            "gathering": p["gathering"] is not None, "gather_progress": (p["gathering"]["progress"] / 1.15 if p["gathering"] else 0), "zone": zone["id"],
            "dodge_ready": now >= p["dodge_at"]}


def snapshot(for_id: str) -> dict[str, Any]:
    now = time.monotonic()
    return {"type": "state", "you": for_id, "world": {"w": WORLD_W, "h": WORLD_H},
            "zones": ZONES, "elements": ELEMENT_FX, "power_sites": POWER_SITES,
            "players": [player_row(pid, p, now) for pid, p in players.items()],
            "mobs": [{**{k: mob[k] for k in ("id", "kind", "level", "x", "y", "hp", "max_hp", "boss")},
                      "telegraphing": mob["telegraph_until"] > now}
                     for mob in mobs if mob["hp"] > 0],
            "nodes": [{k: n[k] for k in ("id", "kind", "x", "y", "active", "zone")} for n in nodes],
            "arrows": [{k: a[k] for k in ("x", "y", "vx", "vy", "life", "kind", "radius", "spell_id", "spell_kind", "spell_rarity", "spell_mastery", "spell_variant", "spell_palette", "max_distance", "travelled") if k in a} for a in arrows],
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


async def sync_station_state(p: dict[str, Any]) -> None:
    """Persist station transactions and immediately refresh the player's client."""
    save_character(p)
    pid = str(p.get("id", ""))
    await send_event({"type": "player_update", "target": pid,
                      "player": player_row(pid, p, time.monotonic())})


def mana_growth_bonus(p: dict[str, Any]) -> int:
    spent = max(0, int(p.get("magic_mana_spent", 0)))
    return min(MANA_GROWTH_CAP, int(MANA_GROWTH_COEF * math.sqrt(spent)))


def mana_growth_next(p: dict[str, Any]) -> int:
    """Spent mana required to reach the next integer bonus point."""
    current = mana_growth_bonus(p)
    if current >= MANA_GROWTH_CAP:
        return 0
    spent = max(0, int(p.get("magic_mana_spent", 0)))
    target = current + 1
    candidate = max(spent + 1, math.ceil((target / MANA_GROWTH_COEF) ** 2))
    while int(MANA_GROWTH_COEF * math.sqrt(candidate)) < target:
        candidate += 1
    return candidate


def upgrades_view(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stats = p.get("stats", {})
    return {
        "might": {"level": int(stats.get("might", 1)), "effect": f"+{(int(stats.get('might', 1))-1)*2.2:.1f} к урону оружия"},
        "vitality": {"level": int(stats.get("vitality", 1)), "effect": f"{int(p.get('max_hp', 100))} макс. здоровья"},
        "agility": {"level": int(stats.get("agility", 1)), "effect": f"{int(p.get('max_stamina', 100))} макс. выносливости"},
        "mana_regen": {"level": int(p.get("mana_regen_level", 0)), "effect": f"+{9 + 1.5*int(p.get('mana_regen_level', 0)):.1f} маны/с"},
        "magic_damage": {"level": int(p.get("magic_damage_level", 0)), "effect": f"+{int(p.get('magic_damage_level', 0))*8}% урона заклинаний"},
        "precision": {"level": int(stats.get("precision", 1)), "effect": f"+{min(30, (int(stats.get('precision', 1))-1)*2.5):.1f}% шанс критического удара"},
        "fortune": {"level": int(stats.get("fortune", 1)), "effect": f"+{min(20, (int(stats.get('fortune', 1))-1)*2.5):.1f}% шанс редкой добычи"},
    }



def stats_updated_event(pid: str, p: dict[str, Any]) -> dict[str, Any]:
    """Build one authoritative update for the characteristics panel."""
    return {
        "type": "stats_updated", "target": pid,
        "stats": {key: int(p.get("stats", {}).get(key, 1)) for key in stat_names},
        "stat_values": {key: int(p.get("stats", {}).get(key, 1)) for key in stat_names},
        "skill_points": max(0, int(p.get("skill_points", 0))),
        "xp": max(0, int(p.get("xp", 0))),
        "level": max(1, int(p.get("level", 1))),
        "mana_regen_level": max(0, int(p.get("mana_regen_level", 0))),
        "magic_damage_level": max(0, int(p.get("magic_damage_level", 0))),
        "upgrades_view": upgrades_view(p),
        "hp": p.get("hp", 0), "max_hp": p.get("max_hp", 0),
        "mana": p.get("mana", 0), "max_mana": p.get("max_mana", 0),
        "stamina": p.get("stamina", 0), "max_stamina": p.get("max_stamina", 0),
        "mana_growth": mana_growth_bonus(p), "mana_growth_next": mana_growth_next(p),
        "stats_revision": int(p.get("stats_revision", 0)),
    }


def update_derived(p: dict[str, Any], heal: bool = False) -> None:
    old_hp = p["max_hp"]
    old_stamina = p["max_stamina"]
    p["max_hp"] = 100 + (p["level"] - 1) * 7 + (p["stats"]["vitality"] - 1) * 12
    p["max_stamina"] = 100 + (p["stats"]["agility"] - 1) * 5 + (p["stats"]["might"] - 1) * 2
    previous_max_mana = p.get("max_mana", 60)
    p["max_mana"] = (60 + (p["level"] - 1) * 5 + (p["stats"]["vitality"] - 1) * 3
                     + int(p.get("mana_regen_level", 0)) * 2 + mana_growth_bonus(p))
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
        p["stats_revision"] = int(p.get("stats_revision", 0)) + 1
        # XP/skill points can change while the player stays in the same session.
        # Push the authoritative values immediately; snapshots remain the fallback.
        for pid, current in list(players.items()):
            if current is p:
                try:
                    asyncio.get_running_loop().create_task(send_event(stats_updated_event(pid, p)))
                except RuntimeError:
                    pass
                break
        asyncio.create_task(send_event({"type": "notice", "text": f"{p['name']} достиг(ла) {p['level']} уровня — доступно очко развития"}))


QUESTS = [
    ("slime", 4, "herb", 3, "Очистить опушку"), ("wolf", 3, "ore", 4, "Следы в топи"),
    ("boar", 3, "crystal", 3, "Свет под водой"), ("colossus", 1, "", 0, "Пепельный колосс"),
    ("frost_wyrm", 4, "crystal", 6, "Синий хребет"), ("echo_dragon", 1, "shard", 8, "Разлом Эха"),
    ("rift_knight", 4, "shard", 6, "Стражи разлома"), ("echo_dragon", 2, "crystal", 12, "Сердце пустоты"),
    ("void_wraith", 5, "shard", 12, "Угольный след"), ("obsidian_sentinel", 5, "ore", 18, "Ключ из чёрного стекла"),
    ("starseer", 4, "crystal", 20, "Охота на звёздочёта"), ("starseer", 5, "herb", 22, "Корни под звёздами"),
    ("ancient_warden", 1, "shard", 30, "Страж Первозданного сада"),
]
QUEST_REWARDS = [
    (45, 100, [("potion", "potion", 2)]), (90, 220, [("gear", "wolf_cloak", 1)]),
    (145, 360, [("gear", "marsh_armor", 1)]), (260, 700, [("gear", "ash_plate", 1)]),
    (420, 1000, [("gear", "ash_plate", 1)]), (700, 1600, [("gear", "ash_plate", 1)]),
    (950, 2200, [("weapon", "frostfang", 1)]), (1400, 3200, [("weapon", "void_edge", 1)]),
    (1700, 3800, [("gear", "obsidian_shell", 1)]), (2100, 4600, [("weapon", "obsidian_axe", 1)]),
    (2500, 5600, [("gear", "starseer_robe", 1)]), (3200, 7200, [("weapon", "sunfall_bow", 1)]),
    (5000, 12000, [("gear", "elder_mantle", 1), ("weapon", "elder_staff", 1)]),
]


def quest_requirements(stage: int) -> tuple[str, int, str, int, str]:
    return QUESTS[min(max(0, int(stage)), len(QUESTS) - 1)]


def quest_complete(p: dict[str, Any]) -> bool:
    stage = int(p.get("quest_stage", 0))
    if stage >= len(QUESTS): return False
    mob, mob_n, resource, resource_n, _ = quest_requirements(stage)
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
        gold, xp, rewards = QUEST_REWARDS[stage]
        p["gold"] += gold
        add_xp(p, xp)
        for reward_type, item_id, amount in rewards:
            if reward_type == "potion": p["inventory"]["potion"] += amount
            elif reward_type == "gear":
                for _ in range(amount): grant_gear(p, item_id)
            elif reward_type == "weapon":
                for _ in range(amount): grant_weapon(p, item_id)
        await tell(p["id"], f"Поручение завершено. Получено {gold} монет, {xp} опыта и награда следопыту.")
    elif p["quest_active"]:
        await tell(p["id"], "Поручение ещё не выполнено. Загляни в журнал.")
    elif p["quest_stage"] >= len(QUESTS):
        await tell(p["id"], "Ты завершил историю Леса Эха и спас Первозданный сад.")
    else:
        p["quest_active"] = True
        p["quest_kills"] = {}
        p["quest_gather"] = {}
        _, _, _, _, title = quest_requirements(p["quest_stage"])
        await tell(p["id"], f"Новое поручение: {title}. Цели отмечены в журнале.")


def loot_chance(p: dict[str, Any], base_chance: float) -> bool:
    luck = max(0, int(p.get("stats", {}).get("fortune", 1)) - 1)
    bonus = min(.20, luck * .025)
    return random.random() < min(.95, base_chance + bonus)


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
        if loot_chance(p, .12): grant_gear(p, random.choice(["wolf_cloak", "moss_guard"]))
        if loot_chance(p, .025): grant_weapon(p, "moonblade")
    elif kind == "boar":
        inv["hide"] += 2; inv["ore"] += 1
    elif kind == "wisp":
        inv["crystal"] += random.randint(1, 2); inv["herb"] += 1
    elif kind == "stone":
        inv["ore"] += random.randint(2, 4)
        if loot_chance(p, .18): grant_gear(p, random.choice(["marsh_armor", "moonweave"]))
        if loot_chance(p, .035): grant_weapon(p, random.choice(["moonblade", "starfall_bow"]))
    elif kind == "ashling":
        inv["crystal"] += random.randint(1, 2); inv["ore"] += 1
        inv["shard"] += 1
    elif kind == "ashguard":
        inv["crystal"] += 3; inv["ore"] += 3; inv["shard"] += random.randint(2, 3)
        if loot_chance(p, .35): grant_gear(p, random.choice(["ash_plate", "colossus_core"]))
        if loot_chance(p, .08): grant_weapon(p, random.choice(["ember_greatsword", "starfall_bow"]))
    elif kind == "colossus":
        inv["crystal"] += 12; inv["ore"] += 10; inv["shard"] += 10
        grant_gear(p, "colossus_core")
        grant_weapon(p, "ember_greatsword")
    elif kind == "frost_wyrm":
        inv["crystal"] += 4; inv["shard"] += random.randint(2, 4)
        if loot_chance(p, .12): grant_gear(p, "glacier_mantle")
        if loot_chance(p, .045): grant_weapon(p, "frostfang")
    elif kind == "rift_knight":
        inv["crystal"] += 6; inv["shard"] += random.randint(3, 5)
        if loot_chance(p, .20): grant_gear(p, "rift_plate")
        if loot_chance(p, .06): grant_weapon(p, "void_edge")
    elif kind == "echo_dragon":
        inv["crystal"] += 30; inv["shard"] += 24
        grant_gear(p, "rift_plate")
        grant_weapon(p, "void_edge")
    elif kind == "void_wraith":
        inv["crystal"] += random.randint(1, 3); inv["shard"] += random.randint(2, 5)
        if loot_chance(p, .08): grant_weapon(p, "stormbrand")
    elif kind == "astral_titan":
        inv["crystal"] += 28; inv["shard"] += 32
        grant_gear(p, "obsidian_shell"); grant_weapon(p, "obsidian_axe")
    elif kind == "obsidian_sentinel":
        inv["ore"] += random.randint(3, 6); inv["crystal"] += random.randint(2, 4); inv["shard"] += random.randint(1, 3)
        if loot_chance(p, .14): grant_gear(p, "obsidian_shell")
        if loot_chance(p, .09): grant_weapon(p, "obsidian_axe")
    elif kind == "starseer":
        inv["crystal"] += random.randint(4, 7); inv["shard"] += random.randint(3, 6)
        if loot_chance(p, .16): grant_gear(p, "starseer_robe")
        if loot_chance(p, .08): grant_weapon(p, "sunfall_bow")
    elif kind == "ancient_warden":
        inv["herb"] += 8; inv["crystal"] += 18; inv["shard"] += 20
        grant_gear(p, "elder_mantle"); grant_weapon(p, "elder_staff")
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
    weapon_upgrade = item_upgrade_level(p, "weapon", weapon_id)
    # A staff's forge upgrade is reserved for spells, never its close-range swing.
    physical_upgrade = 0 if spec["kind"] == "staff" else 6 * weapon_upgrade
    base_damage = (spec["damage"] + spec["bonus"] * charge + power_bonus
                   + 8 * enchant_level(p, "weapon", weapon_id, "sharpness")
                   + physical_upgrade)
    crit_chance = min(.30, max(0, (int(p.get("stats", {}).get("precision", 1)) - 1) * .025))
    critical = random.random() < crit_chance
    damage = round(base_damage * (1.75 if critical else 1.0))
    if spec["kind"] == "bow":
        if p["inventory"]["arrows"] <= 0:
            asyncio.create_task(tell(p["id"], "Колчан пуст. Стрелы можно изготовить из дерева и руды."))
            return
        p["inventory"]["arrows"] -= 1
        asyncio.create_task(send_event({"type": "weapon_action", "action": "attack", "id": p["id"],
                                        "weapon": weapon_id, "weapon_kind": spec["kind"],
                                        "x": p["x"], "y": p["y"], "aim_x": ax, "aim_y": ay,
                                        "charge": charge}))
        charge_factor = .22 + .78 * charge
        speed = 210 + 500 * charge + (p["stats"]["agility"] - 1) * 8
        arrow_range = 180 + 620 * charge
        charged_damage = max(1, round(damage * charge_factor))
        arrows.append({"x": p["x"] + ax * 18, "y": p["y"] + ay * 18,
                       "vx": ax * speed, "vy": ay * speed, "damage": charged_damage,
                       "owner": p["id"], "life": arrow_range / max(1, speed),
                       "max_distance": arrow_range, "travelled": 0.0, "kind": "arrow", "critical": critical})
        return
    asyncio.create_task(send_event({"type": "weapon_action", "action": "attack", "id": p["id"],
                                    "weapon": weapon_id, "weapon_kind": spec["kind"],
                                    "x": p["x"], "y": p["y"], "aim_x": ax, "aim_y": ay,
                                    "charge": charge}))
    reach = float(spec.get("range", 44)) + 12 * charge
    hits = []
    for mob in mobs:
        if mob["hp"] <= 0: continue
        dx, dy = mob["x"] - p["x"], mob["y"] - p["y"]
        dist = math.hypot(dx, dy)
        if dist <= reach and dist > .01 and (dx * ax + dy * ay) / dist >= spec["arc"]:
            hits.append((dist, mob))
    hits.sort(key=lambda row: row[0])
    max_hits = 5 if weapon_id == "scythe" else 4 if weapon_id in ("axe", "astral_blade", "obsidian_axe") else 3 if weapon_id in ("iron_sword", "archon_staff", "elder_staff") else 2 if weapon_id in ("spear", "daggers", "stormbrand") else 1
    for _, mob in hits[:max_hits]:
        mob["hp"] -= damage
        vampirism = enchant_level(p, "weapon", weapon_id, "vampirism")
        if vampirism: p["hp"] = min(p["max_hp"], p["hp"] + round(damage * .06 * vampirism))
        mob["alert_until"] = now + 4
        if mob["hp"] <= 0:
            mob["hp"] = 0
            mob["respawn_at"] = now + random.uniform(24, 40)
            award_drop(p, mob)
        asyncio.create_task(send_event({"type": "hit", "mob": mob["id"], "x": mob["x"], "y": mob["y"], "damage": round(damage), "critical": critical}))
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
            if dist <= reach and dist > .01 and (dx * ax + dy * ay) / dist >= spec["arc"]:
                candidates.append((dist, other))
        candidates.sort(key=lambda row: row[0])
        for _, other in candidates[:max_hits]:
            defense = player_defense(other)
            actual = max(1, round(damage * .72) - defense)
            other["hp"] = max(0, other["hp"] - actual)
            asyncio.create_task(send_event({"type": "pvp_hit", "attacker": p["id"], "id": other["id"],
                                            "damage": actual, "x": other["x"], "y": other["y"], "critical": critical}))
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
FORGE_SUCCESS_CHANCES = (1.00, 0.90, 0.80, 0.70, 0.60)


def all_spells(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = dict(SPELLS)
    custom = p.get("custom_spells", {})
    if isinstance(custom, dict):
        for spell_id, spell in custom.items():
            if isinstance(spell, dict) and str(spell_id).startswith("custom_"):
                catalog[str(spell_id)] = spell
    return catalog


def spell_unlocked(p: dict[str, Any], spell_id: str) -> bool:
    spec = all_spells(p).get(spell_id)
    return bool(spec and p.get("level", 1) >= spec.get("unlock_level", 1)
                and p.get("magic_mana_spent", 0) >= spec.get("unlock_spent", 0))


def spell_mastery_level(p: dict[str, Any], spell_id: str) -> int:
    uses = max(0, int(p.get("spell_uses", {}).get(spell_id, 0)))
    return min(6, 1 + uses // 5)


def spell_cooldown_seconds(p: dict[str, Any], spell_id: str) -> float:
    spec = all_spells(p).get(spell_id, {})
    mastery = spell_mastery_level(p, spell_id)
    return round(float(spec.get("cooldown", 0)) * (1 - .04 * (mastery - 1)), 2)


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
        elif kind == "weapon": p["weapons"].append(item_id)
        elif kind == "gear": p["gear_inventory"].append(item_id)
        await sync_station_state(p)
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
        await apply_enchantment(p, item_id, str(msg.get("item_id", "")) or None)
        return
    await tell(p["id"], "Неизвестная операция лавки.")

async def apply_enchantment(p: dict[str, Any], enchant_id: str, selected_item: str | None = None) -> None:
    if math.hypot(p["x"] - WIZARD_X, p["y"] - WIZARD_Y) > 420:
        await tell(p["id"], "Подойди к волшебнику у святилища в лагере."); return
    spec = ENCHANT_CATALOG.get(enchant_id)
    if not spec:
        await tell(p["id"], "Такого зачарования нет."); return
    target = spec["target"]
    catalog = WEAPONS if target == "weapon" else GEAR
    item_id = selected_item or (p.get("weapon") if target == "weapon" else p.get("gear"))
    owned = item_id in p.get("weapons", []) if target == "weapon" else (item_id == p.get("gear") or item_id in p.get("gear_inventory", []))
    if item_id not in catalog or not owned:
        await tell(p["id"], "Выбранный предмет не принадлежит персонажу."); return
    current = enchant_level(p, target, item_id, enchant_id)
    if current >= ENCHANT_MAX_LEVEL:
        await tell(p["id"], "Это зачарование уже достигло максимального уровня."); return
    price = 70 + current * 85
    crystal_cost = 1 + current
    inv = p["inventory"]
    if p["gold"] < price or inv.get("crystal", 0) < crystal_cost:
        await tell(p["id"], f"Нужно {price} монет и {crystal_cost} эхо-кристалл(а). Сейчас: {p['gold']} монет, {inv.get('crystal', 0)} кристаллов."); return
    p["gold"] -= price
    inv["crystal"] -= crystal_cost
    p.setdefault("enchantments", {}).setdefault(target, {}).setdefault(item_id, {})[enchant_id] = current + 1
    await sync_station_state(p)
    await tell(p["id"], f"Зачарование «{spec['name']}» {current + 1}-го уровня наложено на {catalog[item_id]['name']}. Списано: {price} монет и {crystal_cost} эхо-кристалл(а).")


async def forge_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    if math.hypot(p["x"] - FORGE_X, p["y"] - FORGE_Y) > 420:
        await tell(p["id"], "Подойди к кузнице у восточной тропы в лагере."); return
    action, recipe_id = str(msg.get("action", "")), str(msg.get("id", ""))
    inv = p["inventory"]
    if action == "craft":
        recipes = {
            "forest_bow": ({"wood": 8, "hide": 3, "ore": 2}, "Лук следопыта"),
            "thorn_staff": ({"wood": 6, "crystal": 5, "herb": 4}, "Посох живых терний"),
            "stormbrand": ({"ore": 8, "crystal": 4, "shard": 3}, "Клинок Грозового кедра"),
            "obsidian_axe": ({"ore": 14, "crystal": 10, "shard": 12, "hide": 4}, "Топор Чёрного стекла"),
            "elder_staff": ({"wood": 16, "crystal": 12, "shard": 8, "herb": 6}, "Посох Первозданного корня"),
        }
        recipe = recipes.get(recipe_id)
        if not recipe:
            await tell(p["id"], "Такого чертежа в кузнице нет."); return
        cost, display_name = recipe
        if recipe_id in p["weapons"]:
            await tell(p["id"], f"{display_name} уже изготовлен."); return
        if any(inv.get(k, 0) < v for k, v in cost.items()):
            await tell(p["id"], "Не хватает материалов для изготовления."); return
        for key, value in cost.items(): inv[key] -= value
        p["weapons"].append(recipe_id)
        await sync_station_state(p)
        await tell(p["id"], f"{display_name} изготовлен. Материалы списаны, предмет добавлен в рюкзак."); return

    target = "weapon" if action == "upgrade_weapon" else "gear" if action == "upgrade_armor" else ""
    if not target:
        await tell(p["id"], "Неизвестная операция кузницы."); return
    catalog = WEAPONS if target == "weapon" else GEAR
    selected_id = str(msg.get("item_id", ""))
    item_id = selected_id or (p.get("weapon") if target == "weapon" else p.get("gear"))
    owned = item_id in p.get("weapons", []) if target == "weapon" else (item_id == p.get("gear") or item_id in p.get("gear_inventory", []))
    if item_id not in catalog or not owned:
        await tell(p["id"], "Выбранное оружие или броня не найдены в инвентаре."); return
    level = item_upgrade_level(p, target, item_id)
    if level >= MAX_ITEM_UPGRADE:
        await tell(p["id"], "Предмет уже достиг предела +5."); return
    gold_cost = (75 if target == "weapon" else 65) + level * (55 if target == "weapon" else 50)
    ore_cost = 2 + level
    crystal_cost = 0 if level < 2 else 1 + level // 2
    if p["gold"] < gold_cost or inv.get("ore", 0) < ore_cost or inv.get("crystal", 0) < crystal_cost:
        await tell(p["id"], f"Нужно {gold_cost} монет, {ore_cost} руды и {crystal_cost} эхо-кристаллов."); return
    chance = FORGE_SUCCESS_CHANCES[level]
    # Every accepted attempt consumes its displayed costs, success or failure.
    p["gold"] -= gold_cost; inv["ore"] -= ore_cost; inv["crystal"] -= crystal_cost
    success = random.random() < chance
    if success:
        p.setdefault("upgrades", {}).setdefault(target, {})[item_id] = level + 1
    await sync_station_state(p)
    await send_event({
        "type": "forge_result", "target": p["id"], "success": success,
        "upgrade_type": target, "item_id": item_id, "item_name": catalog[item_id]["name"],
        "level_before": level, "level_after": level + (1 if success else 0),
        "chance": round(chance * 100), "gold": int(p["gold"]), "inventory": dict(inv),
        "upgrades": {key: dict(value) for key, value in p.get("upgrades", {}).items()},
        "weapon": p.get("weapon"), "gear": p.get("gear"),
        "benefit": (("+6 к урону заклинаний" if catalog[item_id].get("kind") == "staff"
                     else "+6 к урону стрел" if catalog[item_id].get("kind") == "bow"
                     else "+6 к урону ближней атаки") if target == "weapon" else "+3 защиты"),
        "cost": {"gold": gold_cost, "ore": ore_cost, "crystal": crystal_cost},
    })
    await tell(p["id"], (f"Успех: {catalog[item_id]['name']} улучшено до +{level + 1}." if success
                         else f"Неудача: улучшение не наложено. Списано {gold_cost} монет и {ore_cost} руды."))


async def wizard_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    # Allow the station panel's actions across the camp area; still require a nearby visit.
    if math.hypot(p["x"] - WIZARD_X, p["y"] - WIZARD_Y) > 420:
        await tell(p["id"], "Подойди к синему святилищу волшебника у костра.")
        return
    action, item_id = str(msg.get("action", "")), str(msg.get("id", ""))
    if action == "buy_staff":
        offer_price = 185
        if "apprentice_staff" in p["weapons"]:
            await tell(p["id"], "Посох ученика уже у тебя."); return
        if p["gold"] < offer_price:
            await tell(p["id"], f"Посох стоит {offer_price} монет. Сейчас у тебя {p['gold']}."); return
        p["gold"] -= offer_price; p["weapons"].append("apprentice_staff"); p["weapon"] = "apprentice_staff"
        await sync_station_state(p)
        await tell(p["id"], "Куплен и экипирован посох ученика. Списано 185 монет."); return
    if action == "enchant":
        await apply_enchantment(p, item_id, str(msg.get("item_id", "")) or None)
        return
    await tell(p["id"], "Неизвестная операция волшебника.")


def spell_damage(p: dict[str, Any], mob: dict[str, Any], damage: float, now: float) -> None:
    if mob["hp"] <= 0: return
    dealt = max(1, round(damage)); mob["hp"] -= dealt; mob["alert_until"] = now + 4
    if mob["hp"] <= 0:
        mob["hp"] = 0; mob["respawn_at"] = now + random.uniform(24, 40); award_drop(p, mob)
    try: asyncio.create_task(send_event({"type": "hit", "mob": mob["id"], "x": mob["x"], "y": mob["y"], "damage": dealt}))
    except RuntimeError: pass

def spell_visual(p: dict[str, Any], spell_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    mastery = spell_mastery_level(p, spell_id)
    kind = str(spec.get("kind", "Аркана"))
    palette = ELEMENT_FX.get(kind, ELEMENT_FX["Аркана"])
    stable = f"{spell_id}:{p.get('id', '')}:{int(p.get('spell_uses', {}).get(spell_id, 0))}"
    variant = int(hashlib.sha256(stable.encode("utf-8")).hexdigest()[:8], 16) % 1000000
    return {"mastery": mastery, "variant": variant, "palette": palette}


def spell_fx_event(p: dict[str, Any], spell_id: str, spec: dict[str, Any], x: float, y: float) -> dict[str, Any]:
    return {"type": "spell_fx", "spell": spell_id, "x": x, "y": y,
            "radius": spec.get("radius", 100), "owner": p.get("id"),
            "kind": spec.get("kind", spell_id), "name": spec.get("name", spell_id),
            "rarity": spec.get("rarity", 1), **spell_visual(p, spell_id, spec)}


async def cast_spell(p: dict[str, Any], now: float, spell_id: str, aim_x: float, aim_y: float,
                     target_x: float | None = None, target_y: float | None = None) -> None:
    catalog = all_spells(p)
    spec = catalog.get(spell_id)
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
    max_cast_range = float(spec.get("cast_range", 420))
    if dist > max_cast_range:
        tx, ty = p["x"] + dx / dist * max_cast_range, p["y"] + dy / dist * max_cast_range
    dx, dy = tx - p["x"], ty - p["y"]
    dist = math.hypot(dx, dy)
    if dist > .01:
        aim_x, aim_y = dx / dist, dy / dist
    tx, ty = max(0.0, min(WORLD_W, tx)), max(0.0, min(WORLD_H, ty))
    p["mana"] -= spec["mana"]
    p.setdefault("spell_uses", {})[spell_id] = int(p.get("spell_uses", {}).get(spell_id, 0)) + 1
    cooldowns[spell_id] = now + spell_cooldown_seconds(p, spell_id)
    old_spent = int(p.get("magic_mana_spent", 0))
    p["magic_mana_spent"] = old_spent + int(spec["mana"])
    equipped_weapon = WEAPONS.get(p.get("weapon", ""), {})
    staff_power = float(equipped_weapon.get("spell_power", 0))
    staff_upgrade = (6 * item_upgrade_level(p, "weapon", p.get("weapon", ""))
                     if equipped_weapon.get("kind") == "staff" else 0)
    power = 1.0 + staff_power + 0.08 * int(p.get("magic_damage_level", 0))
    spell_damage_base = float(spec.get("damage", 0)) + staff_upgrade
    update_derived(p)
    for unlocked_id, unlocked_spec in catalog.items():
        threshold = int(unlocked_spec.get("unlock_spent", 0))
        if threshold and old_spent < threshold <= p["magic_mana_spent"]:
            asyncio.create_task(tell(p["id"], f"Открыто заклинание «{unlocked_spec['name']}»! Требуется также уровень {unlocked_spec['unlock_level']}."))
    p["face_x"], p["face_y"] = aim_x, aim_y
    weapon_spec = WEAPONS.get(p.get("weapon", ""), {})
    await send_event({"type": "weapon_action", "action": "cast", "id": p["id"],
                      "weapon": p.get("weapon", ""), "weapon_kind": weapon_spec.get("kind", "melee"),
                      "x": p["x"], "y": p["y"], "aim_x": aim_x, "aim_y": aim_y,
                      "spell": spell_id})
    visual = spell_visual(p, spell_id, spec)
    if spell_id in {"fireball", "ice_lance", "meteor", "shadow_bolt"} or spec.get("crafted") and spec.get("kind") in {"Огонь", "Лёд", "Тень", "Аркана"}:
        distance = max(1.0, math.hypot(tx - p["x"], ty - p["y"]))
        speed = 420 if spell_id == "fireball" else 500 if spell_id in {"ice_lance", "shadow_bolt"} else 250
        arrows.append({"x": p["x"] + aim_x * 18, "y": p["y"] + aim_y * 18,
                       "vx": (tx - p["x"]) / distance * speed, "vy": (ty - p["y"]) / distance * speed,
                       "damage": round(spell_damage_base * power), "owner": p["id"],
                       "life": distance / speed + .08, "max_distance": distance, "travelled": 0.0, "kind": "spell_projectile",
                       "spell_id": spell_id, "spell_kind": spec.get("kind", spell_id), "spell_name": spec.get("name", spell_id),
                       "spell_rarity": spec.get("rarity", 1), "spell_mastery": visual["mastery"],
                       "spell_variant": visual["variant"], "spell_palette": visual["palette"], "radius": spec["radius"]})
    elif spell_id == "lightning" or spec.get("crafted") and spec.get("kind") in {"Молния", "Эхо", "Звёзды"}:
        candidates = sorted((m for m in mobs if m["hp"] > 0 and math.hypot(m["x"] - tx, m["y"] - ty) <= spec["radius"]),
                           key=lambda m: math.hypot(m["x"] - tx, m["y"] - ty))
        for index, mob in enumerate(candidates[:4]): spell_damage(p, mob, spell_damage_base * power * (0.72 ** index), now)
        await send_event(spell_fx_event(p, spell_id, spec, tx, ty))
    elif spell_id == "frost_nova" or spec.get("crafted") and spec.get("kind") == "Лёд":
        for mob in mobs:
            if mob["hp"] > 0 and math.hypot(mob["x"] - p["x"], mob["y"] - p["y"]) <= spec["radius"]:
                spell_damage(p, mob, spell_damage_base * power, now)
        await send_event(spell_fx_event(p, spell_id, spec, p["x"], p["y"]))
    elif spell_id == "arcane_burst" or spec.get("crafted") and spec.get("kind") == "Всплеск":
        for mob in mobs:
            distance = math.hypot(mob["x"] - tx, mob["y"] - ty)
            if mob["hp"] > 0 and distance <= spec["radius"]:
                spell_damage(p, mob, spell_damage_base * power * max(.55, 1.0 - distance / (2 * spec["radius"])), now)
        await send_event(spell_fx_event(p, spell_id, spec, tx, ty))
    elif spell_id == "thorns" or spec.get("crafted") and spec.get("kind") in {"Терни", "Яд"}:
        thorn_fields.append({"x": tx, "y": ty, "radius": spec["radius"], "damage": round(spell_damage_base * power),
                             "owner": p["id"], "until": now + 3.2, "next_hit": now})
        await send_event(spell_fx_event(p, spell_id, spec, tx, ty))
    elif spell_id == "heal" or spec.get("crafted") and spec.get("kind") == "Исцеление":
        healed = 0
        for ally in players.values():
            if math.hypot(ally["x"] - p["x"], ally["y"] - p["y"]) <= spec["radius"] and ally.get("respawn_at", 0) <= now:
                before = ally["hp"]; ally["hp"] = min(ally["max_hp"], ally["hp"] + round(spec["heal"] * power)); healed += ally["hp"] - before
        await send_event(spell_fx_event(p, spell_id, spec, p["x"], p["y"]))
        await tell(p["id"], f"Исцеление восстановило {healed} здоровья группе в радиусе {spec['radius']}."); return
    await tell(p["id"], f"Применено: {spec['name']} · область {spec['radius']} ед.")

def name_spell_profile(name: str) -> dict[str, Any]:
    """Deterministic fantasy-name scoring, with hard server-side bounds."""
    words = [w for w in re.findall(r"[а-яёa-z]+", name.casefold()) if w]
    lexicon = {
        "огонь": ("Огонь", 3), "пламя": ("Огонь", 4), "жар": ("Огонь", 2), "пепел": ("Огонь", 2),
        "лед": ("Лёд", 3), "лёд": ("Лёд", 3), "иней": ("Лёд", 3), "мороз": ("Лёд", 4), "снег": ("Лёд", 2),
        "молния": ("Молния", 4), "гром": ("Молния", 3), "шторм": ("Молния", 3),
        "тень": ("Тень", 3), "мрак": ("Тень", 4), "ночь": ("Тень", 2), "пустота": ("Тень", 4),
        "лечение": ("Исцеление", 4), "исцеление": ("Исцеление", 4), "свет": ("Исцеление", 2), "жизнь": ("Исцеление", 2),
        "корень": ("Терни", 2), "терн": ("Терни", 3), "шип": ("Терни", 3), "лес": ("Терни", 1),
        "взрыв": ("Всплеск", 4), "звезда": ("Звёзды", 3), "звёзд": ("Звёзды", 3), "метеор": ("Звёзды", 4),
        "яд": ("Яд", 3), "кислота": ("Яд", 3), "душа": ("Душа", 2), "эхо": ("Эхо", 2),
    }
    scores = {}
    for word in words:
        for stem, (kind, weight) in lexicon.items():
            if word == stem or (len(stem) >= 4 and word.startswith(stem[:max(4, len(stem)-2)])):
                scores[kind] = scores.get(kind, 0) + weight
    kind = max(scores, key=scores.get) if scores else "Аркана"
    rarity = min(5, max(1, len(words) + (1 if len(name) >= 12 else 0)))
    power = sum(scores.values())
    return {"kind": kind, "rarity": rarity, "power": power}


async def create_custom_spell(p: dict[str, Any], msg: dict[str, Any]) -> None:
    learned = all_spells(p)
    a, b = str(msg.get("a", "")), str(msg.get("b", ""))
    name = " ".join(str(msg.get("name", "")).strip().split())[:28]
    if a not in learned or b not in learned or not spell_unlocked(p, a) or not spell_unlocked(p, b):
        await tell(p["id"], "Для сплетения выбери два изученных заклинания."); return
    if a == b:
        await tell(p["id"], "Нужно выбрать два разных заклинания."); return
    if not name or len(name) < 3:
        await tell(p["id"], "Название должно содержать от 3 до 28 символов."); return
    customs = p.setdefault("custom_spells", {})
    if len(customs) >= 24:
        await tell(p["id"], "Предел коллекции — 24 созданных заклинания."); return
    key = str(msg.get("key", "F1"))
    allowed_keys = {f"F{i}" for i in range(1, 13)} | {"Digit0"}
    if key not in allowed_keys:
        await tell(p["id"], "Для заклинания выбери клавишу F1–F12 или 0."); return
    if any(str(sp.get("key", "")) == key for sp in p.get("custom_spells", {}).values() if isinstance(sp, dict)):
        await tell(p["id"], "Эта клавиша уже назначена созданному заклинанию."); return
    profile = name_spell_profile(name)
    sa, sb = learned[a], learned[b]
    merged_heal = profile["kind"] == "Исцеление"
    damage = round((float(sa.get("damage", sa.get("heal", 22))) + float(sb.get("damage", sb.get("heal", 22)))) * .42)
    radius = round((float(sa.get("radius", 90)) + float(sb.get("radius", 90))) * .36)
    # Better names increase the spell's strength and area, but also its mana cost.
    damage = max(12, min(180, round(damage * (0.78 + profile["rarity"] * .12 + min(profile["power"], 8) * .025))))
    radius = max(52, min(230, round(radius * (0.82 + profile["rarity"] * .09 + min(profile["power"], 8) * .025))))
    mana = max(12, min(100, round((int(sa.get("mana", 20)) + int(sb.get("mana", 20))) * .32 * (0.85 + profile["rarity"] * .12 + min(profile["power"], 8) * .025))))
    cooldown = round(max(2.0, min(18.0, (float(sa.get("cooldown", 4)) + float(sb.get("cooldown", 4))) * .42 + profile["rarity"] * .45)), 2)
    spell_id = "custom_" + uuid.uuid4().hex[:12]
    spec = {"id": spell_id, "name": name, "mana": mana, "cooldown": cooldown, "damage": damage,
            "radius": radius, "kind": profile["kind"], "rarity": profile["rarity"],
            "unlock_level": 1, "unlock_spent": 0, "source": [a, b], "crafted": True, "key": key}
    if merged_heal:
        spec["heal"] = max(10, round((int(sa.get("heal", sa.get("damage", 22))) + int(sb.get("heal", sb.get("damage", 22)))) * .24))
        spec.pop("damage", None)
    customs[spell_id] = spec
    p.setdefault("spell_uses", {})[spell_id] = 0
    await sync_station_state(p)
    await tell(p["id"], f"Создано «{name}» · тип {profile['kind']} · мана {mana} · сила {spec.get('damage', spec.get('heal'))} · область {radius}.")


async def delete_custom_spell(p: dict[str, Any], msg: dict[str, Any]) -> None:
    spell_id = str(msg.get("spell", ""))
    customs = p.get("custom_spells", {})
    spec = customs.pop(spell_id, None) if isinstance(customs, dict) else None
    if not isinstance(spec, dict):
        await tell(p["id"], "Созданное заклинание уже удалено или не найдено."); return
    p.get("spell_uses", {}).pop(spell_id, None)
    p.get("spell_cooldowns", {}).pop(spell_id, None)
    await sync_station_state(p)
    await tell(p["id"], f"Заклинание «{spec.get('name', 'Безымянное')}» удалено.")


async def bind_custom_spell_key(p: dict[str, Any], msg: dict[str, Any]) -> None:
    spell_id = str(msg.get("spell", ""))
    key = str(msg.get("key", ""))
    allowed_keys = {f"F{i}" for i in range(1, 13)} | {"Digit0"}
    if key not in allowed_keys:
        await tell(p["id"], "Для созданных заклинаний доступны F1–F12 и 0."); return
    customs = p.setdefault("custom_spells", {})
    spec = customs.get(spell_id) if isinstance(customs, dict) else None
    if not isinstance(spec, dict):
        await tell(p["id"], "Созданное заклинание не найдено."); return
    if any(other_id != spell_id and isinstance(other, dict) and other.get("key") == key
           for other_id, other in customs.items()):
        await tell(p["id"], "Эта клавиша уже назначена другому созданному заклинанию."); return
    spec["key"] = key
    await sync_station_state(p)
    await tell(p["id"], f"Клавиша для «{spec.get('name', 'заклинания')}» назначена: {'0' if key == 'Digit0' else key}.")


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
    elif kind == "create_spell":
        await create_custom_spell(p, msg)
    elif kind == "bind_custom_spell":
        await bind_custom_spell_key(p, msg)
    elif kind == "delete_custom_spell":
        await delete_custom_spell(p, msg)
    elif kind == "spell":
        try:
            await cast_spell(p, now, str(msg.get("spell", "")), float(msg.get("aim_x", 0)), float(msg.get("aim_y", 0)),
                             float(msg["target_x"]) if msg.get("target_x") is not None else None,
                             float(msg["target_y"]) if msg.get("target_y") is not None else None)
        except (TypeError, ValueError, KeyError) as exc:
            print(f"spell action input error: {exc}")
            await tell(pid, "Не удалось прочитать направление заклинания.")
        except Exception as exc:
            print(f"spell action failed for {pid}: {exc}")
            await tell(pid, "Заклинание не удалось применить. Соединение сохранено.")
    elif kind == "weapon":
        weapon = str(msg.get("id", ""))
        if weapon in p["weapons"] and weapon in WEAPONS:
            p["weapon"] = weapon
            await sync_station_state(p)
        else:
            await tell(pid, "Оружие не найдено в сумке.")
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
            await sync_station_state(p)
            await tell(pid, f"Экипировано: {GEAR[gear_id]['name']} · защита {GEAR[gear_id]['defense']}.")
        else:
            await tell(pid, "Предмет не найден в рюкзаке. Обнови инвентарь и попробуй снова.")
    elif kind == "use_potion":
        if p["inventory"]["potion"] > 0 and p["hp"] < p["max_hp"]:
            p["inventory"]["potion"] -= 1; p["hp"] = min(p["max_hp"], p["hp"] + 48)
            await tell(pid, "Настойка восстановила здоровье.")
    elif kind == "upgrade":
        stat = str(msg.get("stat", ""))
        upgraded = False
        if stat in p["stats"] and p["skill_points"] > 0:
            p["stats"][stat] = int(p["stats"].get(stat, 1)) + 1; p["skill_points"] -= 1
            update_derived(p, heal=stat == "vitality")
            await tell(pid, f"Развитие улучшено: {stat_names[stat]} · теперь {p['stats'][stat]}.")
            upgraded = True
        elif stat in {"mana_regen", "magic_damage"} and p["skill_points"] > 0:
            field = "mana_regen_level" if stat == "mana_regen" else "magic_damage_level"
            p[field] = int(p.get(field, 0)) + 1
            p["skill_points"] -= 1
            if stat == "mana_regen":
                update_derived(p)
                await tell(pid, f"Восстановление маны улучшено до уровня {p[field]}.")
            else:
                await tell(pid, f"Сила магии улучшена: +{p[field] * 8}% урона от заклинаний.")
            upgraded = True
        if upgraded:
            p["stats_revision"] = int(p.get("stats_revision", 0)) + 1
            try: save_character(p)
            except sqlite3.Error: pass
            await send_event(stats_updated_event(pid, p))
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


stat_names = {"might": "Сила", "vitality": "Живучесть", "agility": "Ловкость", "precision": "Точность", "fortune": "Удача"}
PERSIST_FIELDS = (
    "x", "y", "hp", "stamina", "xp", "level", "skill_points", "stats",
    "gold", "kills", "weapon", "weapons", "gear", "gear_inventory",
    "inventory", "quest_stage", "quest_active", "quest_kills", "quest_gather",
    "enchantments", "market_starter_grant", "magic_mana_spent", "upgrades", "mana_regen_level", "magic_damage_level", "spell_uses", "custom_spells",
)


def init_database() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS character_saves ("
            "name TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at INTEGER NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS user_accounts ("
            "username_key TEXT PRIMARY KEY, username TEXT NOT NULL, salt TEXT NOT NULL, "
            "password_hash TEXT NOT NULL, created_at INTEGER NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS auth_sessions ("
            "token_hash TEXT PRIMARY KEY, username_key TEXT NOT NULL, expires_at INTEGER NOT NULL, "
            "FOREIGN KEY(username_key) REFERENCES user_accounts(username_key))"
        )


SESSION_SECONDS = 30 * 24 * 60 * 60
PASSWORD_ITERATIONS = 310_000


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)


def _account_for_token(token: str | None) -> dict[str, str] | None:
    if not token or len(token) > 200:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute(
            "SELECT a.username, a.username_key FROM auth_sessions s "
            "JOIN user_accounts a ON a.username_key=s.username_key "
            "WHERE s.token_hash=? AND s.expires_at>?", (token_hash, int(time.time()))
        ).fetchone()
    return {"username": row[0], "username_key": row[1]} if row else None


def _issue_session(username_key: str, request: Request, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires = int(time.time()) + SESSION_SECONDS
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("INSERT INTO auth_sessions(token_hash, username_key, expires_at) VALUES (?, ?, ?)",
                           (token_hash, username_key, expires))
    response.set_cookie("echo_session", token, max_age=SESSION_SECONDS, httponly=True,
                        secure=request.url.scheme == "https", samesite="strict", path="/")


def _credentials(payload: Any) -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Некорректные данные формы.")
    username = str(payload.get("username", "")).strip()
    password = payload.get("password", "")
    if not isinstance(password, str):
        raise HTTPException(status_code=400, detail="Некорректные данные формы.")
    if not 3 <= len(username) <= 18 or not re.fullmatch(r"[\w-]+", username, flags=re.UNICODE):
        raise HTTPException(status_code=400, detail="Имя: 3–18 букв, цифр, дефисов или подчёркиваний.")
    if not 8 <= len(password) <= 128:
        raise HTTPException(status_code=400, detail="Пароль должен содержать от 8 до 128 символов.")
    return username, username.casefold(), password


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
            p["mana"] = min(p["max_mana"], p.get("mana", 0) + (9.0 + 1.5 * p.get("mana_regen_level", 0)) * dt)
            for site in POWER_SITES:
                if math.hypot(p["x"] - site["x"], p["y"] - site["y"]) <= site["radius"]:
                    if site["id"] == "spring": p["hp"] = min(p["max_hp"], p["hp"] + 2.0 * dt)
                    elif site["id"] == "root": p["mana"] = min(p["max_mana"], p["mana"] + 3.0 * dt)
                    elif site["id"] == "ember": p["stamina"] = min(p["max_stamina"], p["stamina"] + 4.0 * dt)
                    elif site["id"] == "glacier":
                        p["hp"] = min(p["max_hp"], p["hp"] + 1.5 * dt)
                        p["mana"] = min(p["max_mana"], p["mana"] + 1.5 * dt)
                    elif site["id"] == "obsidian":
                        p["hp"] = min(p["max_hp"], p["hp"] + 1.0 * dt)
                        p["mana"] = min(p["max_mana"], p["mana"] + 1.0 * dt)
                    else:
                        p["hp"] = min(p["max_hp"], p["hp"] + 3.0 * dt)
                        p["mana"] = min(p["max_mana"], p["mana"] + 3.0 * dt)
                        p["stamina"] = min(p["max_stamina"], p["stamina"] + 3.0 * dt)
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
            step_distance = math.hypot(arrow["vx"] * dt, arrow["vy"] * dt)
            arrow["x"] += arrow["vx"] * dt; arrow["y"] += arrow["vy"] * dt
            arrow["life"] -= dt
            if arrow.get("max_distance") is not None:
                arrow["travelled"] = float(arrow.get("travelled", 0.0)) + step_distance
                if arrow["travelled"] >= float(arrow["max_distance"]):
                    arrow["life"] = 0
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
                await send_event({"type": "spell_fx", "spell": spell_id, "kind": arrow.get("spell_kind", spell_id),
                 "name": arrow.get("spell_name", spell_id), "rarity": arrow.get("spell_rarity", 1),
                 "mastery": arrow.get("spell_mastery", 1), "variant": arrow.get("spell_variant", 0),
                 "palette": arrow.get("spell_palette", ELEMENT_FX["Аркана"]),
                 "x": arrow["x"], "y": arrow["y"], "radius": arrow.get("radius", 100), "owner": arrow.get("owner")})
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
    account = _account_for_token(websocket.cookies.get("echo_session"))
    if not account:
        await websocket.close(code=1008, reason="AUTH_REQUIRED")
        return
    await websocket.accept()
    if len(players) >= MAX_PLAYERS:
        await websocket.send_text(json.dumps({"type": "error", "message": "Мир полон. Максимум 8 следопытов."}, ensure_ascii=False))
        await websocket.close(code=1008); return
    pid = uuid.uuid4().hex[:8]
    name = safe_name(account["username"])
    p = {"id": pid, "name": name, "x": 330.0, "y": 1100.0, "mx": 0.0, "my": 0.0,
         "face_x": 1.0, "face_y": 0.0, "hp": 100, "max_hp": 100, "stamina": 100.0, "max_stamina": 100,
         "xp": 0, "level": 1, "skill_points": 0, "stats": {"might": 1, "vitality": 1, "agility": 1, "precision": 1, "fortune": 1},
         "gold": 0, "kills": 0, "last_attack": 0.0, "attack": None, "respawn_at": 0.0,
         "mana": 60, "max_mana": 60, "spell_cooldowns": {}, "spell_uses": {}, "custom_spells": {},
         "enchantments": {"weapon": {}, "gear": {}}, "upgrades": {"weapon": {}, "gear": {}},
         "magic_mana_spent": 0, "market_starter_grant": False,
         "mana_regen_level": 0, "magic_damage_level": 0,
         "dodge_at": 0.0, "dodge_until": 0.0, "weapon": "sword", "weapons": ["sword", "axe", "bow"],
         "gear": "traveler", "gear_inventory": [],
         "inventory": {"wood": 0, "herb": 0, "ore": 0, "hide": 0, "slime": 0, "crystal": 0, "shard": 0, "potion": 2, "arrows": 18},
         "quest_stage": 0, "quest_active": False, "quest_kills": {}, "quest_gather": {},
         "gathering": None, "last_chat": 0.0}
    saved = load_character(name)
    p.update(saved)
    p["x"] = max(25.0, min(WORLD_W - 25.0, float(p["x"])))
    p["y"] = max(25.0, min(WORLD_H - 25.0, float(p["y"])))
    p["level"] = max(1, int(p.get("level", 1)))
    p["stats"] = {key: max(1, int(p.get("stats", {}).get(key, 1)))
                  for key in stat_names}
    # Recover unspent level-up points in older saves where the UI/action path failed.
    spent_points = sum(max(0, value - 1) for value in p["stats"].values())
    spent_points += max(0, int(p.get("mana_regen_level", 0)))
    spent_points += max(0, int(p.get("magic_damage_level", 0)))
    earned_points = max(0, p["level"] - 1)
    p["skill_points"] = max(0, int(p.get("skill_points", 0)), earned_points - spent_points)
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
    if not isinstance(p.get("spell_uses"), dict): p["spell_uses"] = {}
    if not isinstance(p.get("custom_spells"), dict): p["custom_spells"] = {}
    p["spell_uses"] = {str(k): max(0, min(100000, int(v))) for k, v in p["spell_uses"].items()
                       if k in SPELLS or k in p.get("custom_spells", {})}
    p["magic_mana_spent"] = max(0, min(1000000, int(p.get("magic_mana_spent", 0))))
    p["mana_regen_level"] = max(0, min(1000, int(p.get("mana_regen_level", 0))))
    p["magic_damage_level"] = max(0, min(1000, int(p.get("magic_damage_level", 0))))
    if not isinstance(p.get("upgrades"), dict): p["upgrades"] = {"weapon": {}, "gear": {}}
    p["upgrades"].setdefault("weapon", {}); p["upgrades"].setdefault("gear", {})
    if not p.get("market_starter_grant", False):
        p["gold"] = max(0, int(p.get("gold", 0))) + 150
        p["market_starter_grant"] = True
    p["quest_stage"] = max(0, min(len(QUESTS), int(p["quest_stage"])))
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
