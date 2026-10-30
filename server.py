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
TICK = 0.025
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
    # Расширенный арсенал: новые модели оружия с собственным поведением.
    "warhammer": {"name": "Молот сокрушитель", "kind": "melee", "damage": 38, "bonus": 44, "charge": .92, "stamina": 24, "range": 46, "arc": .10, "cooldown": .55, "color": "#c9b28a", "rarity": "rare"},
    "mace": {"name": "Булава болотного света", "kind": "melee", "damage": 26, "bonus": 30, "charge": .70, "stamina": 16, "range": 42, "arc": .16, "cooldown": .40, "color": "#b7d18f", "rarity": "uncommon"},
    "glaive": {"name": "Глефа жатвы", "kind": "melee", "damage": 33, "bonus": 40, "charge": .74, "stamina": 19, "range": 66, "arc": .14, "cooldown": .40, "color": "#d8b56f", "rarity": "epic"},
    "halberd": {"name": "Альбарда стражи врат", "kind": "melee", "damage": 44, "bonus": 52, "charge": .80, "stamina": 23, "range": 72, "arc": .12, "cooldown": .46, "color": "#9fb6c9", "rarity": "legendary"},
    "rapier": {"name": "Рапира танцующей тени", "kind": "melee", "damage": 28, "bonus": 34, "charge": .48, "stamina": 12, "range": 58, "arc": .30, "cooldown": .22, "color": "#e3d7ff", "rarity": "rare"},
    "claws": {"name": "Когти туманной рыси", "kind": "melee", "damage": 20, "bonus": 24, "charge": .36, "stamina": 9, "range": 34, "arc": .46, "cooldown": .17, "color": "#9fd8c8", "rarity": "uncommon"},
    "flamberge": {"name": "Пламенный клык-клинок", "kind": "melee", "damage": 36, "bonus": 43, "charge": .66, "stamina": 18, "range": 50, "arc": .26, "cooldown": .34, "color": "#ff8f5e", "rarity": "epic"},
    "war_maul": {"name": "Осадная боевая коса-молот", "kind": "melee", "damage": 56, "bonus": 66, "charge": .98, "stamina": 27, "range": 56, "arc": .08, "cooldown": .60, "color": "#bfa0d8", "rarity": "legendary"},
    "longbow": {"name": "Длинный лук Эха", "kind": "bow", "damage": 22, "bonus": 38, "charge": .96, "stamina": 12, "cooldown": .20, "color": "#c8e6a2", "rarity": "rare"},
    "crystal_bow": {"name": "Кристальный лук инея", "kind": "bow", "damage": 28, "bonus": 44, "charge": .84, "stamina": 12, "cooldown": .16, "color": "#a9f0ff", "rarity": "epic"},
    "ember_staff": {"name": "Посох тлеющего угля", "kind": "staff", "damage": 24, "bonus": 28, "charge": .70, "stamina": 12, "range": 46, "arc": .24, "cooldown": .36, "color": "#ff9d6b", "rarity": "rare", "spell_power": .18},
    "moon_staff": {"name": "Посох лунного прилива", "kind": "staff", "damage": 30, "bonus": 34, "charge": .66, "stamina": 13, "range": 47, "arc": .24, "cooldown": .33, "color": "#bcd0ff", "rarity": "epic", "spell_power": .28},
}
WEAPON_LORE = {
    "sword": "Стандартный клинок лесной дозорной стражи.",
    "axe": "Тяжёлый колун, что рубит и вепря, и сук.",
    "bow": "Тисовая плеть, сплетённая из ветвей старого тиса.",
    "forest_bow": "Лук следопыта помнит каждую тропу топей.",
    "apprentice_staff": "Посох, ещё тёплый от рук ученика.",
    "thorn_staff": "Терни лозы жаждут чужой крови.",
    "iron_sword": "Сталь, закалённая в болотной жиже.",
    "moonblade": "Лезвие отражает луну даже в полной тьме.",
    "ember_greatsword": "В клинке тлеет зарево последнего пожара руин.",
    "starfall_bow": "Стрела уходит вслед за падающей звездой.",
    "frostfang": "Клык змея, что уснул подо льдом Синего Пламени.",
    "void_edge": "Рассекает ткань между мирами.",
    "daggers": "Тени режут беззвучно.",
    "spear": "Копьё, которым звёздные стражи держали врата.",
    "scythe": "Жнец косит не только злак.",
    "astral_blade": "Клинок вырезан из сердца упавшей звезды.",
    "archon_staff": "Посох архонта гудит первородным эфиром.",
    "stormbrand": "В стали живёт гром Грозового кедра.",
    "obsidian_axe": "Обсидиан чёрного стекла ломает всё, кроме воли.",
    "sunfall_bow": "Тетива вспыхивает светом Солнцепада.",
    "elder_staff": "Корень Первозданного сада продолжает расти.",
    "warhammer": "Молот, после которого стены не встают.",
    "mace": "Болотный свет бьёт изнутри раны.",
    "glaive": "Жатва начинается на рассвете.",
    "halberd": "Альбарда стражи врат помнит всех, кто стучался.",
    "rapier": "Танцующая тень наносит последний шаг клинком.",
    "claws": "Когти туманной рыси оставляют пять дорог.",
    "flamberge": "Волны клинка горят холодным огнём.",
    "war_maul": "Осадная коса-молот открывает ворота и черепа.",
    "longbow": "Длинный лук Эха отвечает эхом на каждый выстрел.",
    "crystal_bow": "Иней на плечах лука поёт от натуги.",
    "ember_staff": "Угли посоха не гаснут под дождём.",
    "moon_staff": "Приливы луны текут по древку посоха.",
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
    # Новые сеты брони
    "leather_vest": {"name": "Кожаный жилет охотника", "defense": 4, "color": "#a5825f", "rarity": "common", "lore": "Прочная кожа, выдубленная корой дуба."},
    "chain_shirt": {"name": "Кольчуга лесной стражи", "defense": 7, "color": "#9aa7ad", "rarity": "uncommon", "lore": "Мелкие кольца сплетены руками болотного кузнеца."},
    "bark_plate": {"name": "Кора-панцирь друида", "defense": 10, "color": "#7c8f56", "rarity": "rare", "lore": "Живая кора нарастает поверх старых ран."},
    "ember_mail": {"name": "Доспех тлеющих углей", "defense": 14, "color": "#c96f4a", "rarity": "epic", "lore": "Пластины греются, будто память о пожаре руин."},
    "frostguard_plate": {"name": "Панцирь морозной стражи", "defense": 16, "color": "#a8dced", "rarity": "epic", "lore": "Иней на заклёпках не тает даже у костра."},
    "void_cloak": {"name": "Плащ из ткани разлома", "defense": 24, "color": "#8f6fd1", "rarity": "legendary", "lore": "Край плаща исчезает в щели между мирами."},
}
MONSTERS = {
    # "size" is the visual sprite radius; every combat hitbox is derived from it
    # so a monster's collision box matches exactly what the player sees on screen.
    "slime": {"name": "Моховой слизень", "hp": 48, "speed": 42, "damage": 7, "range": 36, "cooldown": 1.35, "xp": 20, "color": "#8fce73", "zone": 1, "size": 20, "anim": "bounce"},
    "wolf": {"name": "Туманный волк", "hp": 70, "speed": 72, "damage": 12, "range": 40, "cooldown": 1.15, "xp": 34, "color": "#b7c7b5", "zone": 1, "size": 22, "anim": "dash"},
    "boar": {"name": "Топкий вепрь", "hp": 125, "speed": 48, "damage": 18, "range": 48, "cooldown": 1.65, "xp": 56, "color": "#a7805b", "zone": 2, "size": 26, "anim": "charge"},
    "wisp": {"name": "Болотный огонёк", "hp": 88, "speed": 58, "damage": 15, "range": 52, "cooldown": 1.45, "xp": 62, "color": "#7bd8cf", "zone": 2, "size": 20, "anim": "float"},
    "stone": {"name": "Каменный дозорный", "hp": 215, "speed": 29, "damage": 25, "range": 58, "cooldown": 2.0, "xp": 105, "color": "#b39c7b", "zone": 2, "size": 28, "anim": "stomp"},
    "ashling": {"name": "Пепельный искатель", "hp": 165, "speed": 55, "damage": 23, "range": 46, "cooldown": 1.3, "xp": 110, "color": "#d38e67", "zone": 3, "size": 23, "anim": "flit"},
    "ashguard": {"name": "Страж руин", "hp": 330, "speed": 34, "damage": 34, "range": 66, "cooldown": 2.15, "xp": 190, "color": "#c6ad86", "zone": 3, "size": 34, "anim": "guard"},
    "colossus": {"name": "Пепельный колосс", "hp": 920, "speed": 22, "damage": 48, "range": 94, "cooldown": 2.6, "xp": 700, "color": "#e2a26c", "zone": 3, "size": 55, "anim": "quake"},
    "frost_wyrm": {"name": "Ледяной змей", "hp": 560, "speed": 59, "damage": 38, "range": 76, "cooldown": 1.65, "xp": 410, "color": "#8ee8f2", "zone": 4, "size": 30, "anim": "serpent"},
    "rift_knight": {"name": "Рыцарь разлома", "hp": 760, "speed": 45, "damage": 52, "range": 82, "cooldown": 1.9, "xp": 580, "color": "#bd85ed", "zone": 5, "size": 32, "anim": "lunge"},
    "echo_dragon": {"name": "Дракон Пустого Эха", "hp": 2600, "speed": 31, "damage": 74, "range": 126, "cooldown": 2.45, "xp": 2400, "color": "#ff637e", "zone": 5, "size": 50, "anim": "fly", "boss": True},
    "void_wraith": {"name": "Призрак Бездны", "hp": 1400, "speed": 48, "damage": 55, "range": 85, "cooldown": 1.4, "xp": 1100, "color": "#7b2cbf", "zone": 6, "size": 28, "anim": "phase"},
    "astral_titan": {"name": "Титан Астральной Бездны", "hp": 4800, "speed": 36, "damage": 95, "range": 140, "cooldown": 2.2, "xp": 4500, "color": "#00f0ff", "zone": 6, "size": 58, "anim": "quake", "boss": True},
    "obsidian_sentinel": {"name": "Страж чёрного стекла", "hp": 2100, "speed": 38, "damage": 70, "range": 94, "cooldown": 1.8, "xp": 1850, "color": "#86718f", "zone": 7, "size": 36, "anim": "guard"},
    "starseer": {"name": "Звёздочёт Пустоты", "hp": 2650, "speed": 49, "damage": 82, "range": 76, "cooldown": 1.55, "xp": 3100, "color": "#d9a6ef", "zone": 8, "size": 30, "anim": "cast"},
    "ancient_warden": {"name": "Хранитель Первозданного сада", "hp": 7200, "speed": 29, "damage": 108, "range": 148, "cooldown": 2.05, "xp": 7200, "color": "#91cb79", "zone": 8, "size": 56, "anim": "quake", "boss": True},
}


for _wid, _wlore in WEAPON_LORE.items():
    if _wid in WEAPONS:
        WEAPONS[_wid]["lore"] = _wlore


def mob_hit_radius(mob: dict[str, Any]) -> float:
    """Hitbox that mirrors the drawn model: sprite size scaled with level."""
    spec = MONSTERS.get(mob.get("kind"), {})
    base = float(spec.get("size", 24))
    growth = 1.0 + min(0.35, max(0, int(mob.get("level", spec.get("zone", 1) or 1)) - int(spec.get("zone", 1) or 1)) * 0.02)
    return round(base * growth, 1)


def mob_touch_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Surface-to-surface contact distance between two entities (circle hitboxes)."""
    return mob_hit_radius(a) + mob_hit_radius(b)


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
    "warhammer": {"name": "Молот сокрушитель", "description": "Тяжёлый дробящий удар", "price": 480, "kind": "weapon"},
    "mace": {"name": "Булава болотного света", "description": "Недорогая дробина для топей", "price": 190, "kind": "weapon"},
    "glaive": {"name": "Глефа жатвы", "description": "Дальний размах по нескольким врагам", "price": 560, "kind": "weapon"},
    "halberd": {"name": "Альбарда стражи врат", "description": "Максимальная дистанция ближнего боя", "price": 1450, "kind": "weapon"},
    "rapier": {"name": "Рапира танцующей тени", "description": "Молниеносные колющие выпады", "price": 430, "kind": "weapon"},
    "claws": {"name": "Когти туманной рыси", "description": "Самая быстрая атака в лесу", "price": 240, "kind": "weapon"},
    "flamberge": {"name": "Пламенный клык-клинок", "description": "Клинок, паленый в угольной яме", "price": 690, "kind": "weapon"},
    "war_maul": {"name": "Осадная коса-молот", "description": "Разит целые стаи одним замахом", "price": 1650, "kind": "weapon"},
    "longbow": {"name": "Длинный лук Эха", "description": "Дальнобойный лук следопыта", "price": 380, "kind": "weapon"},
    "crystal_bow": {"name": "Кристальный лук инея", "description": "Стрелы оставляют ледяной след", "price": 860, "kind": "weapon"},
    "ember_staff": {"name": "Посох тлеющего угля", "description": "Усиливает огненные чары", "price": 410, "kind": "weapon"},
    "moon_staff": {"name": "Посох лунного прилива", "description": "Плавный приток маны и силы чар", "price": 720, "kind": "weapon"},
    "wolf_cloak": {"name": "Плащ туманного волка", "description": "Броня · защита 5", "price": 145, "kind": "gear"},
    "marsh_armor": {"name": "Болотная броня", "description": "Броня · защита 8", "price": 270, "kind": "gear"},
    "leather_vest": {"name": "Кожаный жилет охотника", "description": "Броня · защита 4", "price": 90, "kind": "gear"},
    "chain_shirt": {"name": "Кольчуга лесной стражи", "description": "Броня · защита 7", "price": 240, "kind": "gear"},
    "bark_plate": {"name": "Кора-панцирь друида", "description": "Броня · защита 10", "price": 360, "kind": "gear"},
    "ember_mail": {"name": "Доспех тлеющих углей", "description": "Броня · защита 14", "price": 620, "kind": "gear"},
    "frostguard_plate": {"name": "Панцирь морозной стражи", "description": "Броня · защита 16", "price": 780, "kind": "gear"},
    "void_cloak": {"name": "Плащ из ткани разлома", "description": "Броня · защита 24", "price": 1350, "kind": "gear"},
    "mana_potion": {"name": "Эссенция синего пламени", "description": "+60 маны", "price": 45, "kind": "mana_potion"},
    "stamina_potion": {"name": "Отвар живучести", "description": "+55 выносливости", "price": 38, "kind": "stamina_potion"},
    "elixir": {"name": "Эликсир первозданной росы", "description": "Полное восстановление ресурсов", "price": 120, "kind": "elixir"},
    "bandage": {"name": "Лубяная повязка", "description": "+24 здоровья", "price": 14, "kind": "bandage"},
    "throwing_knife": {"name": "Связка метательных ножей ×5", "description": "Метательный боеприпас", "price": 60, "kind": "throwing_knife"},
}
SELL_PRICES = {"wood": 3, "herb": 4, "ore": 6, "hide": 8, "slime": 5, "crystal": 10, "shard": 14, "potion": 12, "arrows": 1,
               "mana_potion": 16, "stamina_potion": 14, "elixir": 45, "throwing_knife": 4, "bandage": 5}
CONSUMABLES = {
    "mana_potion": {"name": "Эссенция синего пламени", "description": "+60 маны", "price": 45, "restore_mana": 60},
    "stamina_potion": {"name": "Отвар живучести", "description": "+55 выносливости", "price": 38, "restore_stamina": 55},
    "elixir": {"name": "Эликсир первозданной росы", "description": "+90 здоровья, +60 маны, +40 выносливости", "price": 120,
                "restore_hp": 90, "restore_mana": 60, "restore_stamina": 40},
    "bandage": {"name": "Лубяная повязка", "description": "+24 здоровья мгновенно", "price": 14, "restore_hp": 24},
}
CRAFT_RECIPES = {
    "arrows": {"name": "Колчан стрел ×8", "cost": {"wood": 2, "ore": 1}},
    "potion": {"name": "Настойка следопыта", "cost": {"herb": 3, "slime": 1}},
    "mana_potion": {"name": "Эссенция синего пламени", "cost": {"crystal": 2, "herb": 2}},
    "stamina_potion": {"name": "Отвар живучести", "cost": {"hide": 2, "ore": 1}},
    "elixir": {"name": "Эликсир первозданной росы", "cost": {"crystal": 4, "shard": 2, "herb": 4}},
    "bandage": {"name": "Стопка повязок ×3", "cost": {"herb": 2}},
    "throwing_knife": {"name": "Метательные ножи ×5", "cost": {"ore": 2, "wood": 1}},
    "iron_sword": {"name": "Клинок из болотной стали", "cost": {"ore": 6, "wood": 4}},
    "mace": {"name": "Булава болотного света", "cost": {"ore": 4, "wood": 3, "hide": 1}},
    "warhammer": {"name": "Молот сокрушитель", "cost": {"ore": 9, "wood": 4, "hide": 2}},
    "longbow": {"name": "Длинный лук Эха", "cost": {"wood": 8, "hide": 3, "crystal": 1}},
    "ember_staff": {"name": "Посох тлеющего угля", "cost": {"wood": 6, "crystal": 3, "shard": 1}},
    "leather_vest": {"name": "Кожаный жилет охотника", "cost": {"hide": 5, "wood": 1}},
    "chain_shirt": {"name": "Кольчуга лесной стражи", "cost": {"ore": 7, "hide": 2}},
    "armor": {"name": "Болотная броня", "cost": {"hide": 4, "ore": 3}},
    "bark_plate": {"name": "Кора-панцирь друида", "cost": {"wood": 8, "herb": 4, "ore": 3}},
}
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
ground_effects: list[dict[str, Any]] = []
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

CLASS_MIN_LEVEL = 5
MASTERY_MAX_LEVEL = 5
MASTERY_TREES = ("warrior", "ranger", "mage")
MASTERY_NAMES = {"warrior": "Воин", "ranger": "Следопыт", "mage": "Маг"}
TREE_WEAPON_KIND = {"warrior": "melee", "ranger": "bow", "mage": "staff"}
WEAPON_TREE = {"melee": "warrior", "bow": "ranger", "staff": "mage"}
CLASSES = {
    "warrior": {
        "name": "Воин", "title": "Стальной клинок", "style": "Ближний бой",
        "description": "Держит удар в самой гуще схватки. Сила и живучесть выше, способности открываются по мере владения оружием.",
        "stat_bonus": {"might": 3, "vitality": 2},
        "abilities": ["roar", "lunge", "whirlwind", "iron_guard", "bash", "bloodhunt", "seismic_slam"],
    },
    "ranger": {
        "name": "Следопыт", "title": "Глаз бури", "style": "Дальний бой",
        "description": "Бьёт с дистанции и управляет полем боя. Ловкость и точность выше, стрелы получают стихийные эффекты.",
        "stat_bonus": {"agility": 3, "precision": 2},
        "abilities": ["arrow_rain", "piercing_shot", "fire_arrow", "ice_arrow", "double_shot",
                      "poison_arrow", "blackout_bolt", "eagle_mark"],
    },
    "mage": {
        "name": "Маг", "title": "Хранитель чар", "style": "Магия посоха",
        "description": "Использует прежнюю систему заклинаний и созданных чар. Сила магии растёт вместе с мастерством направления.",
        "stat_bonus": {"vitality": 1, "magic_damage": 1, "mana_regen": 1},
        "abilities": [],
    },
}
ABILITY_CATALOG = {
    "roar": {"tree": "warrior", "name": "Свирепый рык", "icon": "🗣", "mastery": 1,
             "cost": 18, "cooldown": 14.0, "duration": 6.0, "heal_per_sec": 6.0, "key": "KeyR",
             "desc": "На 6 секунд ускоряет восстановление здоровья на 6 ед./с."},
    "lunge": {"tree": "warrior", "name": "Выпад", "icon": "➹", "mastery": 2,
              "cost": 22, "cooldown": 8.0, "distance": 155.0, "range": 205.0, "width": 34.0,
              "mult": 1.35, "key": "KeyT",
              "desc": "Рывок вперёд до 155 ед. с ударом по линии; не выходит за границы мира."},
    "whirlwind": {"tree": "warrior", "name": "Круговой удар", "icon": "⟳", "mastery": 3,
                  "cost": 26, "cooldown": 9.0, "radius": 112.0, "mult": 1.05, "key": "KeyC",
                  "desc": "Разворачивает оружие по кругу и задевает всех врагов в радиусе 112."},
    "iron_guard": {"tree": "warrior", "name": "Железная стойка", "icon": "🛡", "mastery": 4,
                   "cost": 16, "cooldown": 16.0, "duration": 5.0, "armor": 14, "key": "KeyV",
                   "desc": "На 5 секунд добавляет 14 брони и снижает входящий урон."},
    "arrow_rain": {"tree": "ranger", "name": "Дождь стрел", "icon": "☔", "mastery": 1,
                   "cost": 28, "arrows": 3, "cooldown": 15.0, "range": 520.0, "radius": 122.0,
                   "duration": 2.4, "telegraph": 0.9, "tick": 0.55, "mult": 0.52, "key": "KeyR",
                   "desc": "Отмечает область; через 0,9 с по ней трижды бьёт дождь стрел."},
    "piercing_shot": {"tree": "ranger", "name": "Пронзающий выстрел", "icon": "➶", "mastery": 2,
                      "cost": 20, "arrows": 1, "cooldown": 7.0, "range": 900.0, "pierce": 3,
                      "mult": 1.25, "key": "KeyT",
                      "desc": "Стрела проходит сквозь трёх врагов по линии прицела."},
    "fire_arrow": {"tree": "ranger", "name": "Огненная стрела", "icon": "🔥", "mastery": 3,
                   "cost": 22, "arrows": 1, "cooldown": 8.0, "range": 900.0, "mult": 1.0,
                   "burn_duration": 5.0, "burn_tick": 0.75, "burn_mult": 0.16, "key": "KeyC",
                   "desc": "Поджигает цель на 5 секунд; горение не складывается бесконечно."},
    "ice_arrow": {"tree": "ranger", "name": "Ледяная стрела", "icon": "❄", "mastery": 3,
                  "cost": 22, "arrows": 1, "cooldown": 8.0, "range": 900.0, "mult": 0.95,
                  "slow_duration": 4.0, "slow_factor": 0.45, "key": "KeyV",
                  "desc": "Замедляет цель до 45% скорости на 4 секунды."},
    "double_shot": {"tree": "ranger", "name": "Двойной залп", "icon": "⇉", "mastery": 4,
                    "cost": 26, "arrows": 2, "cooldown": 6.5, "range": 760.0, "shots": 2,
                    "spread": 0.09, "mult": 0.78, "key": "KeyX",
                    "desc": "Выпускает две стрелы веером по направлению прицела."},
    # Расширение воина: три дополнительные ближние техники.
    "bash": {"tree": "warrior", "name": "Оглушающий удар", "icon": "⛨", "mastery": 2,
             "cost": 17, "cooldown": 7.0, "radius": 95.0, "mult": 0.55,
             "stun_duration": 1.6, "knockback": 70.0, "key": "KeyZ",
             "desc": "Резкий выпад: оглушает ближайших врагов на 1,6 с и отбрасывает их назад."},
    "bloodhunt": {"tree": "warrior", "name": "Жажда крови", "icon": "🩸", "mastery": 3,
                  "cost": 15, "cooldown": 16.0, "duration": 6.0, "heal_per_hit": 12, "key": "KeyZ",
                  "desc": "6 секунд каждый удар по врагу восстанавливает тебе 12 здоровья."},
    "seismic_slam": {"tree": "warrior", "name": "Сейсмический удар", "icon": "☄", "mastery": 5,
                    "cost": 26, "cooldown": 12.0, "radius": 135.0, "mult": 1.15,
                    "slow_duration": 2.5, "slow_factor": 0.5, "key": "KeyZ",
                    "desc": "Удар о землю: волна поражает всех вокруг и замедляет врагов на 2,5 с."},
    # Расширение следопыта: три дополнительные дальнобойные техники.
    "poison_arrow": {"tree": "ranger", "name": "Отравленная стрела", "icon": "☠", "mastery": 2,
                     "cost": 14, "arrows": 1, "cooldown": 5.5, "range": 760.0, "pierce": 0, "mult": 0.9,
                     "poison_duration": 4.0, "poison_tick": 0.8, "poison_mult": 0.14, "key": "KeyR",
                     "desc": "Стрела впрыскивает яд: урон с течением времени в течение 4 секунд."},
    "blackout_bolt": {"tree": "ranger", "name": "Ослепляющий выстрел", "icon": "◌", "mastery": 3,
                      "cost": 17, "arrows": 1, "cooldown": 8.5, "range": 700.0, "pierce": 0, "mult": 0.85,
                      "stun_duration": 1.8, "key": "KeyR",
                      "desc": "Тёмный болт оглушает цель на 1,8 секунды и прерывает её атаки."},
    "eagle_mark": {"tree": "ranger", "name": "Метка орла", "icon": "🦅", "mastery": 5,
                   "cost": 12, "arrows": 0, "cooldown": 14.0, "range": 620.0,
                   "duration": 8.0, "bonus_mult": 0.25, "key": "KeyR",
                   "desc": "Метка на цели: 8 секунд весь твой урон по ней усилен на 25%."},
}
for _ability_id, _ability_spec in ABILITY_CATALOG.items():
    _ability_spec["id"] = _ability_id

# Воин наносит удары на полтора раза дальше обычного ближнего боя.
CLASS_MELEE_REACH = {"warrior": 1.5}


def melee_reach_factor(p: dict[str, Any]) -> float:
    return CLASS_MELEE_REACH.get(str(p.get("class") or ""), 1.5)

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
            "burn_until": 0.0, "burn_next": 0.0, "burn_owner": "", "burn_damage": 0.0,
            "burn_tick": .75, "slow_until": 0.0, "slow_factor": .45,
            "stun_until": 0.0,
            "poison_until": 0.0, "poison_next": 0.0, "poison_owner": "", "poison_damage": 0.0,
            "poison_tick": .8,
            "boss": bool(spec.get("boss") or kind == "colossus")}


def grant_gear(p: dict[str, Any], gear_id: str) -> bool:
    if gear_id not in GEAR:
        return False
    if gear_id == p.get("gear") or gear_id in p.get("gear_inventory", []):
        p["gold"] += 18
        p.setdefault("inventory", {})["crystal"] = p.get("inventory", {}).get("crystal", 0) + 1
        try:
            broadcast({"type": "notice", "target": p["id"], "text": "Дубликат превращён в 18 монет и эхо-кристалл."})
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
            broadcast({"type": "notice", "target": p["id"], "text": "Дубликат оружия разобран: +24 монеты и 2 эхо-кристалла."})
        except RuntimeError:
            pass
        return False
    p.setdefault("weapons", []).append(weapon_id)
    try:
        broadcast({"type": "notice", "target": p["id"], "text": f"Найдено оружие: {WEAPONS[weapon_id]['name']}!"})
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
    token = request.cookies.get("echo_session")
    account = _account_for_token(token)
    return {"authenticated": bool(account), "username": account["username"] if account else None,
            "accounts": browser_account_roster(_browser_marker(request))}


@app.post("/api/auth/switch")
async def auth_switch(request: Request, response: Response) -> dict[str, Any]:
    """Switch between accounts that signed in from this browser.

    Only the roster stored under *this* browser's marker is accepted — other
    players' accounts are never visible here. A password is required for every
    switch so a shared or unattended browser cannot be used to jump into
    someone else's character.
    """
    browser_id = _browser_marker(request)
    if not browser_id:
        raise HTTPException(status_code=401, detail="Требуется вход в аккаунт.")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Не удалось прочитать форму.")
    username = str((payload or {}).get("username", "")).strip() if isinstance(payload, dict) else ""
    password = (payload or {}).get("password", "") if isinstance(payload, dict) else ""
    if not isinstance(password, str) or len(password) > 128:
        raise HTTPException(status_code=400, detail="Некорректные данные формы.")
    with sqlite3.connect(DB_PATH) as connection:
        wanted = connection.execute(
            "SELECT b.username_key, a.username FROM browser_sessions b "
            "JOIN user_accounts a ON a.username_key=b.username_key "
            "WHERE b.browser_id=? AND b.username_key=? AND b.last_seen>?",
            (browser_id, username.casefold(), int(time.time()) - SESSION_SECONDS)
        ).fetchone()
        if not wanted:
            raise HTTPException(status_code=403, detail="Этот аккаунт не выполнял вход из данного браузера.")
        account_row = connection.execute(
            "SELECT salt, password_hash FROM user_accounts WHERE username_key=?", (wanted[0],)
        ).fetchone()
    if not account_row:
        raise HTTPException(status_code=404, detail="Аккаунт не найден.")
    salt = bytes.fromhex(account_row[0])
    if not hmac.compare_digest(_password_hash(password, salt).hex(), account_row[1]):
        raise HTTPException(status_code=401, detail="Неверный пароль для этого аккаунта.")
    # Keep the old session alive so switching back stays possible; issue a new cookie.
    _issue_session(wanted[0], request, response)
    _set_browser_marker(response, request)
    return {"ok": True, "username": wanted[1]}


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
    _set_browser_marker(response, request)
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
    _set_browser_marker(response, request)
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
    tree = action_tree(p)
    chosen_class = p.get("class") if p.get("class") in CLASSES else None
    return {"id": pid, "name": p["name"], "x": round(p["x"], 1), "y": round(p["y"], 1),
            "class": chosen_class, "class_name": CLASSES[chosen_class]["name"] if chosen_class else "Путник",
            "class_offer": p["level"] >= CLASS_MIN_LEVEL and not chosen_class,
            "class_compatible": class_compatible(p, tree), "action_tree": tree,
            "weapon_kind": weapon_kind(p), "mastery": mastery_view(p),
            "abilities": abilities_view(p, now), "effects": player_effects(p, now),
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
            "insight_level": int(p.get("insight_level", 0) or 0),
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
            "classes": CLASSES,
            "players": [player_row(pid, p, now) for pid, p in players.items()],
            "mobs": [{**{k: mob[k] for k in ("id", "kind", "level", "x", "y", "hp", "max_hp", "boss")},
                      "telegraphing": mob["telegraph_until"] > now,
                      "burning": float(mob.get("burn_until", 0) or 0) > now,
                      "slowed": float(mob.get("slow_until", 0) or 0) > now,
                      "stunned": float(mob.get("stun_until", 0) or 0) > now,
                      "poisoned": float(mob.get("poison_until", 0) or 0) > now,
                      "marked": any(float((pl_.get("eagle_marks") or {}).get(mob["id"], 0) or 0) > now
                                    for pl_ in players.values())}
                     for mob in mobs if mob["hp"] > 0],
            "nodes": [{k: n[k] for k in ("id", "kind", "x", "y", "active", "zone")} for n in nodes],
            "arrows": [{k: a[k] for k in ("x", "y", "vx", "vy", "life", "kind", "radius", "element", "spell_id", "spell_kind", "spell_rarity", "spell_mastery", "spell_variant", "spell_palette", "max_distance", "travelled") if k in a} for a in arrows],
            "thorn_fields": [{k: field[k] for k in ("x", "y", "radius", "until", "owner")} for field in thorn_fields],
            "ground_effects": [{"id": field["id"], "kind": field["kind"], "x": round(field["x"], 1),
                                 "y": round(field["y"], 1), "radius": field["radius"],
                                 "owner": field.get("owner"), "remaining": round(max(0.0, field["until"] - now), 2),
                                 "telegraph": round(max(0.0, field.get("activate_at", now) - now), 2),
                                 "duration": round(max(.01, field["until"] - field["started"]), 2)}
                                for field in ground_effects]}


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


def broadcast(event: dict[str, Any]) -> None:
    """Fire-and-forget an event without crashing outside the running loop."""
    try:
        asyncio.get_running_loop().create_task(send_event(event))
    except RuntimeError:
        # No event loop here (e.g. called from a login/reconcile path): the
        # player will receive fresh data with the next full snapshot anyway.
        pass


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
    insight = max(0, int(p.get("insight_level", 0) or 0))
    enriched = {**stats, "insight": 1 + insight}
    original = stats
    p = {**p, "stats": enriched}
    result = _upgrades_view_core(p)
    del original
    return result


def _upgrades_view_core(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stats = p.get("stats", {})
    return {
        "might": {"level": int(stats.get("might", 1)), "effect": f"+{(int(stats.get('might', 1))-1)*2.2:.1f} к урону оружия"},
        "vitality": {"level": int(stats.get("vitality", 1)), "effect": f"{int(p.get('max_hp', 100))} макс. здоровья"},
        "agility": {"level": int(stats.get("agility", 1)), "effect": f"{int(p.get('max_stamina', 100))} макс. выносливости"},
        "mana_regen": {"level": int(p.get("mana_regen_level", 0)), "effect": f"+{9 + 1.5*int(p.get('mana_regen_level', 0)):.1f} маны/с"},
        "magic_damage": {"level": int(p.get("magic_damage_level", 0)), "effect": f"+{int(p.get('magic_damage_level', 0))*8}% урона заклинаний"},
        "insight": {"level": max(0, int(p.get("insight_level", 0) or 0)), "effect": f"опыт от побед ×{1 + 0.04*max(0, int(p.get('insight_level', 0) or 0)):.2f}, монеты из-за удачи +{min(60, max(0, int(p.get('insight_level', 0) or 0))*3)}%"},
        "precision": {"level": int(stats.get("precision", 1)), "effect": f"+{min(30, (int(stats.get('precision', 1))-1)*2.5):.1f}% шанс критического удара"},
        "fortune": {"level": int(stats.get("fortune", 1)), "effect": f"+{min(20, (int(stats.get('fortune', 1))-1)*2.5):.1f}% шанс редкой добычи"},
    }



def mastery_required_xp(level: int) -> int:
    level = max(1, min(MASTERY_MAX_LEVEL, int(level)))
    return 0 if level >= MASTERY_MAX_LEVEL else 80 + level * 40


def default_mastery() -> dict[str, dict[str, Any]]:
    return {tree: {"level": 1, "xp": 0, "next": mastery_required_xp(1),
                   "unlocked": [aid for aid, spec in ABILITY_CATALOG.items()
                                if spec["tree"] == tree and spec["mastery"] <= 1]}
            for tree in MASTERY_TREES}


def normalize_mastery(raw: Any) -> dict[str, dict[str, Any]]:
    """Migrate old or damaged saves to neutral mastery without touching character progress."""
    source = raw if isinstance(raw, dict) else {}
    result: dict[str, dict[str, Any]] = {}
    for tree in MASTERY_TREES:
        entry = source.get(tree) if isinstance(source.get(tree), dict) else {}
        level = max(1, min(MASTERY_MAX_LEVEL, int(entry.get("level", 1) or 1)))
        xp = max(0, min(100000, int(entry.get("xp", 0) or 0)))
        needed = mastery_required_xp(level)
        if needed and xp >= needed:
            xp = max(0, needed - 1)
        result[tree] = {
            "level": level, "xp": xp, "next": needed,
            "total_xp": max(0, min(1000000, int(entry.get("total_xp", xp) or xp))),
            "unlocked": [aid for aid, spec in ABILITY_CATALOG.items()
                         if spec["tree"] == tree and spec["mastery"] <= level],
        }
    return result


def mastery_level(p: dict[str, Any], tree: str) -> int:
    entry = p.get("mastery", {}).get(tree, {}) if isinstance(p.get("mastery"), dict) else {}
    return max(1, min(MASTERY_MAX_LEVEL, int(entry.get("level", 1) or 1)))


def mastery_view(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    view: dict[str, dict[str, Any]] = {}
    for tree in MASTERY_TREES:
        entry = p.get("mastery", {}).get(tree, {}) if isinstance(p.get("mastery"), dict) else {}
        level = mastery_level(p, tree)
        unlocked = [aid for aid, spec in ABILITY_CATALOG.items()
                    if spec["tree"] == tree and spec["mastery"] <= level]
        view[tree] = {"name": MASTERY_NAMES[tree], "level": level, "max": MASTERY_MAX_LEVEL,
                      "xp": max(0, int(entry.get("xp", 0) or 0)),
                      "next": mastery_required_xp(level), "unlocked": unlocked}
    return view


def ability_unlocked(p: dict[str, Any], ability_id: str) -> bool:
    spec = ABILITY_CATALOG.get(ability_id)
    return bool(spec and spec["mastery"] <= mastery_level(p, spec["tree"]))


def ability_cooldown_seconds(p: dict[str, Any], ability_id: str) -> float:
    spec = ABILITY_CATALOG.get(ability_id, {})
    mastery = mastery_level(p, str(spec.get("tree", "warrior")))
    return round(max(1.5, float(spec.get("cooldown", 8.0)) * (1 - .03 * (mastery - 1))), 2)


def weapon_kind(p: dict[str, Any]) -> str:
    return str(WEAPONS.get(p.get("weapon", ""), {}).get("kind", "melee"))


def action_tree(p: dict[str, Any]) -> str:
    return WEAPON_TREE.get(weapon_kind(p), "warrior")


def class_compatible(p: dict[str, Any], tree: str | None = None) -> bool:
    tree = tree or action_tree(p)
    chosen = p.get("class")
    if not chosen:
        # Before the class choice the old spell system stays available with any weapon.
        return tree == "mage"
    return chosen == tree


def player_effects(p: dict[str, Any], now: float) -> list[dict[str, Any]]:
    effects: list[dict[str, Any]] = []
    roar_until = float(p.get("roar_until", 0) or 0)
    guard_until = float(p.get("guard_until", 0) or 0)
    if roar_until > now:
        effects.append({"kind": "roar", "name": "Свирепый рык", "remaining": round(roar_until - now, 2)})
    if guard_until > now:
        effects.append({"kind": "guard", "name": "Железная стойка", "remaining": round(guard_until - now, 2)})
    bloodhunt_until = float(p.get("bloodhunt_until", 0) or 0)
    if bloodhunt_until > now:
        effects.append({"kind": "bloodhunt", "name": "Жажда крови", "remaining": round(bloodhunt_until - now, 2)})
    marks = p.get("eagle_marks") if isinstance(p.get("eagle_marks"), dict) else {}
    for mob_id, until in list(marks.items()):
        try:
            until_value = float(until or 0)
        except (TypeError, ValueError):
            marks.pop(mob_id, None); continue
        if until_value <= now:
            marks.pop(mob_id, None)
        else:
            effects.append({"kind": "eagle_mark", "name": "Метка орла", "target": mob_id,
                            "remaining": round(until_value - now, 2)})
    return effects


def abilities_view(p: dict[str, Any], now: float) -> dict[str, dict[str, Any]]:
    cooldowns = p.get("ability_cooldowns", {}) if isinstance(p.get("ability_cooldowns"), dict) else {}
    result: dict[str, dict[str, Any]] = {}
    for ability_id, spec in ABILITY_CATALOG.items():
        until = float(cooldowns.get(ability_id, 0) or 0)
        result[ability_id] = {
            "id": ability_id, "tree": spec["tree"], "name": spec["name"], "icon": spec.get("icon", "✦"),
            "desc": spec["desc"], "cost": int(spec.get("cost", 0)), "arrows": int(spec.get("arrows", 0)),
            "mastery_required": int(spec["mastery"]), "unlocked": ability_unlocked(p, ability_id),
            "key": spec.get("key", ""), "cooldown": ability_cooldown_seconds(p, ability_id),
            "range": float(spec.get("range", 0) or 0), "radius": float(spec.get("radius", 0) or 0),
            "distance": float(spec.get("distance", 0) or 0), "width": float(spec.get("width", 0) or 0),
            "telegraph": float(spec.get("telegraph", 0) or 0),
            "remaining": max(0.0, round(until - now, 2)),
        }
    return result


def weapon_power(p: dict[str, Any]) -> float:
    spec = WEAPONS.get(p.get("weapon", ""), WEAPONS["sword"])
    upgrade = 0 if spec.get("kind") == "staff" else 6 * item_upgrade_level(p, "weapon", p.get("weapon", ""))
    return (float(spec.get("damage", 0)) + float(spec.get("bonus", 0)) * .55
            + (int(p.get("stats", {}).get("might", 1)) - 1) * 2.2
            + 8 * enchant_level(p, "weapon", p.get("weapon", ""), "sharpness") + upgrade)


def award_mastery(p: dict[str, Any], tree: str, amount: int) -> bool:
    if tree not in MASTERY_TREES or amount <= 0:
        return False
    mastery = p.setdefault("mastery", normalize_mastery({}))
    entry = mastery.setdefault(tree, {"level": 1, "xp": 0, "total_xp": 0, "unlocked": []})
    entry["level"] = max(1, min(MASTERY_MAX_LEVEL, int(entry.get("level", 1) or 1)))
    entry["xp"] = max(0, int(entry.get("xp", 0) or 0)) + int(amount)
    entry["total_xp"] = max(0, int(entry.get("total_xp", 0) or 0)) + int(amount)
    leveled = False
    while entry["level"] < MASTERY_MAX_LEVEL:
        needed = mastery_required_xp(entry["level"])
        if entry["xp"] < needed:
            break
        entry["xp"] -= needed
        entry["level"] += 1
        leveled = True
    entry["next"] = mastery_required_xp(entry["level"])
    entry["unlocked"] = [aid for aid, spec in ABILITY_CATALOG.items()
                         if spec["tree"] == tree and spec["mastery"] <= entry["level"]]
    if leveled:
        broadcast({
            "type": "mastery_update", "target": p.get("id"), "tree": tree,
            "mastery": mastery_view(p), "level": entry["level"],
            "unlocked": entry["unlocked"],
        })
        names = [ABILITY_CATALOG[aid]["name"] for aid in entry["unlocked"]
                 if ABILITY_CATALOG[aid]["mastery"] == entry["level"]]
        text = (f"Мастерство «{MASTERY_NAMES[tree]}» достигло {entry['level']} уровня."
                + (f" Открыто: {', '.join(names)}." if names else ""))
        broadcast({"type": "notice", "target": str(p.get("id", "")), "text": text})
    return leveled


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
        "insight_level": max(0, int(p.get("insight_level", 0) or 0)),
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
                broadcast(stats_updated_event(pid, p))
                break
        broadcast({"type": "notice", "text": f"{p['name']} достиг(ла) {p['level']} уровня — доступно очко развития"})
        if p["level"] >= CLASS_MIN_LEVEL and not p.get("class"):
            broadcast({
                "type": "class_offer", "target": p.get("id"), "level": p["level"],
                "classes": CLASSES,
            })


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
        # Поручения Хранителя дают очко развития — ещё один путь прокачки вне боёв.
        p["skill_points"] = int(p.get("skill_points", 0)) + 1
        p["quest_points"] = int(p.get("quest_points", 0)) + 1
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


def insight_level(p: dict[str, Any]) -> int:
    return max(0, int(p.get("insight_level", 0) or 0))


def award_drop(p: dict[str, Any], mob: dict[str, Any]) -> None:
    kind = mob["kind"]
    inv = p["inventory"]
    p["kills"] += 1
    insight = insight_level(p)
    xp_gain = int(round((MONSTERS[kind]["xp"] + max(0, mob["level"] - MONSTERS[kind]["zone"]) * 7)
                        * (1 + 0.04 * insight)))
    add_xp(p, xp_gain)
    gold_gain = int(round((random.randint(4, 11) + mob["level"]) * (1 + 0.03 * insight)))
    p["gold"] += gold_gain
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
    broadcast({"type": "notice", "target": p["id"], "text": f"Победа над {MONSTERS[kind]['name']}: добыча собрана."})


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
        broadcast({"type": "notice", "target": p["id"], "text": "Слишком мало выносливости — отступи на мгновение."})
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
            broadcast({"type": "notice", "target": p["id"], "text": "Колчан пуст. Стрелы можно изготовить из дерева и руды."})
            return
        p["inventory"]["arrows"] -= 1
        broadcast({"type": "weapon_action", "action": "attack", "id": p["id"],
                                        "weapon": weapon_id, "weapon_kind": spec["kind"],
                                        "x": p["x"], "y": p["y"], "aim_x": ax, "aim_y": ay,
                                        "charge": charge})
        charge_factor = .22 + .78 * charge
        speed = 210 + 500 * charge + (p["stats"]["agility"] - 1) * 8
        arrow_range = 180 + 620 * charge
        charged_damage = max(1, round(damage * charge_factor))
        arrows.append({"x": p["x"] + ax * 18, "y": p["y"] + ay * 18,
                       "vx": ax * speed, "vy": ay * speed, "damage": charged_damage,
                       "owner": p["id"], "life": arrow_range / max(1, speed),
                       "max_distance": arrow_range, "travelled": 0.0, "kind": "arrow", "critical": critical,
                       "hit_ids": []})
        award_mastery(p, "ranger", 5 + int(charge * 3))
        return
    broadcast({"type": "weapon_action", "action": "attack", "id": p["id"],
                                    "weapon": weapon_id, "weapon_kind": spec["kind"],
                                    "x": p["x"], "y": p["y"], "aim_x": ax, "aim_y": ay,
                                    "charge": charge})
    reach = (float(spec.get("range", 44)) + 12 * charge) * melee_reach_factor(p)
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
        if float(p.get("bloodhunt_until", 0) or 0) > now:
            heal = int(ABILITY_CATALOG["bloodhunt"].get("heal_per_hit", 12))
            p["hp"] = min(p["max_hp"], p["hp"] + heal)
            broadcast({"type": "hit_player_heal", "id": p["id"], "heal": heal})
        mob["alert_until"] = now + 4
        if mob["hp"] <= 0:
            mob["hp"] = 0
            mob["respawn_at"] = now + random.uniform(24, 40)
            award_drop(p, mob)
        broadcast({"type": "hit", "mob": mob["id"], "x": mob["x"], "y": mob["y"], "damage": round(damage), "critical": critical})
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
            broadcast({"type": "pvp_hit", "attacker": p["id"], "id": other["id"],
                                            "damage": actual, "x": other["x"], "y": other["y"], "critical": critical})
            if other["hp"] <= 0:
                other["respawn_at"] = now + 5
                other["attack"] = None
                other["gathering"] = None
                broadcast({"type": "notice", "target": other["id"], "text": f"Ты пал в дуэли с {p['name']}. Через несколько секунд вернёшься в лагерь."})
                broadcast({"type": "notice", "target": p["id"], "text": f"Победа в дуэли над {other['name']}!"})
    award_mastery(p, "warrior", 4 + min(6, len(hits)))


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
    spec = CRAFT_RECIPES.get(recipe)
    if not spec:
        return "Такого рецепта нет в самоучителе ремёсел."
    for resource, need in spec["cost"].items():
        if int(inv.get(resource, 0)) < need:
            return f"Не хватает материалов для «{spec['name']}»: нужно {need} × {resource}."
    for resource, need in spec["cost"].items():
        inv[resource] = int(inv.get(resource, 0)) - need
    # Consumables and ammunition simply fill the backpack.
    if recipe in {"arrows", "potion"} or recipe in CONSUMABLES or recipe in {"bandage", "throwing_knife"}:
        amount = {"arrows": 8, "bandage": 3, "throwing_knife": 5}.get(recipe, 1)
        inv[recipe] = int(inv.get(recipe, 0)) + amount
        return f"Изготовлено: {spec['name']}" + (f" ×{amount}." if amount > 1 else ".")
    # Equipment recipes must avoid duplicates.
    if recipe in WEAPONS:
        if recipe in p["weapons"]:
            for resource, need in spec["cost"].items():
                inv[resource] = int(inv.get(resource, 0)) + need
            return "Такое оружие уже выковано — материалы возвращены."
        p["weapons"].append(recipe)
        return f"Сковано: {WEAPONS[recipe]['name']}. Открой инвентарь, чтобы экипировать."
    if recipe in GEAR:
        if recipe == p["gear"] or recipe in p["gear_inventory"]:
            for resource, need in spec["cost"].items():
                inv[resource] = int(inv.get(resource, 0)) + need
            return "Такая броня уже есть в сумке — материалы возвращены."
        grant_gear(p, recipe)
        return f"Собрано: {GEAR[recipe]['name']}. Открой инвентарь, чтобы надеть её."
    return "Рецепт не найден."


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
    guard = 14 if float(p.get("guard_until", 0) or 0) > time.monotonic() else 0
    return (base + 3 * item_upgrade_level(p, "gear", gear_id)
            + 2 * enchant_level(p, "gear", gear_id, "protection") + guard)


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
        elif kind in CONSUMABLES: inv[kind] = inv.get(kind, 0) + 1
        elif kind == "throwing_knife": inv["throwing_knife"] = inv.get("throwing_knife", 0) + 5
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
    # «Метка орла» усиливает весь урон владельца метки по помеченной цели.
    mark = p.get("eagle_marks") if isinstance(p.get("eagle_marks"), dict) else {}
    if float(mark.get(mob["id"], 0) or 0) > now:
        damage *= 1 + float(ABILITY_CATALOG.get("eagle_mark", {}).get("bonus_mult", .25))
    dealt = max(1, round(damage)); mob["hp"] -= dealt; mob["alert_until"] = now + 4
    if mob["hp"] <= 0:
        mob["hp"] = 0; mob["respawn_at"] = now + random.uniform(24, 40); award_drop(p, mob)
    broadcast({"type": "hit", "mob": mob["id"], "x": mob["x"], "y": mob["y"], "damage": dealt})

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


def _ability_event(p: dict[str, Any], ability_id: str, target_x: float, target_y: float,
                   aim_x: float, aim_y: float, **extra: Any) -> dict[str, Any]:
    spec = ABILITY_CATALOG[ability_id]
    return {"type": "ability_cast", "id": p["id"], "ability": ability_id,
            "tree": spec["tree"], "name": spec["name"], "icon": spec.get("icon", "✦"),
            "x": round(p["x"], 1), "y": round(p["y"], 1),
            "from_x": round(p["x"], 1), "from_y": round(p["y"], 1),
            "target_x": round(target_x, 1), "target_y": round(target_y, 1),
            "aim_x": aim_x, "aim_y": aim_y,
            "radius": spec.get("radius", 0), "duration": spec.get("duration", 0), **extra}


def _damage_players_around(p: dict[str, Any], now: float, x: float, y: float, radius: float,
                           damage: float, source: str = "ability") -> None:
    if zone_for_x(p["x"])["danger"] == 0:
        return
    for other in list(players.values()):
        if other["id"] == p["id"] or other.get("respawn_at", 0) > now:
            continue
        if zone_for_x(other["x"])["danger"] == 0:
            continue
        if math.hypot(other["x"] - x, other["y"] - y) > radius:
            continue
        actual = max(1, round(damage * .72) - player_defense(other))
        other["hp"] = max(0, other["hp"] - actual)
        broadcast({"type": "pvp_hit", "attacker": p["id"], "id": other["id"],
                                        "damage": actual, "x": other["x"], "y": other["y"], "source": source})
        if other["hp"] <= 0:
            other["respawn_at"] = now + 5
            other["attack"] = None
            other["gathering"] = None
            broadcast({"type": "notice", "target": other["id"], "text": f"Ты пал в бою с {p['name']}. Через несколько секунд вернёшься в лагерь."})
            broadcast({"type": "notice", "target": p["id"], "text": f"Победа над {other['name']}!"})


STAT_CAPS = {"might": 50, "vitality": 50, "agility": 50,
             "precision": 13, "fortune": 9,
             "mana_regen": 20, "magic_damage": 20, "insight": 15}
LEVEL_BASED_STATS = {"mana_regen": "mana_regen_level", "magic_damage": "magic_damage_level",
                     "insight": "insight_level"}


async def choose_class(p: dict[str, Any], msg: dict[str, Any]) -> None:
    chosen = str(msg.get("class", ""))
    if p.get("class"):
        await tell(p["id"], f"Класс уже выбран: {CLASSES.get(p['class'], {}).get('name', p['class'])}. Изменить его нельзя.")
        return
    if int(p.get("level", 1)) < CLASS_MIN_LEVEL:
        await tell(p["id"], f"Класс выбирается на {CLASS_MIN_LEVEL}-м уровне. Сейчас у тебя {int(p.get('level', 1))}.")
        return
    if chosen not in CLASSES:
        await tell(p["id"], "Неизвестный класс. Выбери Воина, Следопыта или Мага.")
        return
    p["class"] = chosen
    bonus = CLASSES[chosen].get("stat_bonus", {})
    bonus_total = sum(max(0, min(20, int(value))) for value in bonus.values())
    # The class grants a one-time bundle of development points; the signature
    # characteristics are invested automatically so the fantasy stays intact.
    # Because every raised statistic spends exactly one point from this ledger,
    # the pool can never self-replenish when the "+" buttons are clicked.
    p["class_bonus_points"] = int(p.get("class_bonus_points", 0) or 0) + bonus_total
    p["skill_points"] = int(p.get("skill_points", 0) or 0) + bonus_total
    applied: list[str] = []
    spent_on_bonus = 0
    for key, value in bonus.items():
        amount = max(0, min(20, int(value)))
        if not amount:
            continue
        cap = STAT_CAPS.get(key, 50)
        if key in p.get("stats", {}):
            room = max(0, cap - int(p["stats"].get(key, 1)))
            take = min(amount, room)
            if take:
                p["stats"][key] = int(p["stats"].get(key, 1)) + take
                applied.append(f"{stat_names.get(key, key)} +{take}")
                spent_on_bonus += take
        elif key == "mana_regen":
            current = max(0, int(p.get("mana_regen_level", 0) or 0))
            take = min(amount, max(0, cap - current))
            if take:
                p["mana_regen_level"] = current + take
                applied.append(f"восстановление маны +{take}")
                spent_on_bonus += take
        elif key == "magic_damage":
            current = max(0, int(p.get("magic_damage_level", 0) or 0))
            take = min(amount, max(0, cap - current))
            if take:
                p["magic_damage_level"] = current + take
                applied.append(f"сила магии +{take * 8}%")
                spent_on_bonus += take
    spare = max(0, bonus_total - spent_on_bonus)
    if spare:
        applied.append(f"+{spare} свободных очков развития")
    p["stats_revision"] = int(p.get("stats_revision", 0)) + 1
    update_derived(p, heal=True)
    try:
        save_character(p)
    except sqlite3.Error:
        pass
    row = None
    if players.get(str(p["id"])) is p:
        try:
            row = player_row(p["id"], p, time.monotonic())
        except Exception:
            row = None
    await send_event({"type": "class_selected", "target": p["id"], "class": chosen,
                      "class_name": CLASSES[chosen]["name"], "bonus": applied,
                      "player": row})
    await send_event(stats_updated_event(p["id"], p))
    await tell(p["id"], f"Класс выбран: {CLASSES[chosen]['name']}. Постоянные бонусы: {', '.join(applied) or 'нет'}.")


async def use_ability(p: dict[str, Any], now: float, ability_id: str, aim_x: float,
                      aim_y: float, target_x: float | None = None, target_y: float | None = None) -> None:
    spec = ABILITY_CATALOG.get(ability_id)
    if not spec:
        await tell(p["id"], "Неизвестная боевая способность.")
        return
    tree = spec["tree"]
    if not p.get("class"):
        await tell(p["id"], f"Сначала выбери класс на {CLASS_MIN_LEVEL}-м уровне.")
        return
    if p.get("class") != tree:
        await tell(p["id"], f"Способность «{spec['name']}» доступна классу «{MASTERY_NAMES[tree]}».")
        return
    if weapon_kind(p) != TREE_WEAPON_KIND[tree]:
        need = {"melee": "оружие ближнего боя", "bow": "лук", "staff": "посох"}[TREE_WEAPON_KIND[tree]]
        await tell(p["id"], f"Для этой способности нужно подходящее оружие: {need}.")
        return
    if p.get("respawn_at", 0) > now:
        await tell(p["id"], "Нельзя применять способности во время возвращения в лагерь.")
        return
    if now < float(p.get("ability_lock_until", 0) or 0):
        await tell(p["id"], "Персонаж ещё не завершил предыдущее действие.")
        return
    if not ability_unlocked(p, ability_id):
        await tell(p["id"], f"Способность откроется на {spec['mastery']}-м уровне мастерства «{MASTERY_NAMES[tree]}».")
        return
    cooldowns = p.setdefault("ability_cooldowns", {})
    if float(cooldowns.get(ability_id, 0) or 0) > now:
        await tell(p["id"], f"«{spec['name']}» перезаряжается: {float(cooldowns[ability_id]) - now:.1f} с.")
        return
    cost = int(spec.get("cost", 0))
    if float(p.get("stamina", 0)) < cost:
        await tell(p["id"], f"Мало выносливости: нужно {cost}, сейчас {int(p.get('stamina', 0))}.")
        return
    arrow_cost = int(spec.get("arrows", 0))
    if arrow_cost and int(p.get("inventory", {}).get("arrows", 0)) < arrow_cost:
        await tell(p["id"], f"Нужно стрел: {arrow_cost}. Пополни колчан в лагере или изготовь стрелы.")
        return
    # Normalize and clamp every client-provided direction and target.
    if not all(math.isfinite(float(v)) for v in (aim_x, aim_y)):
        aim_x, aim_y = p.get("face_x", 1.0), p.get("face_y", 0.0)
    length = math.hypot(aim_x, aim_y)
    if length < .01:
        aim_x, aim_y = p.get("face_x", 1.0), p.get("face_y", 0.0)
        length = max(.01, math.hypot(aim_x, aim_y))
    aim_x, aim_y = aim_x / length, aim_y / length
    max_range = float(spec.get("range", 0) or 0)
    if target_x is not None and target_y is not None and all(math.isfinite(float(v)) for v in (target_x, target_y)):
        tx, ty = float(target_x), float(target_y)
        dx, dy = tx - p["x"], ty - p["y"]
        distance = math.hypot(dx, dy)
        if max_range and distance > max_range:
            tx, ty = p["x"] + dx / max(1, distance) * max_range, p["y"] + dy / max(1, distance) * max_range
        tx = max(0.0, min(WORLD_W, tx)); ty = max(0.0, min(WORLD_H, ty))
    else:
        tx = max(0.0, min(WORLD_W, p["x"] + aim_x * (max_range or 180)))
        ty = max(0.0, min(WORLD_H, p["y"] + aim_y * (max_range or 180)))
    p["stamina"] -= cost
    if arrow_cost:
        p["inventory"]["arrows"] = max(0, int(p["inventory"].get("arrows", 0)) - arrow_cost)
    cooldowns[ability_id] = now + ability_cooldown_seconds(p, ability_id)
    p["ability_lock_until"] = now + .18
    p["gathering"] = None
    p["attack"] = None
    p["face_x"], p["face_y"] = aim_x, aim_y
    p["last_ability"] = ability_id
    event = _ability_event(p, ability_id, tx, ty, aim_x, aim_y)
    power = weapon_power(p) * float(spec.get("mult", 1.0))
    hits = 0
    if ability_id == "roar":
        p["roar_until"] = max(float(p.get("roar_until", 0) or 0), now + float(spec["duration"]))
        await send_event(event)
        await tell(p["id"], f"Свирепый рык: восстановление здоровья усилено на {spec['duration']:.0f} с.")
    elif ability_id == "iron_guard":
        p["guard_until"] = max(float(p.get("guard_until", 0) or 0), now + float(spec["duration"]))
        await send_event(event)
        await tell(p["id"], f"Железная стойка: +{spec['armor']} брони на {spec['duration']:.0f} с.")
    elif ability_id == "lunge":
        start_x, start_y = p["x"], p["y"]
        travel = float(spec["distance"])
        end_x = max(25.0, min(WORLD_W - 25.0, start_x + aim_x * travel))
        end_y = max(25.0, min(WORLD_H - 25.0, start_y + aim_y * travel))
        # The world has no wall geometry; movement is still stepped and clamped to the
        # authoritative world bounds so a client cannot teleport outside it.
        steps = max(1, int(math.ceil(math.hypot(end_x - start_x, end_y - start_y) / 12)))
        for step in range(1, steps + 1):
            nx = start_x + (end_x - start_x) * step / steps
            ny = start_y + (end_y - start_y) * step / steps
            p["x"] = max(25.0, min(WORLD_W - 25.0, nx))
            p["y"] = max(25.0, min(WORLD_H - 25.0, ny))
        seg_x, seg_y = p["x"] - start_x, p["y"] - start_y
        seg_len = max(.01, math.hypot(seg_x, seg_y))
        for mob in list(mobs):
            if mob["hp"] <= 0:
                continue
            rel_x, rel_y = mob["x"] - start_x, mob["y"] - start_y
            projection = (rel_x * seg_x + rel_y * seg_y) / seg_len
            if projection < -8 or projection > seg_len + 12:
                continue
            perp = abs(rel_x * seg_y - rel_y * seg_x) / seg_len
            if perp <= float(spec["width"]) + (52 if mob.get("boss") else 18):
                spell_damage(p, mob, power, now); hits += 1
        _damage_players_around(p, now, p["x"], p["y"], 58, power, "lunge")
        event["from_x"], event["from_y"] = round(start_x, 1), round(start_y, 1)
        event["x"], event["y"] = round(p["x"], 1), round(p["y"], 1)
        event["target_x"], event["target_y"] = round(p["x"], 1), round(p["y"], 1)
        await send_event(event)
    elif ability_id == "whirlwind":
        for mob in list(mobs):
            if mob["hp"] > 0 and math.hypot(mob["x"] - p["x"], mob["y"] - p["y"]) <= float(spec["radius"]):
                spell_damage(p, mob, power, now); hits += 1
        _damage_players_around(p, now, p["x"], p["y"], float(spec["radius"]), power, "whirlwind")
        await send_event(event)
    elif ability_id == "arrow_rain":
        field = {"id": f"rain-{uuid.uuid4().hex[:8]}", "kind": "arrow_rain", "owner": p["id"],
                 "x": tx, "y": ty, "radius": float(spec["radius"]), "damage": power,
                 "started": now, "activate_at": now + float(spec["telegraph"]),
                 "until": now + float(spec["telegraph"]) + float(spec["duration"]),
                 "next_hit": now + float(spec["telegraph"]), "tick": float(spec["tick"])}
        ground_effects.append(field)
        event["ground"] = {"id": field["id"], "kind": "arrow_rain", "x": round(tx, 1), "y": round(ty, 1),
                           "radius": field["radius"], "telegraph": field["activate_at"] - now,
                           "duration": field["until"] - field["activate_at"]}
        await send_event(event)
    elif ability_id in {"piercing_shot", "fire_arrow", "ice_arrow", "double_shot"}:
        shots = int(spec.get("shots", 1))
        spread = float(spec.get("spread", 0))
        speed = 760.0
        for index in range(shots):
            offset = (index - (shots - 1) / 2) * spread
            ca, sa = math.cos(offset), math.sin(offset)
            sx, sy = aim_x * ca - aim_y * sa, aim_x * sa + aim_y * ca
            max_distance = float(spec.get("range", 760))
            arrow = {"x": p["x"] + sx * 18, "y": p["y"] + sy * 18,
                     "vx": sx * speed, "vy": sy * speed, "damage": max(1, round(power)),
                     "owner": p["id"], "life": max_distance / speed + .08,
                     "max_distance": max_distance, "travelled": 0.0, "kind": "ability_arrow",
                     "element": "fire" if ability_id == "fire_arrow" else "ice" if ability_id == "ice_arrow" else "",
                     "pierce": int(spec.get("pierce", 0)), "hit_ids": [],
                     "burn_duration": float(spec.get("burn_duration", 0) or 0),
                     "burn_tick": float(spec.get("burn_tick", .75) or .75),
                     "burn_damage": max(1, round(power * float(spec.get("burn_mult", .16) or .16))),
                     "slow_duration": float(spec.get("slow_duration", 0) or 0),
                     "slow_factor": float(spec.get("slow_factor", .45) or .45)}
            arrows.append(arrow)
        await send_event(event)
    elif ability_id == "bash":
        for mob in list(mobs):
            if mob["hp"] <= 0:
                continue
            if math.hypot(mob["x"] - p["x"], mob["y"] - p["y"]) <= float(spec["radius"]) + (40 if mob.get("boss") else 12):
                spell_damage(p, mob, power, now); hits += 1
                if mob["hp"] > 0:
                    mob["stun_until"] = now + float(spec.get("stun_duration", 1.6))
                    knock = float(spec.get("knockback", 70.0))
                    ddx, ddy = mob["x"] - p["x"], mob["y"] - p["y"]
                    dd = max(.01, math.hypot(ddx, ddy))
                    mob["x"] = max(25.0, min(WORLD_W - 25.0, mob["x"] + ddx / dd * knock))
                    mob["y"] = max(25.0, min(WORLD_H - 25.0, mob["y"] + ddy / dd * knock))
        _damage_players_around(p, now, p["x"], p["y"], float(spec["radius"]), power, "bash")
        await send_event(event)
    elif ability_id == "bloodhunt":
        p["bloodhunt_until"] = max(float(p.get("bloodhunt_until", 0) or 0), now + float(spec["duration"]))
        await send_event(event)
        await tell(p["id"], f"Жажда крови: каждый удар восстановит {spec['heal_per_hit']} здоровья на {spec['duration']:.0f} с.")
    elif ability_id == "seismic_slam":
        for mob in list(mobs):
            if mob["hp"] <= 0:
                continue
            if math.hypot(mob["x"] - p["x"], mob["y"] - p["y"]) <= float(spec["radius"]) + (48 if mob.get("boss") else 12):
                spell_damage(p, mob, power, now); hits += 1
                if mob["hp"] > 0:
                    mob["slow_until"] = now + float(spec.get("slow_duration", 2.5))
                    mob["slow_factor"] = float(spec.get("slow_factor", .5))
        _damage_players_around(p, now, p["x"], p["y"], float(spec["radius"]), power, "seismic_slam")
        await send_event(event)
    elif ability_id == "poison_arrow":
        arrow = {"x": p["x"] + aim_x * 18, "y": p["y"] + aim_y * 18,
                 "vx": aim_x * 760.0, "vy": aim_y * 760.0, "damage": max(1, round(power)),
                 "owner": p["id"], "life": float(spec.get("range", 760)) / 760.0 + .08,
                 "max_distance": float(spec.get("range", 760)), "travelled": 0.0, "kind": "ability_arrow",
                 "element": "poison", "pierce": int(spec.get("pierce", 0)), "hit_ids": [],
                 "poison_duration": float(spec.get("poison_duration", 4.0)),
                 "poison_tick": float(spec.get("poison_tick", .8)),
                 "poison_damage": max(1, round(power * float(spec.get("poison_mult", .14))))}
        arrows.append(arrow)
        await send_event(event)
    elif ability_id == "blackout_bolt":
        arrow = {"x": p["x"] + aim_x * 18, "y": p["y"] + aim_y * 18,
                 "vx": aim_x * 760.0, "vy": aim_y * 760.0, "damage": max(1, round(power)),
                 "owner": p["id"], "life": float(spec.get("range", 700)) / 760.0 + .08,
                 "max_distance": float(spec.get("range", 700)), "travelled": 0.0, "kind": "ability_arrow",
                 "element": "shadow", "pierce": int(spec.get("pierce", 0)), "hit_ids": [],
                 "stun_duration": float(spec.get("stun_duration", 1.8))}
        arrows.append(arrow)
        await send_event(event)
    elif ability_id == "eagle_mark":
        marked = None
        candidates = [m for m in mobs if m["hp"] > 0 and math.hypot(m["x"] - tx, m["y"] - ty) <= 96]
        if candidates:
            marked = min(candidates, key=lambda m: math.hypot(m["x"] - tx, m["y"] - ty))
        marks = p.setdefault("eagle_marks", {})
        if marked is not None:
            marks[marked["id"]] = now + float(spec["duration"])
            event["target_x"], event["target_y"] = round(marked["x"], 1), round(marked["y"], 1)
            await send_event(event)
            await tell(p["id"], f"Метка орла нанесена: урон по цели +{int(float(spec['bonus_mult']) * 100)}% на {spec['duration']:.0f} с.")
        else:
            await send_event(event)
            await tell(p["id"], "Метку не удалось нанести: рядом с точкой прицела нет живой цели.")
    award_mastery(p, tree, 8 + int(spec["mastery"]) * 2)
    if hits:
        try:
            save_character(p)
        except sqlite3.Error:
            pass


async def cast_spell(p: dict[str, Any], now: float, spell_id: str, aim_x: float, aim_y: float,
                     target_x: float | None = None, target_y: float | None = None) -> None:
    catalog = all_spells(p)
    spec = catalog.get(spell_id)
    if not spec: await tell(p["id"], "Неизвестное заклинание."); return
    if p.get("class") and p.get("class") != "mage":
        await tell(p["id"], "Заклинания доступны классу «Маг». Воин и Следопыт используют свои боевые способности.")
        return
    if p.get("class") == "mage" and weapon_kind(p) != "staff":
        await tell(p["id"], "Для заклинаний нужен посох. Сейчас в руках другое оружие.")
        return
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
    power = (1.0 + staff_power + 0.08 * int(p.get("magic_damage_level", 0))
             + 0.02 * (mastery_level(p, "mage") - 1))
    spell_damage_base = float(spec.get("damage", 0)) + staff_upgrade
    update_derived(p)
    if equipped_weapon.get("kind") == "staff":
        award_mastery(p, "mage", 4 + int(spec.get("mana", 0)) // 8)
    for unlocked_id, unlocked_spec in catalog.items():
        threshold = int(unlocked_spec.get("unlock_spent", 0))
        if threshold and old_spent < threshold <= p["magic_mana_spent"]:
            broadcast({"type": "notice", "target": p["id"], "text": f"Открыто заклинание «{unlocked_spec['name']}»! Требуется также уровень {unlocked_spec['unlock_level']}."})
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


def stat_current_level(p: dict[str, Any], stat: str) -> int:
    if stat in LEVEL_BASED_STATS:
        return max(0, int(p.get(LEVEL_BASED_STATS[stat], 0) or 0))
    return max(1, int(p.get("stats", {}).get(stat, 1) or 1))


def count_spent_points(p: dict[str, Any]) -> int:
    """Every point above a stat's starting value was paid for with a development point."""
    spent = sum(max(0, int(value or 1) - 1) for value in p.get("stats", {}).values())
    spent += max(0, int(p.get("mana_regen_level", 0) or 0))
    spent += max(0, int(p.get("magic_damage_level", 0) or 0))
    spent += max(0, int(p.get("insight_level", 0) or 0))
    return spent


def reconcile_skill_points(p: dict[str, Any]) -> None:
    """Never lose earned points: recompute what remains after all purchases.

    Level-ups grant one point per level, the class choice grants its own bonus
    points, and every raised statistic spends exactly one point. Reconciling on
    login and after each change keeps the pool truthful even for older saves.
    """
    earned = max(0, int(p.get("level", 1)) - 1)
    earned += max(0, int(p.get("quest_points", 0) or 0))
    earned += max(0, int(p.get("class_bonus_points", 0) or 0))
    if not p.get("class_bonus_points"):
        # Legacy saves from before the class-point ledger: their stat_bonus was
        # already written into the statistics, so count it as earned only there.
        chosen = p.get("class")
        if chosen in CLASSES:
            earned += sum(max(0, int(value or 0))
                          for value in CLASSES[chosen].get("stat_bonus", {}).values())
    p["skill_points"] = max(int(p.get("skill_points", 0) or 0),
                            earned - count_spent_points(p))


async def apply_stat_upgrade(pid: str, p: dict[str, Any], stat: str) -> None:
    """Spend one development point on a characteristic — single source of truth."""
    if stat not in STAT_CAPS:
        await tell(pid, "Неизвестная характеристика для улучшения.")
        return
    # The server is authoritative about the pool; repair it before deciding.
    reconcile_skill_points(p)
    if int(p.get("skill_points", 0)) <= 0:
        await tell(pid, "Нет свободных очков развития. Получай уровни за бой и поручения.")
        return
    current_level = stat_current_level(p, stat)
    if current_level >= STAT_CAPS[stat]:
        await tell(pid, "Эта характеристика уже достигла предела.")
        return
    level_based = {"mana_regen": "mana_regen_level", "magic_damage": "magic_damage_level",
                   "insight": "insight_level"}
    if stat in level_based:
        p[level_based[stat]] = current_level + 1
    else:
        p["stats"][stat] = current_level + 1
    p["skill_points"] = max(0, int(p.get("skill_points", 0)) - 1)
    update_derived(p, heal=stat == "vitality")
    if stat == "mana_regen":
        await tell(pid, f"Восстановление маны улучшено до уровня {p['mana_regen_level']}.")
    elif stat == "magic_damage":
        await tell(pid, f"Сила магии улучшена: +{p['magic_damage_level'] * 8}% урона от заклинаний.")
    elif stat == "insight":
        await tell(pid, f"Прозорливость повышена: опыт от побед ×{1 + 0.04 * p['insight_level']:.2f}, добыча монет +{min(60, p['insight_level'] * 3)}%.")
    else:
        await tell(pid, f"Развитие улучшено: {stat_names[stat]} · теперь {p['stats'][stat]}.")
    p["stats_revision"] = int(p.get("stats_revision", 0)) + 1
    try:
        save_character(p)
    except sqlite3.Error:
        pass
    await send_event(stats_updated_event(pid, p))
    # A second, complete row for the owner so every HUD/panel copy refreshes
    # even if the lightweight stats event gets coalesced or lost on the wire.
    # (Only possible while the character is actually online in the world.)
    if players.get(pid) is p:
        try:
            await send_event({"type": "player_update", "target": pid,
                              "player": player_row(pid, p, time.monotonic())})
        except Exception:
            pass


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
    elif kind == "choose_class":
        await choose_class(p, msg)
    elif kind == "ability":
        try:
            aim_x = float(msg.get("aim_x", 0)); aim_y = float(msg.get("aim_y", 0))
            target_x = float(msg["target_x"]) if msg.get("target_x") is not None else None
            target_y = float(msg["target_y"]) if msg.get("target_y") is not None else None
            await use_ability(p, now, str(msg.get("ability", "")), aim_x, aim_y, target_x, target_y)
        except (TypeError, ValueError, KeyError):
            await tell(pid, "Не удалось прочитать направление способности.")
        except Exception as exc:
            print(f"ability action failed for {pid}: {exc}")
            await tell(pid, "Способность не удалось применить. Соединение сохранено.")
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
            if now < float(p.get("ability_lock_until", 0) or 0):
                await tell(pid, "Дождись завершения текущей способности, затем смени оружие.")
                return
            p["weapon"] = weapon
            # Changing a weapon cancels an unfinished wind-up instead of letting it fire
            # with the old weapon's data.
            p["attack"] = None
            p["gathering"] = None
            p["ability_lock_until"] = now + .12
            await sync_station_state(p)
            tree = action_tree(p)
            if p.get("class") and p.get("class") != tree:
                if tree == "mage":
                    await tell(pid, "Оружие экипировано, но заклинания доступны только классу «Маг».")
                else:
                    await tell(pid, f"Оружие экипировано, но способности «{MASTERY_NAMES.get(tree, tree)}» недоступны твоему классу.")
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
    elif kind == "sync":
        # The client asks for an authoritative copy of its own row.
        await send_event({"type": "player_update", "target": pid,
                          "player": player_row(pid, p, now)})
    elif kind == "upgrade":
        await apply_stat_upgrade(pid, p, str(msg.get("stat", "")))
    elif kind == "upgrade_http":
        # Резервный путь применения очков развития (если WebSocket-событие потерялось).
        stat = str(msg.get("stat", ""))
        await handle_message(pid, p, {"type": "upgrade", "stat": stat}, now)
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
EXTRA_STAT_NAMES = {"insight": "Прозорливость"}
PERSIST_FIELDS = (
    "x", "y", "hp", "stamina", "xp", "level", "skill_points", "stats",
    "gold", "kills", "weapon", "weapons", "gear", "gear_inventory",
    "inventory", "quest_stage", "quest_active", "quest_kills", "quest_gather", "quest_points",
    "class_bonus_points",
    "enchantments", "market_starter_grant", "magic_mana_spent", "upgrades", "mana_regen_level", "magic_damage_level", "insight_level", "spell_uses", "custom_spells",
    "class", "mastery", "ability_cooldowns",
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


def _browser_marker(request: Request) -> str | None:
    """Stable per-browser id derived from the persistent echo_browser cookie."""
    marker = request.cookies.get("echo_browser")
    if not marker or len(marker) > 64 or not re.fullmatch(r"[A-Za-z0-9_-]+", marker):
        return None
    return marker


def _set_browser_marker(response: Response, request: Request) -> None:
    marker = _browser_marker(request) or secrets.token_urlsafe(24)
    response.set_cookie("echo_browser", marker, max_age=400 * 86400,
                        secure=request.url.scheme == "https", samesite="lax", path="/")


def _issue_session(username_key: str, request: Request, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires = int(time.time()) + SESSION_SECONDS
    with sqlite3.connect(DB_PATH) as connection:
        # Remember every session this browser has signed into (max 6), so the
        # account-switch menu can list them later. Sessions for other players'
        # browsers live under different markers and stay invisible here.
        connection.execute(
            "CREATE TABLE IF NOT EXISTS browser_sessions ("
            "browser_id TEXT NOT NULL, username_key TEXT NOT NULL, last_seen INTEGER NOT NULL, "
            "PRIMARY KEY(browser_id, username_key))"
        )
        # Stable per-browser marker: a long-lived non-httpOnly cookie that
        # survives logout and session expiry, so the roster keeps working even
        # after the player signs out of every account in this browser.
        browser_id = _browser_marker(request)
        if not browser_id:
            browser_id = secrets.token_urlsafe(24)
            response.set_cookie("echo_browser", browser_id, max_age=400 * 86400,
                                secure=request.url.scheme == "https", samesite="lax", path="/")
        connection.execute(
            "DELETE FROM browser_sessions WHERE last_seen<?", (int(time.time()) - SESSION_SECONDS,)
        )
        if not connection.execute(
            "SELECT 1 FROM browser_sessions WHERE browser_id=? AND username_key=?",
            (browser_id, username_key)
        ).fetchone() and connection.execute(
            "SELECT COUNT(*) FROM browser_sessions WHERE browser_id=?", (browser_id,)
        ).fetchone()[0] >= 6:
            raise HTTPException(status_code=400, detail="Слишком много аккаунтов в этом браузере.")
        connection.execute(
            "INSERT OR REPLACE INTO browser_sessions(browser_id, username_key, last_seen) VALUES (?, ?, ?)",
            (browser_id, username_key, int(time.time()))
        )
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


def browser_account_roster(browser_id: str | None) -> list[dict[str, Any]]:
    """Accounts this browser signed into, with level/class from their saves.

    Reads only the browser_sessions rows keyed by this browser's marker, so
    accounts belonging to other players are never listed here.
    """
    if not browser_id:
        return []
    roster: list[dict[str, Any]] = []
    try:
        with sqlite3.connect(DB_PATH) as connection:
            rows = connection.execute(
                "SELECT b.username_key, a.username FROM browser_sessions b "
                "JOIN user_accounts a ON a.username_key=b.username_key "
                "WHERE b.browser_id=? AND b.last_seen>? ORDER BY b.last_seen DESC",
                (browser_id, int(time.time()) - SESSION_SECONDS)
            ).fetchall()
            for username_key, username in rows:
                level, class_name = 1, "Путник"
                save_row = connection.execute(
                    "SELECT data FROM character_saves WHERE name=?", (username_key,)
                ).fetchone()
                if save_row:
                    try:
                        data = json.loads(save_row[0])
                        level = int(data.get("level") or 1)
                        chosen = data.get("class")
                        if isinstance(chosen, str) and chosen in CLASSES:
                            class_name = CLASSES[chosen]["name"]
                    except (ValueError, TypeError, json.JSONDecodeError):
                        pass
                roster.append({"username": username, "level": level, "class": class_name})
    except sqlite3.Error:
        return []
    return roster


def save_character(p: dict[str, Any]) -> None:
    data = {key: p[key] for key in PERSIST_FIELDS if key in p}
    # Store cooldowns as remaining seconds: monotonic clocks restart with the process,
    # while the player's cooldown progress should survive a normal reconnect.
    now = time.monotonic()
    data["ability_cooldowns"] = {
        str(ability_id): round(max(0.0, min(300.0, float(until) - now)), 2)
        for ability_id, until in (p.get("ability_cooldowns", {}) or {}).items()
        if str(ability_id) in ABILITY_CATALOG
    }
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
            if float(p.get("roar_until", 0) or 0) > now:
                p["hp"] = min(p["max_hp"], p["hp"] + 6.0 * dt)
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
            if float(mob.get("burn_until", 0) or 0) > now and float(mob.get("burn_next", 0) or 0) <= now:
                owner = players.get(str(mob.get("burn_owner", "")))
                mob["burn_next"] = now + max(.35, float(mob.get("burn_tick", .75) or .75))
                if owner and owner.get("respawn_at", 0) <= now:
                    spell_damage(owner, mob, float(mob.get("burn_damage", 1) or 1), now)
                if mob["hp"] <= 0:
                    continue
            if float(mob.get("poison_until", 0) or 0) > now and float(mob.get("poison_next", 0) or 0) <= now:
                owner = players.get(str(mob.get("poison_owner", "")))
                mob["poison_next"] = now + max(.35, float(mob.get("poison_tick", .8) or .8))
                if owner and owner.get("respawn_at", 0) <= now:
                    spell_damage(owner, mob, float(mob.get("poison_damage", 1) or 1), now)
                if mob["hp"] <= 0:
                    continue
            slow_active = float(mob.get("slow_until", 0) or 0) > now
            mob_speed = float(mob["speed"]) * (float(mob.get("slow_factor", .45) or .45) if slow_active else 1.0)
            if float(mob.get("stun_until", 0) or 0) > now:
                continue
            target = min((p for p in players.values() if p["respawn_at"] <= now and
                          zone_for_x(p["x"])["danger"] > 0 and
                          zone_for_x(p["x"])["id"] == zone_for_x(mob["x"])["id"]),
                         key=lambda p: math.hypot(p["x"] - mob["x"], p["y"] - mob["y"]), default=None)
            if target is None:
                if now > mob["wander_at"]:
                    mob["wander_x"], mob["wander_y"] = random.uniform(-1, 1), random.uniform(-1, 1)
                    mob["wander_at"] = now + random.uniform(1.2, 3.3)
                mob["x"] += mob["wander_x"] * mob_speed * .16 * dt
                mob["y"] += mob["wander_y"] * mob_speed * .16 * dt
                continue
            dx, dy = target["x"] - mob["x"], target["y"] - mob["y"]
            dist = math.hypot(dx, dy)
            if dist > 300 and now > mob["wander_at"]:
                mob["wander_x"], mob["wander_y"] = random.uniform(-1, 1), random.uniform(-1, 1)
                mob["wander_at"] = now + 2
            elif dist < 260 and dist > MONSTERS[mob["kind"]]["range"] * .72:
                mob["x"] += dx / max(1, dist) * mob_speed * dt
                mob["y"] += dy / max(1, dist) * mob_speed * dt
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
        for field in list(ground_effects):
            if field["until"] <= now:
                ground_effects.remove(field)
                continue
            if now < float(field.get("activate_at", 0) or 0) or now < float(field.get("next_hit", 0) or 0):
                continue
            field["next_hit"] = now + max(.25, float(field.get("tick", .55) or .55))
            owner = players.get(field.get("owner"))
            if not owner or owner.get("respawn_at", 0) > now:
                continue
            radius = float(field.get("radius", 0) or 0)
            for mob in list(mobs):
                if mob["hp"] > 0 and math.hypot(mob["x"] - field["x"], mob["y"] - field["y"]) <= radius:
                    spell_damage(owner, mob, float(field.get("damage", 1) or 1), now)
            _damage_players_around(owner, now, float(field["x"]), float(field["y"]),
                                   radius, float(field.get("damage", 1) or 1) * .8, "arrow_rain")
            await send_event({"type": "ground_pulse", "id": field["id"], "kind": field["kind"],
                              "x": round(float(field["x"]), 1), "y": round(float(field["y"]), 1),
                              "radius": radius, "owner": field.get("owner")})
        for arrow in list(arrows):
            step_distance = math.hypot(arrow["vx"] * dt, arrow["vy"] * dt)
            arrow["x"] += arrow["vx"] * dt; arrow["y"] += arrow["vy"] * dt
            arrow["life"] -= dt
            if arrow.get("max_distance") is not None:
                arrow["travelled"] = float(arrow.get("travelled", 0.0)) + step_distance
                if arrow["travelled"] >= float(arrow["max_distance"]):
                    arrow["life"] = 0
            shooter = players.get(arrow.get("owner"))
            is_ability_arrow = arrow.get("kind") == "ability_arrow"
            hit_ids = arrow.setdefault("hit_ids", []) if is_ability_arrow else []
            player_target = next((p for p in players.values()
                                  if arrow.get("kind") != "spell_projectile"
                                  and p["id"] != arrow.get("owner") and p["respawn_at"] <= now
                                  and p["id"] not in hit_ids
                                  and zone_for_x(p["x"])["danger"] > 0
                                  and math.hypot(p["x"] - arrow["x"], p["y"] - arrow["y"]) < 28), None)
            if player_target and shooter and zone_for_x(shooter["x"])["danger"] > 0:
                defense = player_defense(player_target)
                actual = max(1, round(arrow["damage"] * .72) - defense)
                player_target["hp"] = max(0, player_target["hp"] - actual)
                await send_event({"type": "pvp_hit", "attacker": shooter["id"], "id": player_target["id"],
                                  "damage": actual, "x": player_target["x"], "y": player_target["y"],
                                  **({"element": arrow.get("element", "")} if is_ability_arrow else {})})
                if player_target["hp"] <= 0:
                    player_target["respawn_at"] = now + 5
                    player_target["attack"] = None
                    player_target["gathering"] = None
                    await tell(player_target["id"], f"Ты пал в дуэли с {shooter['name']}. Через несколько секунд вернёшься в лагерь.")
                    await tell(shooter["id"], f"Победа в дуэли над {player_target['name']}!")
                if is_ability_arrow:
                    hit_ids.append(player_target["id"])
                    arrow["pierce"] = int(arrow.get("pierce", 0)) - 1
                    if arrow["pierce"] > 0:
                        continue
                arrows.remove(arrow)
                continue
            safe_player = next((p for p in players.values() if p["id"] != arrow.get("owner")
                                and zone_for_x(p["x"])["danger"] == 0
                                and math.hypot(p["x"] - arrow["x"], p["y"] - arrow["y"]) < 28), None)
            if safe_player:
                arrows.remove(arrow)
                continue
            target = next((m for m in mobs if m["hp"] > 0 and m["id"] not in hit_ids
                           and math.hypot(m["x"] - arrow["x"], m["y"] - arrow["y"]) < (52 if m["boss"] else 30)), None)
            expired = arrow["life"] <= 0 or not (0 <= arrow["x"] <= WORLD_W and 0 <= arrow["y"] <= WORLD_H)
            if is_ability_arrow and target:
                owner = players.get(arrow.get("owner"))
                if owner:
                    spell_damage(owner, target, float(arrow["damage"]), now)
                    element = str(arrow.get("element", "") or "")
                    if element == "fire" and target["hp"] > 0:
                        until = now + float(arrow.get("burn_duration", 0) or 0)
                        # Igniting an already burning target refreshes the timer but never stacks
                        # a second independent damage-over-time instance.
                        if until > float(target.get("burn_until", 0) or 0):
                            target["burn_until"] = until
                        target["burn_next"] = min(float(target.get("burn_next", now) or now), now + .05)
                        target["burn_owner"] = owner["id"]
                        target["burn_damage"] = float(arrow.get("burn_damage", 1) or 1)
                        target["burn_tick"] = float(arrow.get("burn_tick", .75) or .75)
                        target["burn_until"] = max(float(target.get("burn_until", 0) or 0), until)
                    elif element == "ice" and target["hp"] > 0:
                        target["slow_until"] = now + float(arrow.get("slow_duration", 0) or 0)
                        target["slow_factor"] = float(arrow.get("slow_factor", .45) or .45)
                    elif element == "poison" and target["hp"] > 0:
                        until = now + float(arrow.get("poison_duration", 0) or 0)
                        # Яд обновляет длительность, но не складывается в несколько DoT.
                        if until > float(target.get("poison_until", 0) or 0):
                            target["poison_until"] = until
                        target["poison_next"] = min(float(target.get("poison_next", now) or now), now + .05)
                        target["poison_owner"] = owner["id"]
                        target["poison_damage"] = float(arrow.get("poison_damage", 1) or 1)
                        target["poison_tick"] = float(arrow.get("poison_tick", .8) or .8)
                        target["poison_until"] = max(float(target.get("poison_until", 0) or 0), until)
                    elif element == "shadow" and target["hp"] > 0:
                        target["stun_until"] = now + float(arrow.get("stun_duration", 1.8) or 1.8)
                        target["telegraph_until"] = 0.0
                hit_ids.append(target["id"])
                await send_event({"type": "ability_impact", "ability": "arrow", "element": arrow.get("element", ""),
                                  "x": round(target["x"], 1), "y": round(target["y"], 1),
                                  "owner": arrow.get("owner")})
                arrow["pierce"] = int(arrow.get("pierce", 0)) - 1
                if arrow["pierce"] > 0 and not expired:
                    continue
                arrows.remove(arrow)
                continue
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
                broadcast({"type": "hit", "mob": target["id"], "x": target["x"], "y": target["y"], "damage": round(arrow["damage"])})
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


@app.post("/api/stats/upgrade")
async def stats_upgrade_endpoint(request: Request) -> dict[str, Any]:
    """Spend one development point via HTTP — WebSocket-resilient fallback."""
    account = _account_for_token(request.cookies.get("echo_session"))
    if not account:
        return {"ok": False, "error": "Требуется вход в аккаунт."}
    name = safe_name(account["username"])
    try:
        body = await request.json()
    except (ValueError, TypeError):
        return {"ok": False, "error": "Некорректный запрос."}
    stat = str(body.get("stat", ""))
    p = players.get(name)  # players is keyed by pid; look up by name below
    target = next((pl for pl in players.values() if pl.get("name") == name), None)
    if target is None:
        return {"ok": False, "error": "Персонаж сейчас не в мире. Зайдите и повторите."}
    before_points = int(target.get("skill_points", 0) or 0)
    before_stats = dict(target.get("stats", {}))
    before_levels = (int(target.get("mana_regen_level", 0) or 0),
                     int(target.get("magic_damage_level", 0) or 0),
                     int(target.get("insight_level", 0) or 0))
    await handle_message(str(target.get("id", "")), target,
                         {"type": "upgrade", "stat": stat}, time.monotonic())
    changed = (dict(target.get("stats", {})) != before_stats
               or (int(target.get("mana_regen_level", 0) or 0),
                   int(target.get("magic_damage_level", 0) or 0),
                   int(target.get("insight_level", 0) or 0)) != before_levels)
    return {"ok": changed,
            "spent": changed and int(target.get("skill_points", 0)) < before_points,
            "skill_points": int(target.get("skill_points", 0) or 0),
            "upgrades_view": upgrades_view(target),
            "stats": dict(target.get("stats", {}))}


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
         "xp": 0, "level": 1, "skill_points": 0, "quest_points": 0, "class_bonus_points": 0, "stats": {"might": 1, "vitality": 1, "agility": 1, "precision": 1, "fortune": 1},
         "gold": 0, "kills": 0, "last_attack": 0.0, "attack": None, "respawn_at": 0.0,
         "mana": 60, "max_mana": 60, "spell_cooldowns": {}, "spell_uses": {}, "custom_spells": {},
         "enchantments": {"weapon": {}, "gear": {}}, "upgrades": {"weapon": {}, "gear": {}},
         "magic_mana_spent": 0, "market_starter_grant": False,
         "mana_regen_level": 0, "magic_damage_level": 0, "insight_level": 0,
         "class": None, "mastery": default_mastery(), "ability_cooldowns": {},
         "roar_until": 0.0, "guard_until": 0.0, "bloodhunt_until": 0.0, "eagle_marks": {},
         "ability_lock_until": 0.0,
         "dodge_at": 0.0, "dodge_until": 0.0, "weapon": "sword", "weapons": ["sword", "axe", "bow"],
         "gear": "traveler", "gear_inventory": [],
         "inventory": {"wood": 0, "herb": 0, "ore": 0, "hide": 0, "slime": 0, "crystal": 0, "shard": 0, "potion": 2, "arrows": 18},
         "quest_stage": 0, "quest_active": False, "quest_kills": {}, "quest_gather": {},
         "gathering": None, "last_chat": 0.0}
    saved = load_character(name)
    p.update(saved)
    # Safe migration for old saves: missing class/mastery/cooldowns become neutral,
    # while every existing level, item, spell and statistic is kept intact.
    if p.get("class") not in CLASSES:
        p["class"] = None
    p["mastery"] = normalize_mastery(p.get("mastery"))
    saved_cooldowns = p.get("ability_cooldowns") if isinstance(p.get("ability_cooldowns"), dict) else {}
    p["ability_cooldowns"] = {
        str(ability_id): time.monotonic() + max(0.0, min(300.0, float(remaining)))
        for ability_id, remaining in saved_cooldowns.items()
        if str(ability_id) in ABILITY_CATALOG
    }
    p["roar_until"] = 0.0
    p["guard_until"] = 0.0
    p["bloodhunt_until"] = 0.0
    if not isinstance(p.get("eagle_marks"), dict):
        p["eagle_marks"] = {}
    p["ability_lock_until"] = 0.0
    p["x"] = max(25.0, min(WORLD_W - 25.0, float(p["x"])))
    p["y"] = max(25.0, min(WORLD_H - 25.0, float(p["y"])))
    p["level"] = max(1, int(p.get("level", 1)))
    p["stats"] = {key: max(1, int(p.get("stats", {}).get(key, 1)))
                  for key in stat_names}
    # Recover unspent level-up points in older saves where the UI/action path failed.
    reconcile_skill_points(p)
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
    p["insight_level"] = max(0, min(STAT_CAPS["insight"], int(p.get("insight_level", 0) or 0)))
    if not isinstance(p.get("upgrades"), dict): p["upgrades"] = {"weapon": {}, "gear": {}}
    p["upgrades"].setdefault("weapon", {}); p["upgrades"].setdefault("gear", {})
    if not p.get("market_starter_grant", False):
        p["gold"] = max(0, int(p.get("gold", 0))) + 150
        p["market_starter_grant"] = True
    p["quest_stage"] = max(0, min(len(QUESTS), int(p["quest_stage"])))
    update_derived(p)
    players[pid] = p; clients[pid] = websocket
    await websocket.send_text(json.dumps(snapshot(pid), ensure_ascii=False))
    if p["level"] >= CLASS_MIN_LEVEL and not p["class"]:
        await send_event({"type": "class_offer", "target": pid, "level": p["level"],
                          "classes": CLASSES})
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
