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
from encounters import advance_attack, attack_contains, attack_view, backstab, boss_phase
from bestiary import MAX_BESTIARY_KILLS, build_catalog, sanitize_kills

from world import (
    MAP_W, MAP_H, SPAWN, REGIONS, NPCS, PORTALS, POWER_SITES, REGION_QUESTS, POPULATION,
    ZONES, NPC_RADIUS, PORTAL_RADIUS, COMBAT_LOCK, region_for, is_safe, same_region,
    near_npc, nearest_npc, build_shops, public_region, atlas_view, migrate_position, populate,
    resolve_collision, collision_blocked,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "echo_saves.sqlite3"
WORLD_W, WORLD_H = MAP_W, MAP_H
SNAPSHOT_INTERVAL = 0.05
TICK = 0.025
MAX_PLAYERS = 8
# Молчание клиента дольше этого времени означает, что вкладка закрыта/уснула,
# но TCP-соединение осталось «висеть» на сервере. Такой слот принудительно
# освобождается (с сохранением персонажа), чтобы не забирать место у живых игроков.
IDLE_TIMEOUT = 45.0
CLEANUP_INTERVAL = 5.0
HEARTBEAT_INTERVAL = 10.0

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
    # Новые виды оружия (ближний бой, луки/арбалеты, жезлы/фолианты/посохи)
    "twinblades": {"name": "Парные серпы ветра", "kind": "melee", "damage": 23, "bonus": 28, "charge": .40, "stamina": 10, "range": 40, "arc": .42, "cooldown": .18, "color": "#a7f0d2", "rarity": "uncommon"},
    "thunder_fists": {"name": "Кастеты Громовержца", "kind": "melee", "damage": 27, "bonus": 32, "charge": .38, "stamina": 9, "range": 36, "arc": .44, "cooldown": .15, "color": "#8be4ff", "rarity": "rare", "element": "lightning"},
    "runic_claymore": {"name": "Рунный двуручник Титана", "kind": "melee", "damage": 45, "bonus": 56, "charge": .86, "stamina": 22, "range": 56, "arc": .15, "cooldown": .48, "color": "#f3b96d", "rarity": "epic"},
    "frost_spear": {"name": "Пика Вечной Мерзлоты", "kind": "melee", "damage": 38, "bonus": 46, "charge": .64, "stamina": 17, "range": 68, "arc": .22, "cooldown": .33, "color": "#94eaff", "rarity": "epic", "element": "ice"},
    "katana": {"name": "Клинок Багрового Рассвета", "kind": "melee", "damage": 40, "bonus": 48, "charge": .52, "stamina": 14, "range": 54, "arc": .26, "cooldown": .23, "color": "#ff6f87", "rarity": "epic"},
    "blood_reaper": {"name": "Коса Кровавой Жатвы", "kind": "melee", "damage": 50, "bonus": 62, "charge": .78, "stamina": 21, "range": 66, "arc": .12, "cooldown": .39, "color": "#e94e67", "rarity": "legendary", "vampirism": .04},
    "solar_halberd": {"name": "Глефа Солнечного Зенита", "kind": "melee", "damage": 58, "bonus": 72, "charge": .80, "stamina": 23, "range": 76, "arc": .12, "cooldown": .42, "color": "#ffe07d", "rarity": "legendary", "element": "fire"},
    "eclipse_katana": {"name": "Клинок Полного Затмения", "kind": "melee", "damage": 54, "bonus": 68, "charge": .50, "stamina": 15, "range": 58, "arc": .22, "cooldown": .21, "color": "#d39bff", "rarity": "legendary", "vampirism": .03},
    "hunter_crossbow": {"name": "Арбалет зверолова", "kind": "bow", "damage": 21, "bonus": 34, "charge": .72, "stamina": 11, "cooldown": .22, "color": "#c9a679", "rarity": "uncommon"},
    "storm_bow": {"name": "Лук Грозового Шторма", "kind": "bow", "damage": 30, "bonus": 48, "charge": .74, "stamina": 12, "cooldown": .15, "color": "#7ce2ff", "rarity": "epic", "element": "lightning"},
    "shadow_repeater": {"name": "Сумрачный самострел", "kind": "bow", "damage": 32, "bonus": 50, "charge": .64, "stamina": 11, "cooldown": .13, "color": "#ba8dff", "rarity": "epic"},
    "dragonbone_bow": {"name": "Лук из кости Дракона", "kind": "bow", "damage": 38, "bonus": 64, "charge": .82, "stamina": 14, "cooldown": .16, "color": "#ff9e86", "rarity": "legendary"},
    "zenith_bow": {"name": "Лук Звёздного Горизонта", "kind": "bow", "damage": 42, "bonus": 72, "charge": .72, "stamina": 13, "cooldown": .12, "color": "#fff199", "rarity": "legendary"},
    "crystal_wand": {"name": "Жезл эхо-кристалла", "kind": "staff", "damage": 20, "bonus": 22, "charge": .52, "stamina": 9, "range": 44, "arc": .24, "cooldown": .26, "color": "#8fece8", "rarity": "uncommon", "spell_power": .15},
    "storm_scepter": {"name": "Скипетр Буревестника", "kind": "staff", "damage": 32, "bonus": 38, "charge": .62, "stamina": 12, "range": 47, "arc": .24, "cooldown": .30, "color": "#7be3ff", "rarity": "epic", "spell_power": .31},
    "blood_tome": {"name": "Фолиант Алой Луны", "kind": "staff", "damage": 35, "bonus": 40, "charge": .58, "stamina": 12, "range": 46, "arc": .24, "cooldown": .28, "color": "#ff7a95", "rarity": "epic", "spell_power": .33, "vampirism": .03},
    "frost_crown_staff": {"name": "Посох Короны Льдов", "kind": "staff", "damage": 39, "bonus": 46, "charge": .65, "stamina": 13, "range": 48, "arc": .22, "cooldown": .31, "color": "#a8f3ff", "rarity": "legendary", "spell_power": .39},
    "cosmos_staff": {"name": "Посох Ткача Созвездий", "kind": "staff", "damage": 48, "bonus": 58, "charge": .62, "stamina": 14, "range": 50, "arc": .22, "cooldown": .28, "color": "#f4c8ff", "rarity": "legendary", "spell_power": .50},
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
    "twinblades": "Два изогнутых клинка поют в унисон с лесным ветром.",
    "thunder_fists": "Каждый удар высекает дугу живой молнии.",
    "runic_claymore": "Древние руны тяжелеют в момент замаха, проламывая любую стойкость.",
    "frost_spear": "Острие выковано из вечного льда северных шпилей.",
    "katana": "Тончайшая сталь разрубает воздух прежде, чем слышен звон.",
    "blood_reaper": "Лезвие пьёт жизненную силу поверженных врагов.",
    "solar_halberd": "Сияющее древко несёт пламя первого рассвета.",
    "eclipse_katana": "Клинок, выкованный на границе света и пустоты.",
    "hunter_crossbow": "Тугая стальная дуга бьёт без промаха.",
    "storm_bow": "Тетива натянута из грозового разряда.",
    "shadow_repeater": "Выпускает болты один за другим из самой тени.",
    "dragonbone_bow": "Плечи из кости Дракона Эха требуют исполинской силы.",
    "zenith_bow": "Стрелы этого лука летят быстрее падающих созвездий.",
    "crystal_wand": "Фокусирует чистые импульсы эхо-кристалла.",
    "storm_scepter": "Наконечник скипетра притягивает бурю с небес.",
    "blood_tome": "Страницы переплетены багровыми нитями древних чар.",
    "frost_crown_staff": "Венчает владельца властью над вечной зимой.",
    "cosmos_staff": "В навершии вращается живая спираль далёких галактик.",
}

GEAR = {
    "traveler": {"name": "Куртка путника", "defense": 2, "color": "#547c50", "rarity": "common", "lore": "Простая одежда для долгой дороги."},
    "wolf_cloak": {"name": "Плащ туманного волка", "defense": 5, "color": "#778d8d", "rarity": "uncommon", "lore": "Шерсть гасит звук шагов.", "bonuses": {"stamina_flat": 15, "move_speed_pct": 0.04}},
    "moss_guard": {"name": "Живой моховой панцирь", "defense": 6, "color": "#8bb56b", "rarity": "uncommon", "lore": "Мох впитывает часть удара.", "bonuses": {"hp_flat": 25, "hp_regen": 0.8}},
    "marsh_armor": {"name": "Болотная броня", "defense": 8, "color": "#9c815e", "rarity": "rare", "lore": "Креплёная кожа и пластины из топкой руды.", "bonuses": {"hp_flat": 30}},
    "moonweave": {"name": "Мантия лунного ткача", "defense": 9, "color": "#9bc8bd", "rarity": "epic", "lore": "Нити мерцают в сумерках затонувших топей.", "bonuses": {"mana_flat": 45, "spell_power_pct": 0.12}},
    "ash_plate": {"name": "Пепельный панцирь", "defense": 12, "color": "#a8aaa4", "rarity": "epic", "lore": "Тяжёлые пластины стражей руин.", "bonuses": {"hp_flat": 45, "damage_pct": 0.05}},
    "colossus_core": {"name": "Сердце Колосса", "defense": 18, "color": "#f49a60", "rarity": "legendary", "lore": "Остывшая броня всё ещё хранит жар древнего титана.", "bonuses": {"hp_flat": 85, "stagger_pct": 0.15}},
    "glacier_mantle": {"name": "Мантия Синего Пламени", "defense": 21, "color": "#8ee8f2", "rarity": "legendary", "lore": "Ледяные пластины звенят, будто далёкие колокола.", "bonuses": {"mana_flat": 70, "spell_power_pct": 0.16}},
    "rift_plate": {"name": "Доспех Пустого Эха", "defense": 27, "color": "#bd85ed", "rarity": "legendary", "lore": "Собран из осколков, переживших разлом между мирами.", "bonuses": {"hp_flat": 90, "damage_pct": 0.08}},
    "obsidian_shell": {"name": "Панцирь чёрного стекла", "defense": 30, "color": "#887090", "rarity": "legendary", "lore": "Осколки обсидиана глушат удары и мерцают в сумраке.", "bonuses": {"hp_flat": 110, "thorns_pct": 0.20}},
    "starseer_robe": {"name": "Мантия звёздочёта", "defense": 32, "color": "#d2a4d7", "rarity": "legendary", "lore": "Ткань хранит холодный свет далёких созвездий.", "bonuses": {"mana_flat": 110, "spell_power_pct": 0.22, "cdr_pct": 0.06}},
    "elder_mantle": {"name": "Плащ Первозданного сада", "defense": 36, "color": "#8ec884", "rarity": "legendary", "lore": "Живые корни вплетают в ткань силу древнего леса.", "bonuses": {"hp_flat": 120, "mana_flat": 65, "hp_regen": 2.5}},
    "leather_vest": {"name": "Кожаный жилет охотника", "defense": 4, "color": "#a5825f", "rarity": "common", "lore": "Прочная кожа, выдубленная корой дуба.", "bonuses": {"stamina_flat": 10}},
    "chain_shirt": {"name": "Кольчуга лесной стражи", "defense": 7, "color": "#9aa7ad", "rarity": "uncommon", "lore": "Мелкие кольца сплетены руками болотного кузнеца.", "bonuses": {"hp_flat": 20}},
    "bark_plate": {"name": "Кора-панцирь друида", "defense": 10, "color": "#7c8f56", "rarity": "rare", "lore": "Живая кора нарастает поверх старых ран.", "bonuses": {"hp_flat": 35, "mana_flat": 20}},
    "ember_mail": {"name": "Доспех тлеющих углей", "defense": 14, "color": "#c96f4a", "rarity": "epic", "lore": "Пластины греются, будто память о пожаре руин.", "bonuses": {"hp_flat": 50, "damage_pct": 0.06}},
    "frostguard_plate": {"name": "Панцирь морозной стражи", "defense": 16, "color": "#a8dced", "rarity": "epic", "lore": "Иней на заклёпках не тает даже у костра.", "bonuses": {"hp_flat": 65, "damage_reduction_pct": 0.04}},
    "void_cloak": {"name": "Плащ из ткани разлома", "defense": 24, "color": "#8f6fd1", "rarity": "legendary", "lore": "Край плаща исчезает в щели между мирами.", "bonuses": {"crit_pct": 0.05, "move_speed_pct": 0.06, "cdr_pct": 0.05}},
    # Расширенные архетипы брони (лёгкая, средняя, тяжёлая, магическая, мифическая)
    "scout_tunic": {"name": "Туника лесного разведчика", "defense": 4, "color": "#6e9960", "rarity": "uncommon", "lore": "Лёгкая ткань не сковывает рывок.", "bonuses": {"stamina_flat": 22, "move_speed_pct": 0.05, "crit_pct": 0.02}},
    "acolyte_robe": {"name": "Ряса послушника чар", "defense": 3, "color": "#5f79b0", "rarity": "uncommon", "lore": "Вышитые руны удерживают искры эфира.", "bonuses": {"mana_flat": 30, "spell_power_pct": 0.08, "mana_regen": 1.2}},
    "iron_cuirass": {"name": "Кираса железного бастиона", "defense": 11, "color": "#8d99a6", "rarity": "rare", "lore": "Кованая грудная пластина держит прямой удар вепря.", "bonuses": {"hp_flat": 45, "damage_reduction_pct": 0.03}},
    "shadow_garb": {"name": "Облачение ночного клинка", "defense": 13, "color": "#5b4f78", "rarity": "epic", "lore": "Сшито из теней, скользящих между клинками.", "bonuses": {"crit_pct": 0.06, "attack_speed_pct": 0.08, "move_speed_pct": 0.06}},
    "runic_vestments": {"name": "Облачение рунного мага", "defense": 12, "color": "#6f86cf", "rarity": "epic", "lore": "Серебряные письмена ускоряют плетение заклинаний.", "bonuses": {"mana_flat": 55, "spell_power_pct": 0.14, "mana_cost_pct": 0.06}},
    "hunter_brigandine": {"name": "Бригантина соколиного глаза", "defense": 15, "color": "#7b9465", "rarity": "epic", "lore": "Пластины на плечах подогнаны под натяжение тугой тетивы.", "bonuses": {"damage_pct": 0.07, "crit_pct": 0.05, "stamina_flat": 30}},
    "crimson_plate": {"name": "Багровый латный доспех", "defense": 22, "color": "#b54854", "rarity": "legendary", "lore": "Закалён в крови древних чудовищ обсидианового края.", "bonuses": {"hp_flat": 95, "damage_pct": 0.09, "vampirism_pct": 0.03}},
    "stormweaver_coat": {"name": "Пальто ткача бурь", "defense": 20, "color": "#5ca9d6", "rarity": "legendary", "lore": "Полы пальто искрят при каждом шаге.", "bonuses": {"mana_flat": 75, "spell_power_pct": 0.18, "cdr_pct": 0.07, "move_speed_pct": 0.05}},
    "phantom_shroud": {"name": "Саван призрачного охотника", "defense": 26, "color": "#7f92b8", "rarity": "legendary", "lore": "Стрелок в этом саване растворяется в звёздной дымке.", "bonuses": {"crit_pct": 0.08, "damage_pct": 0.10, "move_speed_pct": 0.08}},
    "archmage_regalia": {"name": "Регалии Верховного Архонта", "defense": 28, "color": "#a87ce8", "rarity": "legendary", "lore": "Высшее облачение хранителей обсерватории Бездны.", "bonuses": {"mana_flat": 125, "spell_power_pct": 0.25, "cdr_pct": 0.08, "mana_cost_pct": 0.08}},
    "dragonscale_mail": {"name": "Чешуя Дракона Эха", "defense": 33, "color": "#e0677a", "rarity": "legendary", "lore": "Чешуя древнего дракона не поддаётся ни клинку, ни пламени.", "bonuses": {"hp_flat": 130, "damage_pct": 0.10, "damage_reduction_pct": 0.06}},
    "sunforged_aegis": {"name": "Эгида Солнечной Кузни", "defense": 40, "color": "#f2c15e", "rarity": "legendary", "lore": "Сияющий панцирь отражает ярость врагов обратно в них.", "bonuses": {"hp_flat": 165, "damage_reduction_pct": 0.08, "thorns_pct": 0.30, "hp_regen": 3.0}},
    "celestial_raiment": {"name": "Звёздное облачение Вечности", "defense": 38, "color": "#d9b8ff", "rarity": "legendary", "lore": "Соткано из света всех девяти земель.", "bonuses": {"hp_flat": 110, "mana_flat": 110, "damage_pct": 0.12, "spell_power_pct": 0.20, "crit_pct": 0.06, "cdr_pct": 0.08}},
}

# ── Кольца, ожерелья и артефакты (4 слота экипировки: ring, amulet, artifact_1, artifact_2) ──
ACCESSORY_SLOTS = ("ring", "amulet", "artifact_1", "artifact_2")
MAX_ACCESSORY_UPGRADE = 10
ACCESSORIES: dict[str, dict[str, Any]] = {
    # Кольца (slot = "ring")
    "copper_band": {"name": "Медное кольцо путника", "slot": "ring", "rarity": "common", "color": "#d18f62",
                    "description": "+22 здоровья, +2 защиты", "lore": "Простое кольцо с вырезанной тропой у костра.",
                    "bonuses": {"hp_flat": 22, "defense_flat": 2}},
    "emerald_ring": {"name": "Изумрудный перстень ветра", "slot": "ring", "rarity": "uncommon", "color": "#64d98a",
                     "description": "+7% скорости бега, +25 выносливости", "lore": "В гранёном камне кружится лесной вихрь.",
                     "bonuses": {"move_speed_pct": 0.07, "stamina_flat": 25}},
    "sapphire_mana_ring": {"name": "Сапфировое кольцо прилива", "slot": "ring", "rarity": "rare", "color": "#5aa8ff",
                           "description": "+40 маны, +2.5 маны/с", "lore": "Холодный сапфир притягивает рассеянный эфир.",
                           "bonuses": {"mana_flat": 40, "mana_regen": 2.5}},
    "ruby_fang_ring": {"name": "Рубиновый перстень клыка", "slot": "ring", "rarity": "rare", "color": "#f05669",
                       "description": "+8% урона, +3% вампиризма", "lore": "Алый камень теплеет с каждым нанесённым ударом.",
                       "bonuses": {"damage_pct": 0.08, "vampirism_pct": 0.03}},
    "hawk_eye_ring": {"name": "Перстень соколиного взора", "slot": "ring", "rarity": "rare", "color": "#e9cf6b",
                      "description": "+6% шанс крита, +10% крит. урона", "lore": "Помогает заметить брешь в любой броне.",
                      "bonuses": {"crit_pct": 0.06, "crit_mult_bonus": 0.10}},
    "ember_signet": {"name": "Печатка пепельной кузни", "slot": "ring", "rarity": "epic", "color": "#ff8d4f",
                     "description": "+10% урона, +15% ошеломления", "lore": "Носилась мастерами старой наковальни руин.",
                     "bonuses": {"damage_pct": 0.10, "stagger_pct": 0.15}},
    "frost_band": {"name": "Кольцо вечной стужи", "slot": "ring", "rarity": "epic", "color": "#8beeff",
                   "description": "+5 защиты, +13% силы чар, +35 маны", "lore": "Иней на ободке никогда не тает.",
                   "bonuses": {"defense_flat": 5, "spell_power_pct": 0.13, "mana_flat": 35}},
    "void_signet": {"name": "Перстень Пустого Разлома", "slot": "ring", "rarity": "epic", "color": "#b87dff",
                    "description": "+11% ко всему урону, -6% перезарядки", "lore": "Сжимает само время между ударами.",
                    "bonuses": {"damage_pct": 0.11, "spell_power_pct": 0.11, "cdr_pct": 0.06}},
    "obsidian_bastion_ring": {"name": "Обсидиановый перстень бастиона", "slot": "ring", "rarity": "legendary", "color": "#9d83b5",
                              "description": "+10 защиты, +85 здоровья, -5% входящего урона", "lore": "Тёмный обсидиан поглощает инерцию сокрушительных атак.",
                              "bonuses": {"defense_flat": 10, "hp_flat": 85, "damage_reduction_pct": 0.05}},
    "celestial_band": {"name": "Кольцо Девяти Созвездий", "slot": "ring", "rarity": "legendary", "color": "#ffe891",
                       "description": "+14% урона и чар, +7% крита, +55 HP и маны", "lore": "Девять крошечных звёзд вращаются вокруг ободка.",
                       "bonuses": {"damage_pct": 0.14, "spell_power_pct": 0.14, "crit_pct": 0.07, "hp_flat": 55, "mana_flat": 55}},

    # Ожерелья и амулеты (slot = "amulet")
    "wolf_tooth_amulet": {"name": "Ожерелье волчьего клыка", "slot": "amulet", "rarity": "common", "color": "#d8cdb4",
                          "description": "+5% урона, +3% шанс крита", "lore": "Трофей первой удачной охоты в Шепчущем лесу.",
                          "bonuses": {"damage_pct": 0.05, "crit_pct": 0.03}},
    "moon_dew_pendant": {"name": "Кулон лунной росы", "slot": "amulet", "rarity": "uncommon", "color": "#8be6d8",
                         "description": "+35 маны, +2 маны/с, +1.5 HP/с", "lore": "Капля росы внутри стекла светится в темноте.",
                         "bonuses": {"mana_flat": 35, "mana_regen": 2.0, "hp_regen": 1.5}},
    "bog_amber_torc": {"name": "Янтарная гривна топей", "slot": "amulet", "rarity": "rare", "color": "#e6a949",
                       "description": "+50 здоровья, +5 защиты", "lore": "Древний янтарь затвердел тысячу лет назад.",
                       "bonuses": {"hp_flat": 50, "defense_flat": 5}},
    "cross_necklace": {"name": "Звёздный оберег стража", "slot": "amulet", "rarity": "rare", "color": "#f0d88b",
                       "description": "+6 защиты, +55 HP, -6% входящего урона", "lore": "Хранит владельца в самой гуще схватки.",
                       "bonuses": {"defense_flat": 6, "hp_flat": 55, "damage_reduction_pct": 0.06}},
    "pyre_talisman": {"name": "Ожерелье живого пламени", "slot": "amulet", "rarity": "epic", "color": "#ff7847",
                      "description": "+12% урона и силы чар, +12% урона реакций", "lore": "Сердцевина амулета пылает неугасимым жаром.",
                      "bonuses": {"damage_pct": 0.12, "spell_power_pct": 0.12, "reaction_pct": 0.12}},
    "glacier_heart_amulet": {"name": "Амулет Сердца Ледника", "slot": "amulet", "rarity": "epic", "color": "#7ce4ff",
                             "description": "+70 маны, -8% расхода маны, +15% силы чар", "lore": "Осколок сердца Хребта Синего Пламени.",
                             "bonuses": {"mana_flat": 70, "mana_cost_pct": 0.08, "spell_power_pct": 0.15}},
    "dragon_fang_necklace": {"name": "Ожерелье Драконьего Эха", "slot": "amulet", "rarity": "legendary", "color": "#ff6984",
                             "description": "+15% урона, +6% крита, +18% ошеломления", "lore": "Клык Дракона Разлома вибрирует перед каждым критом.",
                             "bonuses": {"damage_pct": 0.15, "crit_pct": 0.06, "stagger_pct": 0.18}},
    "astral_compass_amulet": {"name": "Астральный медальон пустоты", "slot": "amulet", "rarity": "legendary", "color": "#8ac6ff",
                              "description": "-10% перезарядки, +9% скорости бега и атаки", "lore": "Стрелка медальона указывает сквозь само время.",
                              "bonuses": {"cdr_pct": 0.10, "move_speed_pct": 0.09, "attack_speed_pct": 0.09}},
    "reaper_choker": {"name": "Ошейник Жнеца Душ", "slot": "amulet", "rarity": "legendary", "color": "#d45679",
                      "description": "+5% вампиризма, +16% крит. урона, +8% урона", "lore": "Тёмный металл обращает боль врагов в твою силу.",
                      "bonuses": {"vampirism_pct": 0.05, "crit_mult_bonus": 0.16, "damage_pct": 0.08}},
    "eden_seed_amulet": {"name": "Ожерелье Первозданного Семени", "slot": "amulet", "rarity": "legendary", "color": "#a8eb86",
                         "description": "+115 HP, +85 маны, +15% ко всему урону, +3.5 HP/с", "lore": "Семя первого дерева мира бьётся, словно живое сердце.",
                         "bonuses": {"hp_flat": 115, "mana_flat": 85, "damage_pct": 0.15, "spell_power_pct": 0.15, "hp_regen": 3.5}},

    # Артефакты в духе Террарии (slot = "artifact", экипируются в Артефакт I или Артефакт II)
    "hermes_boots": {"name": "Сапоги Стремительного Ветра", "slot": "artifact", "rarity": "rare", "color": "#7ce8a0",
                     "description": "+16% скорости бега, -18% расхода выносливости", "lore": "Крылатые пряжки несут владельца быстрее лесного ветра.",
                     "bonuses": {"move_speed_pct": 0.16, "stamina_cost_pct": 0.18, "stamina_flat": 25}},
    "feral_claws_art": {"name": "Перчатка Яростного Боя", "slot": "artifact", "rarity": "rare", "color": "#e39b5f",
                        "description": "+14% скорости атаки оружием, +9% урона", "lore": "Ускоряет каждый замах, выпад и натяжение тетивы.",
                        "bonuses": {"attack_speed_pct": 0.14, "damage_pct": 0.09}},
    "mana_flower": {"name": "Цветок Эфирного Истока", "slot": "artifact", "rarity": "epic", "color": "#6eb5ff",
                    "description": "-12% расхода маны, +15% силы чар, +3 маны/с", "lore": "Редкий цветок, распускающийся только в потоках чистой магии.",
                    "bonuses": {"mana_cost_pct": 0.12, "spell_power_pct": 0.15, "mana_regen": 3.0}},
    "magic_quiver": {"name": "Призрачный Колчан Эха", "slot": "artifact", "rarity": "epic", "color": "#b4e884",
                     "description": "+15% урона луков, 30% шанс не потратить стрелу", "lore": "Тетива сама находит призрачную стрелу между выстрелами.",
                     "bonuses": {"bow_pct": 0.15, "ammo_save_pct": 0.30, "crit_pct": 0.04}},
    "blood_chalice": {"name": "Алый Грааль Жизни", "slot": "artifact", "rarity": "epic", "color": "#eb4c64",
                      "description": "+5% вампиризма от любого урона, +70 здоровья", "lore": "Кубок наполняется алой росой в разгар битвы.",
                      "bonuses": {"vampirism_pct": 0.05, "hp_flat": 70}},
    "storm_mirror": {"name": "Зеркало Грозового Ответа", "slot": "artifact", "rarity": "epic", "color": "#7ceaff",
                     "description": "+8 защиты, отражает 40% контактного урона во врагов", "lore": "Гладкая амальгама отвечает молнией каждому нападающему.",
                     "bonuses": {"defense_flat": 8, "thorns_pct": 0.40}},
    "greedy_coin": {"name": "Золотой Компас Удачи", "slot": "artifact", "rarity": "rare", "color": "#ffd559",
                    "description": "+30% золота, +16% опыта, +10% шанс редкой добычи", "lore": "Притягивает блеск монет и редкие осколки из поверженных врагов.",
                    "bonuses": {"gold_pct": 0.30, "xp_pct": 0.16, "luck_pct": 0.10}},
    "titan_gauntlet": {"name": "Рукавица Огненного Титана", "slot": "artifact", "rarity": "legendary", "color": "#ff9248",
                       "description": "+15% урона, +28% урона по стойкости, +12% радиуса удара", "lore": "Выкована из осколка ядра Пепельного Колосса.",
                       "bonuses": {"damage_pct": 0.15, "stagger_pct": 0.28, "reach_pct": 0.12}},
    "chrono_hourglass": {"name": "Песочные Часы Вечности", "slot": "artifact", "rarity": "legendary", "color": "#9ad8ff",
                         "description": "-14% перезарядки навыков и чар, +7% шанс крита", "lore": "Звёздный песок внутри течёт вспять.",
                         "bonuses": {"cdr_pct": 0.14, "crit_pct": 0.07}},
    "prism_core": {"name": "Призма Стихийного Резонанса", "slot": "artifact", "rarity": "legendary", "color": "#e89cff",
                   "description": "+25% к урону стихийных реакций, +18% силы чар", "lore": "Преломляет огонь, лёд и молнию в разрушительный спектр.",
                   "bonuses": {"reaction_pct": 0.25, "spell_power_pct": 0.18}},
    "shadow_cloak_art": {"name": "Плащ Теневого Шага", "slot": "artifact", "rarity": "legendary", "color": "#9d7dfa",
                         "description": "+10% шанс крита, +10% скорости бега, шире окно идеального уклона", "lore": "Позволяет шагнуть сквозь сам удар противника.",
                         "bonuses": {"crit_pct": 0.10, "move_speed_pct": 0.10, "dodge_window_bonus": 0.20}},
    "ankh_shield": {"name": "Реликвия Несокрушимого Эха", "slot": "artifact", "rarity": "legendary", "color": "#f5cf76",
                    "description": "+15 защиты, +110 HP, -50% длительности оглушения и горения", "lore": "Древний щит-талисман, перед которым отступает любое проклятие.",
                    "bonuses": {"defense_flat": 15, "hp_flat": 110, "cc_resist_pct": 0.50, "damage_reduction_pct": 0.07}},
}

# ── Система перековки (Terraria-style Reforge Prefixes) ───────────────────────
REFORGE_PREFIXES: dict[str, dict[str, Any]] = {
    # Оружейные модификаторы (от неудачных до Легендарного / Нереального / Мифического)
    "broken": {"name": "Сломанный", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": -1, "weight": 6,
               "summary": "-16% урона, -8% скорости атаки", "bonuses": {"damage_pct": -0.16, "attack_speed_pct": -0.08}},
    "dull": {"name": "Тупой", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": -1, "weight": 7,
             "summary": "-11% урона", "bonuses": {"damage_pct": -0.11}},
    "sluggish": {"name": "Медлительный", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": -1, "weight": 6,
                 "summary": "-12% скорости атаки", "bonuses": {"attack_speed_pct": -0.12}},
    "keen": {"name": "Острый", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": 1, "weight": 12,
             "summary": "+4% шанс крита", "bonuses": {"crit_pct": 0.04}},
    "nimble": {"name": "Проворный", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": 1, "weight": 12,
               "summary": "+9% скорости атаки", "bonuses": {"attack_speed_pct": 0.09}},
    "forceful": {"name": "Весомый", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": 1, "weight": 12,
                 "summary": "+7% урона, +12% ошеломления", "bonuses": {"damage_pct": 0.07, "stagger_pct": 0.12}},
    "adept": {"name": "Искусный", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": 1, "weight": 10,
              "summary": "-10% расхода выносливости и маны", "bonuses": {"stamina_cost_pct": 0.10, "mana_cost_pct": 0.10}},
    "deadly": {"name": "Смертоносный", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": 2, "weight": 10,
               "summary": "+10% урона, +6% скорости атаки, +3% крита", "bonuses": {"damage_pct": 0.10, "attack_speed_pct": 0.06, "crit_pct": 0.03}},
    "savage": {"name": "Свирепый", "group": "weapon", "allowed": ("melee",), "tier": 2, "weight": 10,
               "summary": "+11% урона, +12% радиуса удара, +4% крита", "bonuses": {"damage_pct": 0.11, "reach_pct": 0.12, "crit_pct": 0.04}},
    "rapid": {"name": "Скоростной", "group": "weapon", "allowed": ("bow", "melee"), "tier": 2, "weight": 10,
              "summary": "+14% скорости атаки, -8% расхода выносливости", "bonuses": {"attack_speed_pct": 0.14, "stamina_cost_pct": 0.08}},
    "mystic": {"name": "Мистический", "group": "weapon", "allowed": ("staff",), "tier": 2, "weight": 11,
               "summary": "+12% силы чар, -12% расхода маны", "bonuses": {"spell_power_pct": 0.12, "mana_cost_pct": 0.12}},
    "ruthless": {"name": "Безжалостный", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": 3, "weight": 8,
                 "summary": "+19% урона, -5% скорости атаки", "bonuses": {"damage_pct": 0.19, "spell_power_pct": 0.14, "attack_speed_pct": -0.05}},
    "demonic": {"name": "Демонический", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": 3, "weight": 8,
                "summary": "+14% урона, +6% шанс крита", "bonuses": {"damage_pct": 0.14, "spell_power_pct": 0.12, "crit_pct": 0.06}},
    "godly": {"name": "Божественный", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": 3, "weight": 7,
              "summary": "+15% урона, +6% шанс крита, +14% ошеломления", "bonuses": {"damage_pct": 0.15, "spell_power_pct": 0.13, "crit_pct": 0.06, "stagger_pct": 0.14}},
    "masterful": {"name": "Мастерский", "group": "weapon", "allowed": ("staff", "bow", "melee"), "tier": 3, "weight": 7,
                  "summary": "+13% урона и чар, +9% скорости, -10% расхода", "bonuses": {"damage_pct": 0.13, "spell_power_pct": 0.13, "attack_speed_pct": 0.09, "mana_cost_pct": 0.10, "stamina_cost_pct": 0.10}},
    "legendary": {"name": "Легендарный", "group": "weapon", "allowed": ("melee",), "tier": 4, "weight": 5,
                  "summary": "+18% урона, +12% скорости, +7% крита, +15% радиуса, +18% ошеломления",
                  "bonuses": {"damage_pct": 0.18, "attack_speed_pct": 0.12, "crit_pct": 0.07, "reach_pct": 0.15, "stagger_pct": 0.18}},
    "unreal": {"name": "Нереальный", "group": "weapon", "allowed": ("bow",), "tier": 4, "weight": 5,
               "summary": "+18% урона, +14% скорости выстрела, +7% крита, -12% расхода вын.",
               "bonuses": {"damage_pct": 0.18, "bow_pct": 0.06, "attack_speed_pct": 0.14, "crit_pct": 0.07, "stamina_cost_pct": 0.12}},
    "mythical": {"name": "Мифический", "group": "weapon", "allowed": ("staff",), "tier": 4, "weight": 5,
                 "summary": "+18% силы чар и урона, +11% скорости, +7% крита, -15% расхода маны",
                 "bonuses": {"damage_pct": 0.18, "spell_power_pct": 0.18, "attack_speed_pct": 0.11, "crit_pct": 0.07, "mana_cost_pct": 0.15}},
    "celestial_reforge": {"name": "Звёздный", "group": "weapon", "allowed": ("melee", "bow", "staff"), "tier": 4, "weight": 4,
                          "summary": "+16% урона и чар, +10% скорости, +8% крита",
                          "bonuses": {"damage_pct": 0.16, "spell_power_pct": 0.16, "attack_speed_pct": 0.10, "crit_pct": 0.08}},

    # Модификаторы колец, ожерелий и артефактов (в духе Террарии: Охранный, Грозный, Счастливый, Стремительный...)
    "cracked": {"name": "Треснувший", "group": "accessory", "tier": -1, "weight": 6,
                "summary": "-2 защиты", "bonuses": {"defense_flat": -2}},
    "worn": {"name": "Тусклый", "group": "accessory", "tier": -1, "weight": 6,
             "summary": "-3% урона", "bonuses": {"damage_pct": -0.03}},
    "hard": {"name": "Твёрдый", "group": "accessory", "tier": 1, "weight": 12,
             "summary": "+2 защиты, +12 здоровья", "bonuses": {"defense_flat": 2, "hp_flat": 12}},
    "jagged": {"name": "Зазубренный", "group": "accessory", "tier": 1, "weight": 12,
               "summary": "+3% урона", "bonuses": {"damage_pct": 0.03, "spell_power_pct": 0.03}},
    "precise": {"name": "Точный", "group": "accessory", "tier": 1, "weight": 11,
                "summary": "+3% шанс крита", "bonuses": {"crit_pct": 0.03}},
    "brisk": {"name": "Резвый", "group": "accessory", "tier": 2, "weight": 10,
              "summary": "+4% скорости бега и атаки", "bonuses": {"move_speed_pct": 0.04, "attack_speed_pct": 0.04}},
    "armored": {"name": "Бронированный", "group": "accessory", "tier": 2, "weight": 10,
                "summary": "+4 защиты, +22 здоровья", "bonuses": {"defense_flat": 4, "hp_flat": 22}},
    "spiked": {"name": "Шипастый", "group": "accessory", "tier": 2, "weight": 10,
               "summary": "+4% урона, +2% крита", "bonuses": {"damage_pct": 0.04, "spell_power_pct": 0.04, "crit_pct": 0.02}},
    "arcane_acc": {"name": "Чародейский", "group": "accessory", "tier": 3, "weight": 8,
                   "summary": "+30 маны, +6% силы чар, -5% расхода маны", "bonuses": {"mana_flat": 30, "spell_power_pct": 0.06, "mana_cost_pct": 0.05}},
    "warding": {"name": "Охранный", "group": "accessory", "tier": 4, "weight": 6,
                "summary": "+6 защиты, +38 здоровья", "bonuses": {"defense_flat": 6, "hp_flat": 38}},
    "menacing": {"name": "Грозный", "group": "accessory", "tier": 4, "weight": 6,
                 "summary": "+6% ко всему урону и силе чар", "bonuses": {"damage_pct": 0.06, "spell_power_pct": 0.06}},
    "lucky": {"name": "Счастливый", "group": "accessory", "tier": 4, "weight": 6,
              "summary": "+5% шанс крита, +8% золота", "bonuses": {"crit_pct": 0.05, "gold_pct": 0.08}},
    "quick": {"name": "Стремительный", "group": "accessory", "tier": 4, "weight": 6,
              "summary": "+7% скорости бега, +6% скорости атаки", "bonuses": {"move_speed_pct": 0.07, "attack_speed_pct": 0.06}},
    "primal": {"name": "Первозданный", "group": "accessory", "tier": 4, "weight": 4,
               "summary": "+5% урона и чар, +4 защиты, +4% крита, +25 HP",
               "bonuses": {"damage_pct": 0.05, "spell_power_pct": 0.05, "defense_flat": 4, "crit_pct": 0.04, "hp_flat": 25}},

    # Модификаторы брони
    "worn_armor": {"name": "Потёртый", "group": "gear", "tier": -1, "weight": 7,
                   "summary": "-3 защиты", "bonuses": {"defense_flat": -3}},
    "sturdy": {"name": "Прочный", "group": "gear", "tier": 1, "weight": 13,
               "summary": "+3 защиты, +20 здоровья", "bonuses": {"defense_flat": 3, "hp_flat": 20}},
    "plated": {"name": "Кованый", "group": "gear", "tier": 2, "weight": 11,
               "summary": "+5 защиты, +35 здоровья", "bonuses": {"defense_flat": 5, "hp_flat": 35}},
    "winged": {"name": "Крылатый", "group": "gear", "tier": 3, "weight": 8,
               "summary": "+4 защиты, +6% скорости бега, +25 выносливости", "bonuses": {"defense_flat": 4, "move_speed_pct": 0.06, "stamina_flat": 25}},
    "runic_ward": {"name": "Рунический", "group": "gear", "tier": 3, "weight": 8,
                   "summary": "+4 защиты, +45 маны, +8% силы чар", "bonuses": {"defense_flat": 4, "mana_flat": 45, "spell_power_pct": 0.08}},
    "impenetrable": {"name": "Непробиваемый", "group": "gear", "tier": 4, "weight": 6,
                     "summary": "+8 защиты, +65 здоровья, -4% входящего урона", "bonuses": {"defense_flat": 8, "hp_flat": 65, "damage_reduction_pct": 0.04}},
    "sovereign": {"name": "Владычный", "group": "gear", "tier": 4, "weight": 4,
                  "summary": "+6 защиты, +50 HP, +6% ко всему урону, +4% крита",
                  "bonuses": {"defense_flat": 6, "hp_flat": 50, "damage_pct": 0.06, "spell_power_pct": 0.06, "crit_pct": 0.04}},
}

# ── Конструктор кастомного оружия (Ковка собственного оружия) ────────────────
CUSTOM_WEAPON_ARCHETYPES: dict[str, dict[str, Any]] = {
    "sword": {"label": "Клинок", "kind": "melee", "damage": 28, "bonus": 34, "charge": .58, "stamina": 14, "range": 50, "arc": .26, "cooldown": .28},
    "greatsword": {"label": "Двуручник / Молот", "kind": "melee", "damage": 42, "bonus": 54, "charge": .84, "stamina": 22, "range": 58, "arc": .14, "cooldown": .46},
    "daggers": {"label": "Парные клинки", "kind": "melee", "damage": 21, "bonus": 26, "charge": .38, "stamina": 10, "range": 38, "arc": .40, "cooldown": .17},
    "spear": {"label": "Копьё / Глефа", "kind": "melee", "damage": 33, "bonus": 42, "charge": .66, "stamina": 16, "range": 68, "arc": .18, "cooldown": .34},
    "bow": {"label": "Лук / Арбалет", "kind": "bow", "damage": 26, "bonus": 44, "charge": .76, "stamina": 12, "range": 520, "arc": .28, "cooldown": .16},
    "staff": {"label": "Магический посох", "kind": "staff", "damage": 28, "bonus": 34, "charge": .62, "stamina": 12, "range": 48, "arc": .24, "cooldown": .30, "spell_power": .26},
}
CUSTOM_WEAPON_CORES: dict[str, dict[str, Any]] = {
    "physical": {"label": "Закалённая сталь", "color": "#e0e8ea", "element": "", "desc": "+12% базового урона", "dmg_mult": 1.12},
    "fire": {"label": "Ядро Пламени", "color": "#ff7d4d", "element": "fire", "desc": "Поджигает цели при попадании", "dmg_mult": 1.05},
    "ice": {"label": "Сердце Стужи", "color": "#7be8ff", "element": "ice", "desc": "Замедляет врагов морозным следом", "dmg_mult": 1.04},
    "lightning": {"label": "Искра Грома", "color": "#ffe869", "element": "lightning", "desc": "+8% скорости атаки и грозовой разряд", "dmg_mult": 1.04, "speed_mult": 0.92},
    "shadow": {"label": "Кровавая Тень", "color": "#df5e88", "element": "shadow", "desc": "Похищает 4% здоровья от урона", "dmg_mult": 1.03, "vampirism": 0.04},
    "astral": {"label": "Звёздный Эфир", "color": "#c996ff", "element": "arcane", "desc": "+6% шанс крита и усиление чар", "dmg_mult": 1.06, "crit_bonus": 0.06, "spell_bonus": 0.08},
}
CUSTOM_WEAPON_TIERS: dict[int, dict[str, Any]] = {
    1: {"label": "Кованый (Редкий)", "rarity": "rare", "scale": 1.0,
        "cost": {"gold": 280, "ore": 8, "wood": 6, "crystal": 3}},
    2: {"label": "Мифриловый (Эпический)", "rarity": "epic", "scale": 1.32,
        "cost": {"gold": 680, "ore": 12, "mithril": 4, "crystal": 6, "essence": 3}},
    3: {"label": "Первозданный (Легендарный)", "rarity": "legendary", "scale": 1.68,
        "cost": {"gold": 1550, "mithril": 10, "crystal": 12, "shard": 8, "essence": 6, "rune_dust": 4}},
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
    "blueflame_siren": {"name": "Певица Синего Пламени", "hp": 880, "speed": 35, "damage": 41, "range": 94, "cooldown": 2.25, "xp": 960, "color": "#72e8ff", "zone": 4, "size": 48, "anim": "cast", "mini_boss": True},
    "rift_knight": {"name": "Рыцарь разлома", "hp": 760, "speed": 45, "damage": 52, "range": 82, "cooldown": 1.9, "xp": 580, "color": "#bd85ed", "zone": 5, "size": 32, "anim": "lunge"},
    "echo_dragon": {"name": "Дракон Пустого Эха", "hp": 2600, "speed": 31, "damage": 74, "range": 126, "cooldown": 2.45, "xp": 2400, "color": "#ff637e", "zone": 5, "size": 50, "anim": "fly", "boss": True},
    "void_wraith": {"name": "Призрак Бездны", "hp": 1400, "speed": 48, "damage": 55, "range": 85, "cooldown": 1.4, "xp": 1100, "color": "#7b2cbf", "zone": 6, "size": 28, "anim": "phase"},
    "astral_titan": {"name": "Титан Астральной Бездны", "hp": 4800, "speed": 36, "damage": 95, "range": 140, "cooldown": 2.2, "xp": 4500, "color": "#00f0ff", "zone": 6, "size": 58, "anim": "quake", "boss": True},
    "obsidian_sentinel": {"name": "Страж чёрного стекла", "hp": 2100, "speed": 38, "damage": 70, "range": 94, "cooldown": 1.8, "xp": 1850, "color": "#86718f", "zone": 7, "size": 36, "anim": "guard"},
    "glass_inquisitor": {"name": "Инквизитор Чёрного Зеркала", "hp": 2400, "speed": 27, "damage": 75, "range": 112, "cooldown": 2.5, "xp": 2750, "color": "#c67acb", "zone": 7, "size": 46, "anim": "guard", "mini_boss": True},
    "starseer": {"name": "Звёздочёт Пустоты", "hp": 2650, "speed": 49, "damage": 82, "range": 76, "cooldown": 1.55, "xp": 3100, "color": "#d9a6ef", "zone": 8, "size": 30, "anim": "cast"},
    "ancient_warden": {"name": "Хранитель Первозданного сада", "hp": 7200, "speed": 29, "damage": 108, "range": 148, "cooldown": 2.05, "xp": 7200, "color": "#91cb79", "zone": 8, "size": 56, "anim": "quake", "boss": True},
    "bramble_warden": {"name": "Корневой Страж", "hp": 360, "speed": 31, "damage": 18, "range": 72, "cooldown": 2.15, "xp": 210, "color": "#9fce66", "zone": 1, "size": 36, "anim": "quake", "mini_boss": True},
    "fen_matron": {"name": "Матрона Топей", "hp": 610, "speed": 38, "damage": 27, "range": 82, "cooldown": 2.0, "xp": 440, "color": "#74d2c0", "zone": 4, "size": 40, "anim": "float", "mini_boss": True},
    "ashbound_herald": {"name": "Пепельный Вестник", "hp": 690, "speed": 36, "damage": 34, "range": 92, "cooldown": 1.9, "xp": 780, "color": "#f0a071", "zone": 7, "size": 42, "anim": "guard", "mini_boss": True},
}


BESTIARY_CATALOG = build_catalog(MONSTERS, POPULATION, REGIONS)


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
    "forest_bow": {"name": "Лук следопыта", "description": "Надёжный лук для первой охоты", "price": 260, "kind": "weapon"},
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
    # Новые алхимические настои и ремесленные наборы
    "rage_potion": {"name": "Эликсир ярости берсерка", "description": "+18% урона и +8% крита на 45с", "price": 75, "kind": "rage_potion"},
    "ironskin_potion": {"name": "Отвар каменной кожи", "description": "+10 защиты и -12% входящего урона на 60с", "price": 70, "kind": "ironskin_potion"},
    "haste_potion": {"name": "Настой стремительного ветра", "description": "+16% скорости бега и +12% скорости атаки на 50с", "price": 68, "kind": "haste_potion"},
    "arcane_tonic": {"name": "Звёздный тоник чародея", "description": "+22% силы чар и +5 маны/с на 45с", "price": 85, "kind": "arcane_tonic"},
    "rune_dust_pack": {"name": "Мешочек рунной пыли ×3", "description": "Катализатор для перековки и закалки", "price": 65, "kind": "rune_dust"},
    "essence_pack": {"name": "Сосуд стихийной эссенции ×2", "description": "Для ковки артефактов и ядер оружия", "price": 78, "kind": "essence"},
    "mithril_pack": {"name": "Слитки мифрила ×2", "description": "Благородный металл для высшей ковки", "price": 110, "kind": "mithril"},
    # Новые виды оружия в лавках
    "twinblades": {"name": "Парные серпы ветра", "description": "Сверхбыстрые двойные клинки", "price": 295, "kind": "weapon"},
    "thunder_fists": {"name": "Кастеты Громовержца", "description": "Кулачное оружие с дугой молнии", "price": 520, "kind": "weapon"},
    "runic_claymore": {"name": "Рунный двуручник Титана", "description": "Сокрушительный двуручный меч", "price": 890, "kind": "weapon"},
    "frost_spear": {"name": "Пика Вечной Мерзлоты", "description": "Дальнобойная морозная пика", "price": 940, "kind": "weapon"},
    "katana": {"name": "Клинок Багрового Рассвета", "description": "Молниеносный клинок мастера", "price": 1120, "kind": "weapon"},
    "blood_reaper": {"name": "Коса Кровавой Жатвы", "description": "Легендарная коса с вампиризмом", "price": 1980, "kind": "weapon"},
    "solar_halberd": {"name": "Глефа Солнечного Зенита", "description": "Мифическая огненная глефа", "price": 2550, "kind": "weapon"},
    "eclipse_katana": {"name": "Клинок Полного Затмения", "description": "Мифическая катана пустоты", "price": 2480, "kind": "weapon"},
    "hunter_crossbow": {"name": "Арбалет зверолова", "description": "Пробивной охотничий арбалет", "price": 310, "kind": "weapon"},
    "storm_bow": {"name": "Лук Грозового Шторма", "description": "Грозовой лук быстрой стрельбы", "price": 1150, "kind": "weapon"},
    "shadow_repeater": {"name": "Сумрачный самострел", "description": "Скорострельный арбалет Бездны", "price": 1380, "kind": "weapon"},
    "dragonbone_bow": {"name": "Лук из кости Дракона", "description": "Тяжёлый легендарный лук", "price": 1920, "kind": "weapon"},
    "zenith_bow": {"name": "Лук Звёздного Горизонта", "description": "Мифический лук Первозданного сада", "price": 2620, "kind": "weapon"},
    "crystal_wand": {"name": "Жезл эхо-кристалла", "description": "Быстрый жезл начинающего мага", "price": 215, "kind": "weapon"},
    "storm_scepter": {"name": "Скипетр Буревестника", "description": "Эпический скипетр штормовых чар", "price": 1180, "kind": "weapon"},
    "blood_tome": {"name": "Фолиант Алой Луны", "description": "Гримуар с похищением жизни", "price": 1420, "kind": "weapon"},
    "frost_crown_staff": {"name": "Посох Короны Льдов", "description": "Легендарный посох вечной зимы", "price": 1850, "kind": "weapon"},
    "cosmos_staff": {"name": "Посох Ткача Созвездий", "description": "Мифический посох созвездий (+50% чар)", "price": 2680, "kind": "weapon"},
    # Новые доспехи в лавках
    "scout_tunic": {"name": "Туника лесного разведчика", "description": "Броня · защита 4 · +скорость и крит", "price": 130, "kind": "gear"},
    "acolyte_robe": {"name": "Ряса послушника чар", "description": "Броня · защита 3 · +мана и сила чар", "price": 135, "kind": "gear"},
    "iron_cuirass": {"name": "Кираса железного бастиона", "description": "Броня · защита 11 · +45 HP", "price": 410, "kind": "gear"},
    "shadow_garb": {"name": "Облачение ночного клинка", "description": "Броня · защита 13 · +крит и скорость атаки", "price": 880, "kind": "gear"},
    "runic_vestments": {"name": "Облачение рунного мага", "description": "Броня · защита 12 · +55 маны и +14% чар", "price": 740, "kind": "gear"},
    "hunter_brigandine": {"name": "Бригантина соколиного глаза", "description": "Броня · защита 15 · +урон и крит", "price": 860, "kind": "gear"},
    "crimson_plate": {"name": "Багровый латный доспех", "description": "Броня · защита 22 · +95 HP и вампиризм", "price": 1680, "kind": "gear"},
    "stormweaver_coat": {"name": "Пальто ткача бурь", "description": "Броня · защита 20 · +18% чар и -7% КД", "price": 1290, "kind": "gear"},
    "phantom_shroud": {"name": "Саван призрачного охотника", "description": "Броня · защита 26 · +8% крита и +10% урона", "price": 1620, "kind": "gear"},
    "archmage_regalia": {"name": "Регалии Верховного Архонта", "description": "Броня · защита 28 · +25% силы чар", "price": 1790, "kind": "gear"},
    "dragonscale_mail": {"name": "Чешуя Дракона Эха", "description": "Броня · защита 33 · +130 HP и +10% урона", "price": 2150, "kind": "gear"},
    "sunforged_aegis": {"name": "Эгида Солнечной Кузни", "description": "Броня · защита 40 · +165 HP и шипы", "price": 2650, "kind": "gear"},
    "celestial_raiment": {"name": "Звёздное облачение Вечности", "description": "Броня · защита 38 · мифический баланс", "price": 2720, "kind": "gear"},
    # Кольца, ожерелья и артефакты в лавках
    **{
        acc_id: {
            "name": acc["name"],
            "description": acc["description"],
            "price": {"common": 140, "uncommon": 260, "rare": 480, "epic": 890, "legendary": 1650}.get(acc["rarity"], 320),
            "kind": "accessory",
        }
        for acc_id, acc in ACCESSORIES.items()
    },
}
SELL_PRICES = {
    "wood": 3, "herb": 4, "ore": 6, "hide": 8, "slime": 5, "crystal": 10, "shard": 14,
    "essence": 18, "rune_dust": 16, "mithril": 26,
    "potion": 12, "arrows": 1, "mana_potion": 16, "stamina_potion": 14, "elixir": 45,
    "throwing_knife": 4, "bandage": 5,
    "rage_potion": 28, "ironskin_potion": 26, "haste_potion": 25, "arcane_tonic": 32,
}
CONSUMABLES = {
    "mana_potion": {"name": "Эссенция синего пламени", "description": "+60 маны", "price": 45, "restore_mana": 60},
    "stamina_potion": {"name": "Отвар живучести", "description": "+55 выносливости", "price": 38, "restore_stamina": 55},
    "elixir": {"name": "Эликсир первозданной росы", "description": "+90 здоровья, +60 маны, +40 выносливости", "price": 120,
                "restore_hp": 90, "restore_mana": 60, "restore_stamina": 40},
    "bandage": {"name": "Лубяная повязка", "description": "+24 здоровья мгновенно", "price": 14, "restore_hp": 24},
    "rage_potion": {"name": "Эликсир ярости берсерка", "description": "+18% урона и +8% крита на 45с", "price": 75,
                    "buff_field": "rage_until", "buff_duration": 45.0, "restore_stamina": 20},
    "ironskin_potion": {"name": "Отвар каменной кожи", "description": "+10 защиты и -12% урона на 60с", "price": 70,
                        "buff_field": "ironskin_until", "buff_duration": 60.0, "restore_hp": 25},
    "haste_potion": {"name": "Настой стремительного ветра", "description": "+16% скорости бега и +12% скорости атаки на 50с", "price": 68,
                     "buff_field": "haste_until", "buff_duration": 50.0, "restore_stamina": 35},
    "arcane_tonic": {"name": "Звёздный тоник чародея", "description": "+22% силы чар и +5 маны/с на 45с", "price": 85,
                     "buff_field": "arcane_tonic_until", "buff_duration": 45.0, "restore_mana": 45},
}
CONSUMABLE_ALIASES: dict[str, dict[str, Any]] = {
    "potion": {"name": "Настойка следопыта", "description": "+48 здоровья", "restore_hp": 48},
    **CONSUMABLES,
}


def consumable_use(p: dict[str, Any], item_id: str) -> tuple[bool, str, dict[str, Any]]:
    """Apply one consumable, returning (used, message, effects).

    Every potion sold or brewed in the game has a working use path; the call is
    rejected with a clear message instead of silently doing nothing.
    """
    spec = CONSUMABLE_ALIASES.get(item_id)
    if not spec:
        return False, "Этот предмет нельзя использовать.", {}
    if int(p.get("inventory", {}).get(item_id, 0)) <= 0:
        return False, f"В сумке нет: {spec['name']}.", {}
    effects: dict[str, Any] = {}
    if "buff_field" in spec:
        now = time.monotonic()
        dur = float(spec.get("buff_duration", 45.0))
        p[spec["buff_field"]] = now + dur
        effects["buff"] = round(dur, 1)
    if "restore_hp" in spec:
        before = float(p["hp"])
        p["hp"] = min(p["max_hp"], p["hp"] + float(spec["restore_hp"]))
        effects["hp"] = round(p["hp"] - before, 1)
    if "restore_mana" in spec:
        before = float(p.get("mana", 0))
        p["mana"] = min(float(p.get("max_mana", 0)), p.get("mana", 0) + float(spec["restore_mana"]))
        effects["mana"] = round(p["mana"] - before, 1)
    if "restore_stamina" in spec:
        before = float(p["stamina"])
        p["stamina"] = min(p["max_stamina"], p["stamina"] + float(spec["restore_stamina"]))
        effects["stamina"] = round(p["stamina"] - before, 1)
    if not any(isinstance(v, (int, float)) and v > 0 for v in effects.values()):
        return False, f"{spec['name']}: восстанавливать нечего — характеристики полны.", {}
    p["inventory"][item_id] = max(0, int(p["inventory"].get(item_id, 0)) - 1)
    effects["id"] = item_id
    effects["name"] = spec["name"]
    return True, f"Использовано: {spec['name']}.", effects


CRAFT_RECIPES = {
    "arrows": {"name": "Колчан стрел ×8", "cost": {"wood": 2, "ore": 1}, "category": "supplies"},
    "potion": {"name": "Настойка следопыта", "cost": {"herb": 3, "slime": 1}, "category": "supplies"},
    "mana_potion": {"name": "Эссенция синего пламени", "cost": {"crystal": 2, "herb": 2}, "category": "supplies"},
    "stamina_potion": {"name": "Отвар живучести", "cost": {"hide": 2, "ore": 1}, "category": "supplies"},
    "elixir": {"name": "Эликсир первозданной росы", "cost": {"crystal": 4, "shard": 2, "herb": 4}, "category": "supplies"},
    "rage_potion": {"name": "Эликсир ярости берсерка", "cost": {"herb": 3, "essence": 1, "shard": 1}, "category": "supplies"},
    "ironskin_potion": {"name": "Отвар каменной кожи", "cost": {"ore": 3, "herb": 2, "slime": 1}, "category": "supplies"},
    "haste_potion": {"name": "Настой стремительного ветра", "cost": {"herb": 3, "essence": 1}, "category": "supplies"},
    "arcane_tonic": {"name": "Звёздный тоник чародея", "cost": {"crystal": 2, "essence": 1, "rune_dust": 1}, "category": "supplies"},
    "bandage": {"name": "Стопка повязок ×3", "cost": {"herb": 2}, "category": "supplies"},
    "throwing_knife": {"name": "Метательные ножи ×5", "cost": {"ore": 2, "wood": 1}, "category": "supplies"},
    # Оружие в кузне
    "iron_sword": {"name": "Клинок из болотной стали", "cost": {"ore": 6, "wood": 4}, "category": "weapon"},
    "mace": {"name": "Булава болотного света", "cost": {"ore": 4, "wood": 3, "hide": 1}, "category": "weapon"},
    "twinblades": {"name": "Парные серпы ветра", "cost": {"ore": 5, "wood": 3, "hide": 2}, "category": "weapon"},
    "hunter_crossbow": {"name": "Арбалет зверолова", "cost": {"wood": 6, "ore": 4, "hide": 2}, "category": "weapon"},
    "crystal_wand": {"name": "Жезл эхо-кристалла", "cost": {"wood": 4, "crystal": 3}, "category": "weapon"},
    "warhammer": {"name": "Молот сокрушитель", "cost": {"ore": 9, "wood": 4, "hide": 2}, "category": "weapon"},
    "longbow": {"name": "Длинный лук Эха", "cost": {"wood": 8, "hide": 3, "crystal": 1}, "category": "weapon"},
    "ember_staff": {"name": "Посох тлеющего угля", "cost": {"wood": 6, "crystal": 3, "shard": 1}, "category": "weapon"},
    "runic_claymore": {"name": "Рунный двуручник Титана", "cost": {"ore": 10, "mithril": 3, "rune_dust": 2}, "category": "weapon"},
    "katana": {"name": "Клинок Багрового Рассвета", "cost": {"mithril": 4, "shard": 3, "essence": 2}, "category": "weapon"},
    "storm_bow": {"name": "Лук Грозового Шторма", "cost": {"wood": 8, "mithril": 3, "essence": 3}, "category": "weapon"},
    "storm_scepter": {"name": "Скипетр Буревестника", "cost": {"crystal": 6, "mithril": 3, "essence": 3}, "category": "weapon"},
    # Доспехи в кузне
    "leather_vest": {"name": "Кожаный жилет охотника", "cost": {"hide": 5, "wood": 1}, "category": "gear"},
    "scout_tunic": {"name": "Туника лесного разведчика", "cost": {"hide": 4, "herb": 3}, "category": "gear"},
    "acolyte_robe": {"name": "Ряса послушника чар", "cost": {"herb": 4, "crystal": 2}, "category": "gear"},
    "chain_shirt": {"name": "Кольчуга лесной стражи", "cost": {"ore": 7, "hide": 2}, "category": "gear"},
    "armor": {"name": "Болотная броня", "cost": {"hide": 4, "ore": 3}, "category": "gear"},
    "iron_cuirass": {"name": "Кираса железного бастиона", "cost": {"ore": 9, "hide": 3}, "category": "gear"},
    "bark_plate": {"name": "Кора-панцирь друида", "cost": {"wood": 8, "herb": 4, "ore": 3}, "category": "gear"},
    "shadow_garb": {"name": "Облачение ночного клинка", "cost": {"hide": 6, "shard": 3, "essence": 2}, "category": "gear"},
    "runic_vestments": {"name": "Облачение рунного мага", "cost": {"crystal": 5, "rune_dust": 3, "essence": 2}, "category": "gear"},
    "crimson_plate": {"name": "Багровый латный доспех", "cost": {"mithril": 6, "shard": 5, "essence": 3}, "category": "gear"},
    # Ювелирное дело и ковка артефактов
    "copper_band": {"name": "Медное кольцо путника", "cost": {"ore": 4, "wood": 2}, "category": "accessory"},
    "wolf_tooth_amulet": {"name": "Ожерелье волчьего клыка", "cost": {"hide": 3, "ore": 2}, "category": "accessory"},
    "sapphire_mana_ring": {"name": "Сапфировое кольцо прилива", "cost": {"ore": 4, "crystal": 4}, "category": "accessory"},
    "hawk_eye_ring": {"name": "Перстень соколиного взора", "cost": {"ore": 5, "crystal": 3, "hide": 2}, "category": "accessory"},
    "cross_necklace": {"name": "Звёздный оберег стража", "cost": {"ore": 6, "crystal": 4, "shard": 2}, "category": "accessory"},
    "ember_signet": {"name": "Печатка пепельной кузни", "cost": {"ore": 8, "shard": 4, "rune_dust": 2}, "category": "accessory"},
    "hermes_boots": {"name": "Сапоги Стремительного Ветра", "cost": {"hide": 6, "essence": 2, "crystal": 3}, "category": "accessory"},
    "greedy_coin": {"name": "Золотой Компас Удачи", "cost": {"ore": 6, "crystal": 4, "rune_dust": 2}, "category": "accessory"},
    "blood_chalice": {"name": "Алый Грааль Жизни", "cost": {"mithril": 4, "essence": 4, "shard": 3}, "category": "accessory"},
    "titan_gauntlet": {"name": "Рукавица Огненного Титана", "cost": {"mithril": 6, "shard": 6, "essence": 4}, "category": "accessory"},
    "prism_core": {"name": "Призма Стихийного Резонанса", "cost": {"crystal": 8, "essence": 5, "rune_dust": 4}, "category": "accessory"},
    "ankh_shield": {"name": "Реликвия Несокрушимого Эха", "cost": {"mithril": 8, "shard": 8, "rune_dust": 5, "crystal": 6}, "category": "accessory"},
}
ENCHANT_CATALOG = {
    "sharpness": {"name": "Острота", "target": "weapon", "description": "+8 урона за уровень"},
    "vampirism": {"name": "Похищение жизни", "target": "weapon", "description": "Лечит на 6% урона за уровень"},
    "celerity": {"name": "Стремительность", "target": "weapon", "description": "+4% скорости атаки и +2% крита за уровень"},
    "protection": {"name": "Защита", "target": "gear", "description": "+2 к защите за уровень"},
    "vital_ward": {"name": "Живучесть бастиона", "target": "gear", "description": "+18 здоровья за уровень"},
}
ENCHANT_MAX_LEVEL = 5
PLAYER_MAX_LEVEL = 100
ABILITY_MAX_LEVEL = 10
SPELL_MAX_LEVEL = 12
MAIN_BOSS_KIND = "ancient_warden"


def all_weapons(p: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    if not p or not p.get("custom_weapons"):
        return WEAPONS
    return {**WEAPONS, **p["custom_weapons"]}


def weapon_spec_for(p: dict[str, Any] | None, weapon_id: str) -> dict[str, Any]:
    if p and weapon_id in p.get("custom_weapons", {}):
        return p["custom_weapons"][weapon_id]
    return WEAPONS.get(weapon_id, WEAPONS["sword"])


def gear_sell_price(item_id: str) -> int:
    return {"common": 18, "uncommon": 34, "rare": 58, "epic": 92, "legendary": 150}.get(GEAR.get(item_id, {}).get("rarity", "common"), 18)


def weapon_sell_price(item_id: str, p: dict[str, Any] | None = None) -> int:
    spec = (p.get("custom_weapons", {}).get(item_id) if p else None) or WEAPONS.get(item_id, {})
    return {"common": 22, "uncommon": 36, "rare": 64, "epic": 105, "legendary": 165}.get(spec.get("rarity", "common"), 22)


def accessory_sell_price(item_id: str) -> int:
    return {"common": 24, "uncommon": 42, "rare": 74, "epic": 125, "legendary": 210}.get(ACCESSORIES.get(item_id, {}).get("rarity", "common"), 24)

app = FastAPI(title="Лес Эхо: Пробуждение")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
players: dict[str, dict[str, Any]] = {}
clients: dict[str, WebSocket] = {}
snapshot_profiles_sent: set[str] = set()
# Heartbeat bookkeeping for the idle watchdog (see close_stale_clients).
last_seen_at: dict[str, float] = {}
last_ping_at: dict[str, float] = {}
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
    # Станящие заклинания: урон меньше, зато обездвиживают и монстров, и других игроков.
    "frost_ring": {"name": "Кольцо стужи", "kind": "Лёд", "rarity": 3, "mana": 34, "cooldown": 9.5, "damage": 34, "radius": 150, "stun_duration": 2.0, "slow_duration": 3.0, "slow_factor": .45, "unlock_spent": 420, "unlock_level": 7},
    "root_bind": {"name": "Оковы корней", "kind": "Терни", "rarity": 3, "mana": 30, "cooldown": 10.0, "damage": 26, "radius": 138, "stun_duration": 2.6, "slow_duration": 3.5, "slow_factor": .35, "unlock_spent": 300, "unlock_level": 6},
    "mind_chill": {"name": "Леденящий разум", "kind": "Тень", "rarity": 4, "mana": 42, "cooldown": 11.0, "damage": 58, "radius": 78, "stun_duration": 2.2, "slow_duration": 2.5, "slow_factor": .5, "unlock_spent": 620, "unlock_level": 9},
    "echo_lattice": {"name": "Сеть эха", "kind": "Эхо", "rarity": 4, "mana": 42, "cooldown": 9.0,
                     "damage": 54, "radius": 172, "chain": True, "jumps": 4, "falloff": .76,
                     "stun_duration": .85, "slow_duration": 1.4, "slow_factor": .68,
                     "unlock_spent": 0, "unlock_level": 7, "unlock_story_stage": 3},
}

CLASS_MIN_LEVEL = 5
MASTERY_MAX_LEVEL = 20
MASTERY_TREES = ("warrior", "ranger", "mage")
MASTERY_NAMES = {"warrior": "Воин", "ranger": "Следопыт", "mage": "Маг"}
TREE_WEAPON_KIND = {"warrior": "melee", "ranger": "bow", "mage": "staff"}
WEAPON_TREE = {"melee": "warrior", "bow": "ranger", "staff": "mage"}
CLASS_PERKS: dict[str, list[dict[str, Any]]] = {
    "warrior": [
        {"level": 5, "id": "tempered_steel", "name": "Закалённая сталь", "desc": "+10% физ. урона и +6 к броне"},
        {"level": 10, "id": "blood_rush", "name": "Кровавый натиск", "desc": "Удары в комбо лечат на 4% от нанесённого урона"},
        {"level": 15, "id": "bastion", "name": "Несокрушимый бастион", "desc": "Идеальный уворот даёт +18 брони на 4 с"},
        {"level": 20, "id": "war_avatar", "name": "Аватар Войны", "desc": "Финал комбо рассекает всех врагов вокруг (+25% урона по площади)"},
    ],
    "ranger": [
        {"level": 5, "id": "eagle_eye", "name": "Орлиный взор", "desc": "+8% шанса крита и +12% скорости стрел"},
        {"level": 10, "id": "thrill_hunt", "name": "Охотничий азарт", "desc": "Попадание по замедленной или помеченной цели возвращает 6 выносливости"},
        {"level": 15, "id": "phantom_step", "name": "Призрачный шаг", "desc": "Идеальный уворот гарантирует критический следующий выстрел"},
        {"level": 20, "id": "wind_lord", "name": "Владыка Ветров", "desc": "Заряженный выстрел выпускает призрачную стрелу (45% урона)"},
    ],
    "mage": [
        {"level": 5, "id": "aether_flow", "name": "Поток эфира", "desc": "+12% силы магии и +25 к макс. мане"},
        {"level": 10, "id": "elemental_resonance", "name": "Элементальный резонанс", "desc": "Смена стихии даёт +18% урона чар и возвращает 6 маны"},
        {"level": 15, "id": "mind_ward", "name": "Щит разума", "desc": "Применение заклинаний даёт чародейский барьер (+8 брони на 4 с)"},
        {"level": 20, "id": "archmage", "name": "Архимаг Вечности", "desc": "+25% критического урона чар и -0,5 с перезарядки умений при касте"},
    ],
}
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
        "description": "Держит дистанцию и бьёт чарами: способности тратят ману, а прежние заклинания и созданные чары остаются в отдельной панели.",
        "stat_bonus": {"vitality": 1, "magic_damage": 1, "mana_regen": 1},
        "abilities": ["arcane_bolt", "frost_lance", "flame_burst", "chain_lightning",
                      "blink", "arcane_shield", "mana_surge", "meteor_fall"],
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
                   "desc": "Первые 0,22 с парирует удар монстра: без урона, с оглушением и контратакой. Затем +14 брони на 5 секунд."},
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
    # ── Маг: чары в общем наборе способностей. Стоят ману, а не выносливость. ──
    "arcane_bolt": {"tree": "mage", "name": "Чародейская стрела", "icon": "✦", "mastery": 1,
                    "resource": "mana", "cost": 10, "cooldown": 4.5, "range": 720.0, "mult": 1.05,
                    "element": "arcane", "spell_kind": "Аркана", "key": "KeyR",
                    "desc": "Быстрый сгусток арканы летит в точку прицела и бьёт первого, кого встретит."},
    "frost_lance": {"tree": "mage", "name": "Ледяное копьё", "icon": "❄", "mastery": 2,
                    "resource": "mana", "cost": 14, "cooldown": 7.0, "range": 740.0, "mult": 1.0,
                    "element": "ice", "spell_kind": "Лёд", "slow_duration": 3.5, "slow_factor": .45,
                    "key": "KeyT",
                    "desc": "Копьё льда замедляет цель до 45% скорости на 3,5 секунды."},
    "flame_burst": {"tree": "mage", "name": "Пламенный всплеск", "icon": "🔥", "mastery": 2,
                    "resource": "mana", "cost": 18, "cooldown": 9.0, "range": 460.0, "radius": 118.0,
                    "mult": .9, "spell_kind": "Огонь", "burn_duration": 4.0, "burn_tick": .8,
                    "burn_mult": .14, "key": "KeyP",
                    "desc": "Вспышка пламени в точке прицела: задевает всех рядом и поджигает на 4 секунды."},
    "chain_lightning": {"tree": "mage", "name": "Цепная молния", "icon": "⚡", "mastery": 3,
                        "resource": "mana", "cost": 20, "cooldown": 9.5, "range": 480.0, "radius": 155.0,
                        "jumps": 3, "falloff": .78, "mult": .8, "spell_kind": "Молния", "key": "KeyX",
                        "desc": "Молния перескакивает по трём ближайшим врагам; каждый следующий получает меньше."},
    "blink": {"tree": "mage", "name": "Мерцание", "icon": "✧", "mastery": 3,
              "resource": "mana", "cost": 12, "cooldown": 8.0, "distance": 190.0, "key": "KeyO",
              "desc": "Мгновенный шаг сквозь пространство на 190 единиц в сторону прицела."},
    "arcane_shield": {"tree": "mage", "name": "Чародейский щит", "icon": "🛡", "mastery": 4,
                      "resource": "mana", "cost": 16, "cooldown": 16.0, "duration": 6.0, "armor": 12,
                      "key": "KeyN",
                      "desc": "На 6 секунд окутывает щитом: +12 брони и меньше входящего урона."},
    "mana_surge": {"tree": "mage", "name": "Прилив маны", "icon": "✶", "mastery": 4,
                   "resource": "mana", "cost": 0, "cooldown": 18.0, "restore": 28, "key": "KeyK",
                   "desc": "Вытягивает силу из посоха: возвращает 28 маны. Сам прилив маны не тратит."},
    "meteor_fall": {"tree": "mage", "name": "Падение метеора", "icon": "☄", "mastery": 5,
                    "resource": "mana", "cost": 30, "cooldown": 16.0, "range": 520.0, "radius": 132.0,
                    "mult": 1.45, "spell_kind": "Звёзды", "burn_duration": 3.0, "burn_tick": .75,
                    "burn_mult": .12, "key": "KeyL",
                    "desc": "С неба падает метеор: тяжёлый урон по области и короткое горение."},
}
for _ability_id, _ability_spec in ABILITY_CATALOG.items():
    _ability_spec["id"] = _ability_id

# Воин наносит удары на полтора раза дальше обычного ближнего боя.
CLASS_MELEE_REACH = {"warrior": 1.5}


def melee_reach_factor(p: dict[str, Any]) -> float:
    return CLASS_MELEE_REACH.get(str(p.get("class") or ""), 1.5) * (1.0 + equipment_bonuses(p)["reach_pct"])

MANA_GROWTH_COEF, MANA_GROWTH_CAP = 1.25, 180
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
REGION_SHOPS = build_shops(SHOP_CATALOG)



def safe_name(value: Any) -> str:
    return " ".join(str(value).strip().split())[:18] or "Путник"


def zone_for_x(x: float, region: str = "camp") -> dict[str, Any]:
    """Compatibility helper: regions are maps, not horizontal coordinate bands."""
    return REGIONS.get(region, REGIONS["camp"])


# --- Combat status effects -------------------------------------------------
# The very same slow/stun/poison/burn fields are kept on monsters and on
# players, so any ability or spell that hinders a monster can hinder a player.
PLAYER_STATUS_FIELDS = ("slow_until", "stun_until", "poison_until", "burn_until")
PVP_DAMAGE_FACTOR = .72          # duel damage is softened compared to PvE
PVP_EFFECT_FACTOR = .6           # control effects on players are shorter
MAX_PVP_STUN = 3.0               # never let a chain-lock last longer than this
MAX_PVP_SLOW = 8.0
STUN_MIN_INTERVAL = .5           # how often a stunned target may be refreshed


def ensure_status(p: dict[str, Any]) -> None:
    """Guarantee every status field exists (older saves lack them)."""
    for field in PLAYER_STATUS_FIELDS:
        p.setdefault(field, 0.0)
    p.setdefault("slow_factor", .45)
    for kind in ("burn", "poison"):
        p.setdefault(f"{kind}_next", 0.0)
        p.setdefault(f"{kind}_owner", "")
        p.setdefault(f"{kind}_source", "")
        p.setdefault(f"{kind}_damage", 0.0)
        p.setdefault(f"{kind}_tick", .8)


def apply_player_control(target: dict[str, Any], now: float, *, slow_duration: float = 0.0,
                         slow_factor: float = .45, stun_duration: float = 0.0, source: str = "") -> None:
    """Slow or stun another player using the same fields the mobs use."""
    ensure_status(target)
    if target.get("respawn_at", 0) > now:
        return
    if slow_duration > 0:
        until = now + min(MAX_PVP_SLOW, max(0.0, float(slow_duration)))
        factor = max(.15, min(.95, float(slow_factor)))
        current = float(target.get("slow_until", 0) or 0)
        # A longer slow always wins; a shorter but stronger one replaces the
        # movement penalty while keeping whatever time is already running.
        if until >= current:
            target["slow_until"] = until
            target["slow_factor"] = factor
        elif factor < float(target.get("slow_factor", 1) or 1):
            target["slow_factor"] = factor
    if stun_duration > 0:
        duration = min(MAX_PVP_STUN, max(0.0, float(stun_duration)))
        current = float(target.get("stun_until", 0) or 0)
        # A fresh hit only refreshes a stun that is about to wear off, so
        # repeated stuns cannot produce an endless lock of the same victim.
        if current <= now + STUN_MIN_INTERVAL:
            target["stun_until"] = now + duration
            target["attack"] = None
            target["gathering"] = None
            broadcast({"type": "notice", "target": target["id"],
                       "text": f"Ты оглушён{' ' + source if source else ''}: {duration:.1f} с."})


def apply_player_damage_over_time(target: dict[str, Any], kind: str, *, now: float,
                                  duration: float, damage: float, tick: float,
                                  owner: str = "", source: str = "") -> bool:
    """Refresh a bounded, single-stack burn or poison effect on a player."""
    if kind not in ("burn", "poison") or target.get("respawn_at", 0) > now:
        return False
    ensure_status(target)
    until_key, next_key = f"{kind}_until", f"{kind}_next"
    damage_key, tick_key = f"{kind}_damage", f"{kind}_tick"
    owner_key, source_key = f"{kind}_owner", f"{kind}_source"
    old_until = float(target.get(until_key, 0) or 0)
    active = old_until > now
    effect_tick = max(.35, min(5.0, float(tick)))
    effect_damage = max(1.0, min(10000.0, float(damage)))
    if not active:
        target[next_key] = now + effect_tick
        target[damage_key] = effect_damage
        target[tick_key] = effect_tick
        target[owner_key] = str(owner or "")
        target[source_key] = str(source or "")
    elif effect_damage >= float(target.get(damage_key, 0) or 0):
        # A stronger refresh replaces the source, but never creates a second tick stream.
        target[damage_key] = effect_damage
        target[owner_key] = str(owner or "")
        target[source_key] = str(source or "")
    target[until_key] = min(max(old_until, now + max(0.0, min(8.0, float(duration)))), now + 8.0)
    return True


def consume_player_damage_over_time(target: dict[str, Any], kind: str, now: float) -> dict[str, Any] | None:
    """Consume one due player DOT pulse and move its deadline forward."""
    if kind not in ("burn", "poison"):
        return None
    ensure_status(target)
    until = float(target.get(f"{kind}_until", 0) or 0)
    if until <= now:
        target[f"{kind}_next"] = 0.0
        return None
    if float(target.get(f"{kind}_next", 0) or 0) > now:
        return None
    tick = max(.35, min(5.0, float(target.get(f"{kind}_tick", .8) or .8)))
    target[f"{kind}_next"] = now + tick
    return {"kind": kind, "damage": max(1, round(float(target.get(f"{kind}_damage", 0) or 0))),
            "owner": str(target.get(f"{kind}_owner", "") or ""),
            "source": str(target.get(f"{kind}_source", "") or "")}


def clear_player_combat_status(target: dict[str, Any]) -> None:
    """Remove temporary combat effects when a character dies or respawns."""
    ensure_status(target)
    for field in PLAYER_STATUS_FIELDS:
        target[field] = 0.0
    target["slow_factor"] = .45
    for kind in ("burn", "poison"):
        target[f"{kind}_next"] = 0.0
        target[f"{kind}_owner"] = ""
        target[f"{kind}_source"] = ""
        target[f"{kind}_damage"] = 0.0
        target[f"{kind}_tick"] = .8


def apply_player_dot_pulse(target: dict[str, Any], pulse: dict[str, Any], now: float) -> dict[str, Any] | None:
    """Apply one already-due DOT pulse and return its network event/death result."""
    if target.get("respawn_at", 0) > now:
        return None
    owner_id = str(pulse.get("owner", "") or "")
    damage = max(1, round(float(pulse.get("damage", 0) or 0)
                          * (PVP_DAMAGE_FACTOR if owner_id else 1.0)))
    target["hp"] = max(0, int(target.get("hp", 0) or 0) - damage)
    target["last_combat"] = now
    owner = players.get(owner_id) if owner_id else None
    if owner and owner is not target:
        owner["last_combat"] = now
        add_damage_score(owner, damage, "pvp_dot", now)
    event = {"type": "hit_player", "region": target.get("region", "camp"),
             "id": target.get("id", ""), "damage": damage,
             "status": pulse.get("kind", ""), "damage_over_time": True,
             "mob": pulse.get("source", ""), "attacker": owner_id,
             "x": round(float(target.get("x", 0) or 0), 1),
             "y": round(float(target.get("y", 0) or 0), 1)}
    killed = target["hp"] <= 0
    if killed:
        target["respawn_at"] = now + 5
        target["attack"] = None; target["gathering"] = None
        clear_player_combat_status(target)
    return {"event": event, "killed": killed}


def apply_monster_attack_rider(target: dict[str, Any], mob: dict[str, Any],
                               attack: dict[str, Any], now: float, *, hit_damage: int) -> bool:
    """Apply only the authored herald rider after its strike actually hits."""
    if target.get("respawn_at", 0) > now:
        return False
    signature = {
        "bramble_warden": "slow",
        "fen_matron": "poison",
        "ashbound_herald": "burn",
        "blueflame_siren": "slow",
        "glass_inquisitor": "poison",
    }
    kind = str(mob.get("kind", ""))
    effect = signature.get(kind)
    if not mob.get("mini_boss") or not effect or attack.get("effect") != effect:
        return False
    if effect == "slow":
        source = "Корневой Страж" if kind == "bramble_warden" else MONSTERS[kind]["name"]
        apply_player_control(target, now, slow_duration=2.4, slow_factor=.58,
                             source=source)
    else:
        apply_player_damage_over_time(target, effect, now=now, duration=2.6,
                                      damage=max(1, round(hit_damage * .06)), tick=.8,
                                      source=MONSTERS[kind]["name"])
    return True


def spell_control(spec: dict[str, Any], target: dict[str, Any], now: float, source: str) -> None:
    """Apply a spell's stun/slow fields to a mob or another player.

    Players receive the same fields the monsters use, but every duration is
    shortened by ``PVP_EFFECT_FACTOR`` so duels stay playable.
    """
    stun = float(spec.get("stun_duration", 0) or 0)
    slow = float(spec.get("slow_duration", 0) or 0)
    factor = float(spec.get("slow_factor", .45) or .45)
    if target.get("boss"):
        stun *= .35
        slow *= .6
    elif target.get("mini_boss"):
        stun *= .62
        slow *= .78
    if "mx" in target:  # players carry movement input, mobs do not
        apply_player_control(target, now,
                             stun_duration=pvp_effect_duration(stun),
                             slow_duration=min(MAX_PVP_SLOW, slow),
                             slow_factor=factor, source=source)
    else:
        if stun > 0:
            target["stun_until"] = max(float(target.get("stun_until", 0) or 0), now + stun)
            target["telegraph_until"] = 0.0
        if slow > 0:
            target["slow_until"] = max(float(target.get("slow_until", 0) or 0), now + slow)
            target["slow_factor"] = factor


def clear_expired_status(p: dict[str, Any], now: float) -> None:
    marks = p.get("eagle_marks")
    if isinstance(marks, dict):
        for mob_id, until in list(marks.items()):
            try:
                value = float(until or 0)
            except (TypeError, ValueError):
                marks.pop(mob_id, None); continue
            if value <= now:
                marks.pop(mob_id, None)


def add_damage_score(p: dict[str, Any], amount: float, kind: str, now: float) -> None:
    """Damage points: credited to the attacker, tracked per source and session."""
    amount = max(0, round(float(amount)))
    if amount <= 0:
        return
    stats = p.setdefault("damage_stats", {})
    stats["total"] = int(stats.get("total", 0)) + amount
    stats[kind] = int(stats.get(kind, 0)) + amount
    stats["last_hit"] = amount
    stats["last_kind"] = kind
    stats["last_at"] = now
    window = stats.setdefault("window", [])
    window.append([now, amount])
    while window and (now - float(window[0][0]) > 30.0 or len(window) > 400):
        window.pop(0)
    stats["recent"] = sum(int(row[1]) for row in window)
    stats["dps"] = round(stats["recent"] / 30.0, 1)
    stats["peak_dps"] = max(float(stats.get("peak_dps", 0) or 0), stats["dps"])
    stats["max_hit"] = max(int(stats.get("max_hit", 0) or 0), amount)
    stats["hits"] = int(stats.get("hits", 0)) + 1


STATUS_INFO = {
    "stun": {"name": "Оглушение", "icon": "✦"},
    "slow": {"name": "Замедление", "icon": "❄"},
    "poison": {"name": "Яд", "icon": "☠"},
    "burn": {"name": "Горение", "icon": "🔥"},
}


def player_status_view(p: dict[str, Any], now: float) -> list[dict[str, Any]]:
    """Live control effects on this player, in the shape the client HUD expects."""
    ensure_status(p)
    out: list[dict[str, Any]] = []
    for key, field in (("burn", "burn_until"), ("poison", "poison_until"),
                       ("slow", "slow_until"), ("stun", "stun_until")):
        try:
            until = float(p.get(field, 0) or 0)
        except (TypeError, ValueError):
            continue
        if until <= now:
            continue
        info = STATUS_INFO[key]
        remaining = round(until - now, 2)
        row: dict[str, Any] = {"kind": key, "name": info["name"], "icon": info["icon"],
                               "remaining": remaining}
        if key == "slow":
            row["factor"] = round(float(p.get("slow_factor", .45) or .45), 2)
        out.append(row)
    return out


def damage_points_view(p: dict[str, Any]) -> dict[str, Any]:
    """Damage points summary sent to the client (total, per source, DPS)."""
    stats = p.get("damage_stats") if isinstance(p.get("damage_stats"), dict) else {}
    total = int(stats.get("total", 0) or 0)
    def bucket(*keys: str) -> int:
        return sum(int(stats.get(key, 0) or 0) for key in keys)
    return {
        "total": total,
        "pve": bucket("mob", "spell", "dot"),
        "pvp": bucket("pvp", "pvp_spell", "pvp_dot"),
        "dps": round(float(stats.get("dps", 0) or 0), 1),
        "peak_dps": round(float(stats.get("peak_dps", 0) or 0), 1),
        "recent": int(stats.get("recent", 0) or 0),
        "max_hit": int(stats.get("max_hit", 0) or 0),
        "hits": int(stats.get("hits", 0) or 0),
        "last_hit": int(stats.get("last_hit", 0) or 0),
        "last_kind": str(stats.get("last_kind", "") or ""),
    }


def pvp_effect_duration(duration: float) -> float:
    """Control effects on players are shortened compared to monsters."""
    return max(0.0, min(MAX_PVP_STUN, float(duration) * PVP_EFFECT_FACTOR))


def scaled_mob(kind: str, level: int, index: int, x: float, y: float) -> dict[str, Any]:
    spec = MONSTERS[kind]
    scale = 1 + max(0, level - spec["zone"]) * .16
    return {"id": f"{kind}-{index}", "kind": kind, "level": level,
            "_kill_rewarded": False, "_contributors": {},
            "x": float(x), "y": float(y), "spawn_x": float(x), "spawn_y": float(y),
            "hp": round(spec["hp"] * scale), "max_hp": round(spec["hp"] * scale),
            "speed": spec["speed"] * (1 + max(0, level - spec["zone"]) * .035),
            "wander_x": random.uniform(-1, 1), "wander_y": random.uniform(-1, 1),
            "wander_at": time.monotonic() + random.uniform(.5, 3), "attack_at": 0.0,
            "respawn_at": 0.0, "telegraph_until": 0.0, "alert_until": 0.0,
            "pending_attack": None, "attack_step": 0, "phase": 1,
            "burn_until": 0.0, "burn_next": 0.0, "burn_owner": "", "burn_damage": 0.0,
            "burn_tick": .75, "slow_until": 0.0, "slow_factor": .45,
            "stun_until": 0.0,
            "poison_until": 0.0, "poison_next": 0.0, "poison_owner": "", "poison_damage": 0.0,
            "poison_tick": .8,
            "bleed_until": 0.0, "bleed_next": 0.0, "bleed_owner": "", "bleed_damage": 0.0,
            "sunder_until": 0.0, "stagger": 0.0, "staggered_until": 0.0,
            "boss": bool(spec.get("boss") or kind == "colossus"),
            "mini_boss": bool(spec.get("mini_boss"))}


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


def equipped_accessories_map(p: dict[str, Any]) -> dict[str, str | None]:
    raw = p.get("equipped_accessories")
    if not isinstance(raw, dict):
        raw = {}
    return {
        "ring": raw.get("ring") if raw.get("ring") in ACCESSORIES else None,
        "amulet": raw.get("amulet") if raw.get("amulet") in ACCESSORIES else None,
        "artifact_1": raw.get("artifact_1") if raw.get("artifact_1") in ACCESSORIES else None,
        "artifact_2": raw.get("artifact_2") if raw.get("artifact_2") in ACCESSORIES else None,
    }


def all_owned_accessories(p: dict[str, Any]) -> list[str]:
    eq = [v for v in equipped_accessories_map(p).values() if v]
    bag = [a for a in (p.get("accessories") or []) if a in ACCESSORIES]
    return list(dict.fromkeys([*eq, *bag]))


def grant_accessory(p: dict[str, Any], acc_id: str) -> bool:
    if acc_id not in ACCESSORIES:
        return False
    if acc_id in all_owned_accessories(p):
        p["gold"] += 28
        inv = p.setdefault("inventory", {})
        inv["crystal"] = inv.get("crystal", 0) + 1
        inv["rune_dust"] = inv.get("rune_dust", 0) + 1
        try:
            broadcast({"type": "notice", "target": p["id"], "text": "Дубликат реликвии разобран: +28 монет, эхо-кристалл и рунная пыль."})
        except RuntimeError:
            pass
        return False
    p.setdefault("accessories", []).append(acc_id)
    try:
        broadcast({"type": "notice", "target": p["id"], "text": f"Найдена реликвия: {ACCESSORIES[acc_id]['name']}!"})
    except RuntimeError:
        pass
    return True


def item_reforge_id(p: dict[str, Any], target: str, item_id: str) -> str:
    ref = p.get("reforges")
    if not isinstance(ref, dict):
        return ""
    pid = str((ref.get(target) or {}).get(item_id) or "")
    return pid if pid in REFORGE_PREFIXES else ""


def item_reforge_spec(p: dict[str, Any], target: str, item_id: str) -> dict[str, Any] | None:
    pid = item_reforge_id(p, target, item_id)
    return REFORGE_PREFIXES.get(pid) if pid else None


def equipment_bonuses(p: dict[str, Any], now: float | None = None) -> dict[str, float]:
    """Aggregate passive bonuses from armor, accessories/artifacts, Terraria reforges, custom weapons, buffs & secondary stats."""
    if now is None:
        now = time.monotonic()
    totals: dict[str, float] = {
        "hp_flat": 0.0, "mana_flat": 0.0, "stamina_flat": 0.0, "defense_flat": 0.0,
        "damage_pct": 0.0, "melee_pct": 0.0, "bow_pct": 0.0, "spell_power_pct": 0.0,
        "crit_pct": 0.0, "crit_mult_bonus": 0.0,
        "attack_speed_pct": 0.0, "move_speed_pct": 0.0,
        "cdr_pct": 0.0, "mana_cost_pct": 0.0, "stamina_cost_pct": 0.0,
        "vampirism_pct": 0.0, "hp_regen": 0.0, "mana_regen": 0.0,
        "gold_pct": 0.0, "xp_pct": 0.0, "luck_pct": 0.0,
        "stagger_pct": 0.0, "reaction_pct": 0.0, "damage_reduction_pct": 0.0,
        "thorns_pct": 0.0, "ammo_save_pct": 0.0, "cc_resist_pct": 0.0,
        "reach_pct": 0.0, "dodge_window_bonus": 0.0,
    }

    def _merge(src: dict[str, Any] | None, scale: float = 1.0) -> None:
        if not src:
            return
        for k, val in src.items():
            if k in totals:
                totals[k] += float(val) * scale

    # 1. Надетый доспех + чары живучести + модификатор перековки брони
    gear_id = str(p.get("gear") or "traveler")
    gear_spec = GEAR.get(gear_id, GEAR["traveler"])
    _merge(gear_spec.get("bonuses"))
    vital_lvl = int((p.get("enchantments", {}).get("gear", {}).get(gear_id, {}) or {}).get("vital_ward", 0))
    if vital_lvl > 0:
        totals["hp_flat"] += 18.0 * vital_lvl
    gear_ref = item_reforge_spec(p, "gear", gear_id)
    if gear_ref:
        _merge(gear_ref.get("bonuses"))

    # 2. Экипированное оружие (включая кастомное) + чары стремительности + модификатор перековки оружия
    wid = str(p.get("weapon") or "sword")
    wspec = weapon_spec_for(p, wid)
    if wspec.get("vampirism"):
        totals["vampirism_pct"] += float(wspec["vampirism"])
    if wspec.get("crit_bonus"):
        totals["crit_pct"] += float(wspec["crit_bonus"])
    cel_lvl = int((p.get("enchantments", {}).get("weapon", {}).get(wid, {}) or {}).get("celerity", 0))
    if cel_lvl > 0:
        totals["attack_speed_pct"] += 0.04 * cel_lvl
        totals["crit_pct"] += 0.02 * cel_lvl
    w_ref = item_reforge_spec(p, "weapon", wid)
    if w_ref:
        _merge(w_ref.get("bonuses"))

    # 3. Кольцо, ожерелье и 2 артефакта (+ закалка аксессуаров до +10 и их модификаторы перековки)
    eq_acc = equipped_accessories_map(p)
    acc_upgrades = (p.get("upgrades") or {}).get("accessory") or {}
    for acc_id in eq_acc.values():
        if not acc_id or acc_id not in ACCESSORIES:
            continue
        aspec = ACCESSORIES[acc_id]
        up_lvl = max(0, min(MAX_ACCESSORY_UPGRADE, int(acc_upgrades.get(acc_id, 0) or 0)))
        _merge(aspec.get("bonuses"), 1.0 + 0.08 * up_lvl)
        a_ref = item_reforge_spec(p, "accessory", acc_id)
        if a_ref:
            _merge(a_ref.get("bonuses"))

    # 4. Вторичные характеристики развития героя: Стойкость (tenacity) и Свирепость (ferocity)
    tenacity = max(0, int(p.get("tenacity_level", 0) or 0))
    if tenacity > 0:
        totals["hp_flat"] += 4.0 * tenacity
        totals["damage_reduction_pct"] += 0.005 * tenacity
        totals["cc_resist_pct"] += 0.01 * tenacity
    ferocity = max(0, int(p.get("ferocity_level", 0) or 0))
    if ferocity > 0:
        totals["damage_pct"] += 0.005 * ferocity
        totals["spell_power_pct"] += 0.005 * ferocity
        totals["crit_mult_bonus"] += 0.015 * ferocity
        totals["stagger_pct"] += 0.01 * ferocity

    # 5. Активные боевые настои
    if float(p.get("rage_until", 0) or 0) > now:
        totals["damage_pct"] += 0.18
        totals["crit_pct"] += 0.08
    if float(p.get("ironskin_until", 0) or 0) > now:
        totals["defense_flat"] += 10.0
        totals["damage_reduction_pct"] += 0.12
    if float(p.get("haste_until", 0) or 0) > now:
        totals["move_speed_pct"] += 0.16
        totals["attack_speed_pct"] += 0.12
    if float(p.get("arcane_tonic_until", 0) or 0) > now:
        totals["spell_power_pct"] += 0.22
        totals["mana_regen"] += 5.0

    # Безопасные границы модификаторов
    totals["cdr_pct"] = min(0.45, max(0.0, totals["cdr_pct"]))
    totals["mana_cost_pct"] = min(0.50, max(0.0, totals["mana_cost_pct"]))
    totals["stamina_cost_pct"] = min(0.50, max(0.0, totals["stamina_cost_pct"]))
    totals["damage_reduction_pct"] = min(0.55, max(0.0, totals["damage_reduction_pct"]))
    totals["attack_speed_pct"] = min(0.65, max(-0.35, totals["attack_speed_pct"]))
    totals["move_speed_pct"] = min(0.55, max(-0.20, totals["move_speed_pct"]))
    return totals


def init_world() -> None:
    global mobs, nodes
    if not mobs:
        mobs, nodes = populate(scaled_mob)


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

def quest_objective(kind: str, key: str, need: int, have: int) -> dict[str, Any]:
    need = max(0, int(need))
    return {"kind": kind, "key": key, "need": need, "have": max(0, min(need, int(have)))}


def quest_reward_view(gold: int, xp: int, items: list[tuple[str, str, int]], points: int = 1) -> dict[str, Any]:
    return {"gold": int(gold), "xp": int(xp), "points": int(points),
            "items": [{"type": kind, "id": item, "count": int(amount)} for kind, item, amount in items]}


def _guide_name(region_id: str) -> str:
    guide = NPCS.get(f"{region_id}-guide") or {}
    return str(guide.get("name") or "Хранитель истории")


def _region_name(region_id: str) -> str:
    return str(REGIONS.get(region_id, {}).get("name") or region_id)


def story_quest_status(p: dict[str, Any], stage: int) -> str:
    """«done», «ready», «active» или «idle» для этапа основной ветки."""
    current = int(p.get("quest_stage", 0))
    if stage < current:
        return "done"
    if stage > current or not p.get("quest_active"):
        return "idle"          # ещё не выдано Хранителем — в журнал не попадает
    return "ready" if quest_complete(p) else "active"


def region_quest_status(p: dict[str, Any], region_id: str) -> str:
    """«done», «ready» (цели и материалы есть), «ongoing» или «idle»."""
    state = (p.get("region_quests") or {}).get(region_id) or {}
    if state.get("done"):
        return "done"
    if not state.get("active"):
        return "idle"
    spec = REGION_QUESTS[region_id]
    counters_ok = (state.get("gather", {}).get(spec["resource"], 0) >= spec["count"] and
                   (not spec.get("resource2") or spec.get("count2", 0) <= 0 or
                    state.get("gather", {}).get(spec["resource2"], 0) >= spec["count2"]) and
                   (not spec.get("mob") or state.get("kills", {}).get(spec["mob"], 0) >= spec["mob_count"]))
    if not counters_ok:
        return "ongoing"
    # Progress is not ownership: completed objectives only pay out while the
    # materials are still in the bag.
    stock_ok = (p.get("inventory", {}).get(spec["resource"], 0) >= spec["count"] and
                (not spec.get("resource2") or spec.get("count2", 0) <= 0 or
                 p.get("inventory", {}).get(spec["resource2"], 0) >= spec["count2"]))
    return "ready" if stock_ok else "short"


def gather_node_kind(p: dict[str, Any]) -> str:
    """Which node the character is working on — the renderer picks the tool by it."""
    job = p.get("gathering") or {}
    if not job:
        return ""
    node_id = job.get("node")
    for node in nodes:
        if node.get("id") == node_id:
            return str(node.get("kind", ""))
    return ""


def quest_journal(p: dict[str, Any]) -> list[dict[str, Any]]:
    """Every accepted (and finished) commission, main line and local side work.

    The client renders this list directly: accepted quests carry their live
    counters, finished ones keep a place in the chain so the journal reads as a
    history instead of a single floating objective.
    """
    journal: list[dict[str, Any]] = []
    stage_now = int(p.get("quest_stage", 0))
    for stage, (mob, mob_n, resource, res_n, title) in enumerate(QUESTS):
        status = story_quest_status(p, stage)
        if status == "idle":
            # A stage the keeper has not handed out yet is not part of the journal.
            continue
        current = stage == stage_now
        objectives = []
        if mob:
            objectives.append(quest_objective("kill", mob, mob_n,
                                              mob_n if not current else p.get("quest_kills", {}).get(mob, 0)))
        if resource:
            objectives.append(quest_objective("gather", resource, res_n,
                                              res_n if not current else p.get("quest_gather", {}).get(resource, 0)))
        gold, xp, rewards = QUEST_REWARDS[stage]
        journal.append({
            "id": f"story:{stage}", "kind": "story", "stage": stage, "total": len(QUESTS),
            "title": title, "status": status, "objectives": objectives,
            "reward": quest_reward_view(gold, xp, rewards),
            "region": "camp", "region_name": _region_name("camp"), "giver": _guide_name("camp"),
            "description": "Основная ветка: каждое поручение Хранителя ведёт дальше по девяти землям.",
        })

    herald = herald_story_view(p)
    for chapter in herald["chapters"]:
        if chapter["status"] == "hidden":
            continue
        objective = quest_objective("kill", chapter["mob"], 1,
                                    1 if chapter["status"] in ("ready", "done") else
                                    int(p.get("herald_story_kills", 0) or 0)
                                    if chapter["stage"] == herald["stage"] else 0)
        gold, xp = chapter["gold"], chapter["xp"]
        journal.append({
            "id": f"herald:{chapter['stage']}", "kind": "herald_story", "stage": chapter["stage"],
            "total": len(HERALD_QUESTS), "title": chapter["title"], "status": chapter["status"],
            "objectives": [objective], "reward": quest_reward_view(gold, xp, []),
            "region": chapter["region"], "region_name": _region_name(chapter["region"]),
            "giver": _guide_name("camp"), "description": chapter["description"],
        })

    for region_id, spec in REGION_QUESTS.items():
        status = region_quest_status(p, region_id)
        if status == "idle":
            continue
        state = (p.get("region_quests") or {}).get(region_id) or {}
        objectives = []
        if spec.get("mob"):
            objectives.append(quest_objective("kill", spec["mob"], spec["mob_count"],
                                              state.get("kills", {}).get(spec["mob"], 0)))
        if spec.get("resource"):
            objectives.append(quest_objective("gather", spec["resource"], spec["count"],
                                              state.get("gather", {}).get(spec["resource"], 0)))
        if spec.get("resource2") and spec.get("count2", 0) > 0:
            objectives.append(quest_objective("gather", spec["resource2"], spec["count2"],
                                              state.get("gather", {}).get(spec["resource2"], 0)))
        journal.append({
            "id": f"region:{region_id}", "kind": "region", "stage": None, "total": None,
            "title": str(spec["title"]), "status": status, "objectives": objectives,
            "reward": quest_reward_view(spec["gold"], spec["xp"], [("potion", "potion", 2)]),
            "region": region_id, "region_name": _region_name(region_id), "giver": _guide_name(region_id),
            "description": str(spec.get("description") or "Местное поручение: засчитывается только в этих землях."),
        })

    order = {"ready": 0, "short": 1, "ongoing": 2, "active": 2, "done": 3}
    main_line = sorted((q for q in journal if q["kind"] == "story"), key=lambda q: q["stage"])
    herald_line = sorted((q for q in journal if q["kind"] == "herald_story"), key=lambda q: q["stage"])
    side = sorted((q for q in journal if q["kind"] == "region"),
                  key=lambda q: (order.get(q["status"], 4), list(REGION_QUESTS).index(q["region"])
                                 if q["region"] in REGION_QUESTS else 99))
    return main_line + herald_line + side


HERALD_QUESTS = (
    {"mob": "bramble_warden", "region": "forest", "title": "Корни, что шепчут",
     "description": "Егор просит найти след Корневого Стража и остановить зов, пробуждающий древние корни.",
     "gold": 180, "xp": 480},
    {"mob": "fen_matron", "region": "marsh", "title": "Песнь под чёрной водой",
     "description": "Печать леса привела к Матроне Топей. Прерви её песнь, пока болото не поглотило тропы.",
     "gold": 420, "xp": 1000},
    {"mob": "ashbound_herald", "region": "ruins", "title": "Пепел помнит имя",
     "description": "Пепельный Вестник хранит третью печать и имя того, кто разбудил Эхо.",
     "gold": 900, "xp": 1800},
)


def herald_story_view(p: dict[str, Any]) -> dict[str, Any]:
    stage = max(0, min(len(HERALD_QUESTS), int(p.get("herald_story_stage", 0) or 0)))
    active = bool(p.get("herald_story_active")) and stage < len(HERALD_QUESTS)
    kills = max(0, int(p.get("herald_story_kills", 0) or 0))
    chapters = []
    for index, spec in enumerate(HERALD_QUESTS):
        if index < stage:
            status = "done"
        elif index > stage or stage >= len(HERALD_QUESTS):
            status = "hidden"
        elif active:
            status = "ready" if kills >= 1 else "active"
        else:
            status = "available"
        chapters.append({"stage": index, **spec, "status": status})
    return {"stage": stage, "total": len(HERALD_QUESTS), "active": active,
            "kills": min(1, kills), "complete": stage >= len(HERALD_QUESTS), "chapters": chapters}


def default_tracked_quest(p: dict[str, Any], journal: list[dict[str, Any]]) -> str:
    """The journal's pick when the player has not pinned anything (or it finished)."""
    if not journal:
        return ""
    pinned = str(p.get("tracked_quest") or "")
    if pinned and any(q["id"] == pinned for q in journal):
        return pinned
    for wanted in ("ready", "short"):
        for quest in journal:
            if quest["status"] == wanted:
                return quest["id"]
    for quest in journal:
        if quest["status"] in ("ongoing", "active"):
            return quest["id"]
    return ""


def has_free_world_travel(p: dict[str, Any]) -> bool:
    """Defeating the Primeval Garden's Ancient Warden unlocks free travel across all worlds."""
    if bool(p.get("world_travel_unlocked")):
        return True
    defeated = p.get("bosses_defeated") or []
    return MAIN_BOSS_KIND in defeated


def xp_for_next_level(level: int) -> int:
    lvl = max(1, int(level))
    if lvl >= PLAYER_MAX_LEVEL:
        return 0
    return lvl * 120


def combat_state_view(p: dict[str, Any], now: float) -> dict[str, Any]:
    combo_active = float(p.get("combo_until", 0) or 0) > now
    streak_active = float(p.get("streak_until", 0) or 0) > now
    counter_rem = max(0.0, round(float(p.get("counter_until", 0) or 0) - now, 2))
    streak = int(p.get("combat_streak", 0) or 0) if streak_active else 0
    return {
        "combo_step": int(p.get("combo_step", 0) or 0) if combo_active else 0,
        "combo_remaining": max(0.0, round(float(p.get("combo_until", 0) or 0) - now, 2)),
        "streak": streak,
        "streak_bonus_pct": round(min(25.0, streak * 1.5), 1),
        "counter_ready": counter_rem > 0,
        "counter_remaining": counter_rem,
        "last_element": str(p.get("last_element", "") or ""),
    }


def player_row(pid: str, p: dict[str, Any], now: float, *, compact: bool = False) -> dict[str, Any]:
    reconcile_talent_points(p)
    action = None
    if p["attack"]:
        a = p["attack"]
        spec = weapon_spec_for(p, a["weapon"])
        eff_charge = max(0.16, float(spec["charge"]) / max(0.45, 1.0 + equipment_bonuses(p, now)["attack_speed_pct"]))
        action = {"weapon": a["weapon"], "kind": spec["kind"],
                  "charge": min(1.0, max(0.0, (now - a["started"]) / eff_charge)),
                  "aim_x": a["aim_x"], "aim_y": a["aim_y"]}
    zone = region_for(p)
    tree = action_tree(p)
    chosen_class = p.get("class") if p.get("class") in CLASSES else None
    eq_bonuses = equipment_bonuses(p, now)
    w_all = all_weapons(p) if not compact else {}
    spell_catalog = all_spells(p)
    abilities = abilities_view(p, now, eq_bonuses)
    spells = spells_view(p, now, eq_bonuses, spell_catalog)
    combat_view = combat_state_view(p, now)
    journal = quest_journal(p)
    row = {"id": pid, "name": p["name"], "x": round(p["x"], 1), "y": round(p["y"], 1),
            "class": chosen_class, "class_name": CLASSES[chosen_class]["name"] if chosen_class else "Путник",
            "class_offer": p["level"] >= CLASS_MIN_LEVEL and not chosen_class,
            "class_compatible": class_compatible(p, tree), "action_tree": tree,
            "weapon_kind": weapon_kind(p), "mastery": mastery_view(p),
            "abilities": abilities, "spells": spells,
            "class_perks": class_perks_view(p, chosen_class) if chosen_class else [],
            "effects": player_effects(p, now),
            "combat": combat_view,
            "combat_state": combat_view,
            "face_x": p["face_x"], "face_y": p["face_y"], "hp": p["hp"], "max_hp": p["max_hp"],
            "stamina": round(p["stamina"], 1), "max_stamina": p["max_stamina"],
            "mana": round(p.get("mana", 0), 1), "max_mana": p.get("max_mana", 0), "xp": p["xp"],
            "xp_next": xp_for_next_level(p["level"]),
            "level": p["level"], "max_level": PLAYER_MAX_LEVEL,
            "skill_points": p["skill_points"], "talent_points": int(p.get("talent_points", 0) or 0),
            "ability_max_level": ABILITY_MAX_LEVEL, "spell_max_level": SPELL_MAX_LEVEL,
            "mastery_max_level": MASTERY_MAX_LEVEL,
            "ability_levels": {aid: ability_rank(p, aid) for aid in ABILITY_CATALOG},
            "ability_uses": dict(p.get("ability_uses", {}) or {}),
            "spell_upgrades": dict(p.get("spell_upgrades", {}) or {}),
            "stats": dict(p["stats"]),
            "stat_values": {key: int(p["stats"].get(key, 1)) for key in stat_names},
            "stat_caps": dict(STAT_CAPS),
            "upgrades_view": upgrades_view(p),
            "mana_growth": mana_growth_bonus(p), "mana_growth_next": mana_growth_next(p),
            "stats_revision": int(p.get("stats_revision", 0)),
            "gold": p["gold"], "kills": p["kills"], "quest": quest_data(p),
            "respawning": p["respawn_at"] > now, "weapons": list(p["weapons"]), "weapon": p["weapon"],
            "gear": p["gear"], "gear_inventory": list(p["gear_inventory"]),
            "accessories": [a for a in (p.get("accessories") or []) if a in ACCESSORIES],
            "equipped_accessories": equipped_accessories_map(p),
            "accessory_catalog": ACCESSORIES,
            "accessory_sell_prices": {key: accessory_sell_price(key) for key in all_owned_accessories(p)},
            "max_accessory_upgrade": MAX_ACCESSORY_UPGRADE,
            "reforges": p.get("reforges", {"weapon": {}, "gear": {}, "accessory": {}}),
            "herald_story": herald_story_view(p),
            "reforge_prefixes": REFORGE_PREFIXES,
            "custom_weapons": dict(p.get("custom_weapons", {}) or {}),
            "custom_weapon_archetypes": CUSTOM_WEAPON_ARCHETYPES,
            "custom_weapon_cores": CUSTOM_WEAPON_CORES,
            "custom_weapon_tiers": {str(k): v for k, v in CUSTOM_WEAPON_TIERS.items()},
            "equipment_bonuses": {k: round(v, 4) for k, v in eq_bonuses.items()},
            "craft_recipes": CRAFT_RECIPES,
            "forge_blueprints": ({bid: {"name": name, "cost": dict(cost), "category": kind}
                                  for bid, (cost, name, kind) in FORGE_BLUEPRINTS.items()} if not compact else None),
            "craft_catalog": CRAFT_RECIPES,
            "enchantments": p.get("enchantments", {"weapon": {}, "gear": {}}),
            "enchant_max_level": ENCHANT_MAX_LEVEL, "max_item_upgrade": MAX_ITEM_UPGRADE,
            "mana_regen_level": int(p.get("mana_regen_level", 0)),
            "magic_damage_level": int(p.get("magic_damage_level", 0)),
            "insight_level": int(p.get("insight_level", 0) or 0),
            "tenacity_level": int(p.get("tenacity_level", 0) or 0),
            "ferocity_level": int(p.get("ferocity_level", 0) or 0),
            "magic_damage_bonus": int(p.get("magic_damage_level", 0)) * 8,
            "defense": player_defense(p),
            "defense_total": player_defense(p),
            "attack_power": round(weapon_power(p), 1),
            "crit_chance": round(player_crit_chance(p) * 100, 1),
            "crit_chance_pct": round(player_crit_chance(p) * 100, 1),
            "shop_catalog": REGION_SHOPS[p.get("region", "camp")], "sell_prices": SELL_PRICES, "enchant_catalog": ENCHANT_CATALOG,
            "spell_catalog": spell_catalog,
            "spells_unlocked": [sid for sid in spell_catalog if spell_unlocked(p, sid, spell_catalog)],
            "spell_uses": dict(p.get("spell_uses", {})),
            "spell_levels": {sid: spell_mastery_level(p, sid) for sid in spell_catalog},
            "custom_spells": [{**spell, "id": spell_id, "spell_id": spell_id}
                              for spell_id, spell in p.get("custom_spells", {}).items()
                              if isinstance(spell, dict)],
            "spell_cooldowns": {sid: {"remaining": max(0.0, round(until - now, 2)),
                                      "total": spell_cooldown_seconds(p, sid, spell_catalog, eq_bonuses)}
                                for sid, until in p.get("spell_cooldowns", {}).items()},
            "magic_mana_spent": int(p.get("magic_mana_spent", 0)),
            "upgrades": p.get("upgrades", {"weapon": {}, "gear": {}, "accessory": {}}),
            "weapon_sell_prices": {key: weapon_sell_price(key, p) for key in p["weapons"]},
            "gear_sell_prices": {key: gear_sell_price(key) for key in [p["gear"], *p["gear_inventory"]]},
            "gear_catalog": GEAR,
            "weapon_catalog": {key: {"name": value["name"], "rarity": value.get("rarity", "common"),
                                     "damage": value["damage"], "bonus": value.get("bonus", 0),
                                     "kind": value["kind"], "charge": value.get("charge", .7), "range": value.get("range", 420),
                                     "arc": value.get("arc", .28), "spell_power": value.get("spell_power", 0),
                                     "cooldown": value.get("cooldown", .35), "stamina": value.get("stamina", 14),
                                     "color": value.get("color", "#dce8ea"),
                                     "element": value.get("element", ""),
                                     "vampirism": value.get("vampirism", 0),
                                     "crit_bonus": value.get("crit_bonus", 0),
                                     "custom": bool(value.get("custom")),
                                     "archetype": value.get("archetype", ""),
                                     "core": value.get("core", ""),
                                     "lore": value.get("lore", ""),
                                     "reforge": item_reforge_id(p, "weapon", key),
                                     "upgrade": item_upgrade_level(p, "weapon", key)}
                               for key, value in w_all.items()},
            "region": p.get("region", "camp"), "visited_regions": list(p.get("visited_regions", [])),
            "region_quest": region_quest_view(p, p.get("region", "camp")),
            "journal": journal, "tracked_quest": default_tracked_quest(p, journal),
            "gather_kind": gather_node_kind(p),
            "bosses_defeated": list(p.get("bosses_defeated", [])),
            "bestiary_kills": sanitize_kills(p.get("bestiary_kills"), MONSTERS, p.get("bosses_defeated")),
            "world_travel_unlocked": has_free_world_travel(p),
            "main_boss_id": MAIN_BOSS_KIND,
            "recall_ready": time.monotonic() >= float(p.get("recall_at", 0)),
            "in_combat": time.monotonic() - float(p.get("last_combat", 0)) < COMBAT_LOCK,
            "inventory": dict(p["inventory"]), "attack": action,
            "consumable_catalog": ({cid: {"name": c["name"], "description": c.get("description", "")}
                                    for cid, c in CONSUMABLE_ALIASES.items()} if not compact else None),
            "gathering": p["gathering"] is not None, "gather_progress": (p["gathering"]["progress"] / 1.15 if p["gathering"] else 0), "zone": zone["id"],
            "run": bool(p.get("running")), "sneak": bool(p.get("sneaking")),
            "dodge_ready": now >= p["dodge_at"],
            "status": player_status_view(p, now), "damage_points": damage_points_view(p)}
    if not compact:
        row["bestiary_catalog"] = BESTIARY_CATALOG
    if compact:
        for field in (
            "consumable_catalog", "accessory_catalog", "reforge_prefixes", "custom_weapon_archetypes",
            "custom_weapon_cores", "custom_weapon_tiers", "craft_recipes", "forge_blueprints",
            "craft_catalog", "enchant_catalog", "sell_prices", "spell_catalog", "shop_catalog",
            "gear_catalog", "weapon_catalog",
        ):
            row.pop(field, None)
    return row


def public_player_row(pid: str, p: dict[str, Any], now: float) -> dict[str, Any]:
    """Build only the small player state that nearby clients are allowed to see."""
    action = None
    attack = p.get("attack")
    if attack:
        spec = weapon_spec_for(p, attack["weapon"])
        attack_speed = equipment_bonuses(p, now)["attack_speed_pct"]
        effective_charge = max(0.16, float(spec["charge"]) / max(0.45, 1.0 + attack_speed))
        action = {"weapon": attack["weapon"], "kind": spec["kind"],
                  "charge": min(1.0, max(0.0, (now - attack["started"]) / effective_charge)),
                  "aim_x": attack["aim_x"], "aim_y": attack["aim_y"]}

    chosen_class = p.get("class") if p.get("class") in CLASSES else None
    region_id = p.get("region", "camp")
    return {
        "id": pid, "name": p["name"], "x": round(p["x"], 1), "y": round(p["y"], 1),
        "region": region_id, "zone": region_for(p)["id"],
        "face_x": p["face_x"], "face_y": p["face_y"], "hp": p["hp"], "max_hp": p["max_hp"],
        "level": p["level"], "class": chosen_class,
        "class_name": CLASSES[chosen_class]["name"] if chosen_class else "Путник",
        "weapon": p["weapon"], "weapon_kind": weapon_kind(p), "gear": p["gear"],
        "attack": action, "effects": player_effects(p, now), "status": player_status_view(p, now),
        "respawning": p["respawn_at"] > now, "gathering": p["gathering"] is not None,
        "run": bool(p.get("running")), "sneak": bool(p.get("sneaking")),
    }


def snapshot(for_id: str, *, compact: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    own = players[for_id]
    rid = own.get("region", "camp")
    local_players = [(pid, p) for pid, p in players.items() if p.get("region", "camp") == rid]
    rows = []
    for pid, p in local_players:
        rows.append(player_row(pid, p, now, compact=compact) if pid == for_id else public_player_row(pid, p, now))
    return {"type": "state", "you": for_id, **({"compact": True} if compact else {}),
            "world": {"w": MAP_W, "h": MAP_H, "region": rid, "mode": "separate-maps"},
            "region": {"id": rid} if compact else public_region(REGIONS[rid]),
            **({"regions": atlas_view(), "portals": [v for v in PORTALS.values() if v["region"] == rid],
                "zones": [public_region(REGIONS[rid])], "elements": ELEMENT_FX,
                "power_sites": [s for s in POWER_SITES if s["region"] == rid], "classes": CLASSES}
               if not compact else {}),
            "players": rows,
            "mobs": [{**{k: mob[k] for k in ("id", "kind", "level", "x", "y", "hp", "max_hp", "boss", "mini_boss", "region")},
                      "telegraphing": mob["telegraph_until"] > now,
                      "attack_hint": attack_view(mob, now), "phase": boss_phase(mob),
                      "recovering": mob.get("attack_at", 0) > now and not mob.get("telegraph_until", 0),
                      "burning": float(mob.get("burn_until", 0) or 0) > now,
                      "slowed": float(mob.get("slow_until", 0) or 0) > now,
                      "stunned": float(mob.get("stun_until", 0) or 0) > now,
                      "poisoned": float(mob.get("poison_until", 0) or 0) > now,
                      "bleeding": float(mob.get("bleed_until", 0) or 0) > now,
                      "sundered": float(mob.get("sunder_until", 0) or 0) > now,
                      "staggered": float(mob.get("staggered_until", 0) or 0) > now,
                      "stagger": round(float(mob.get("stagger", 0) or 0), 1),
                      "marked": any(float((pl_.get("eagle_marks") or {}).get(mob["id"], 0) or 0) > now
                                    for pl_ in players.values() if same_region(pl_, mob))}
                     for mob in mobs if mob["hp"] > 0 and mob["region"] == rid],
            "nodes": [{k: n[k] for k in ("id", "kind", "x", "y", "active", "zone", "region")} for n in nodes if n["region"] == rid],
            "arrows": [{k: a[k] for k in ("x", "y", "vx", "vy", "life", "kind", "radius", "element", "spell_id", "spell_kind", "spell_rarity", "spell_mastery", "spell_variant", "spell_palette", "max_distance", "travelled", "region") if k in a} for a in arrows if a.get("region") == rid],
            "thorn_fields": [{k: field[k] for k in ("x", "y", "radius", "until", "owner", "region")} for field in thorn_fields if field.get("region") == rid],
            "ground_effects": [{"id": field["id"], "region": field["region"], "kind": field["kind"], "x": round(field["x"], 1),
                                 "y": round(field["y"], 1), "radius": field["radius"],
                                 "owner": field.get("owner"), "remaining": round(max(0.0, field["until"] - now), 2),
                                 "telegraph": round(max(0.0, field.get("activate_at", now) - now), 2),
                                 "duration": round(max(.01, field["until"] - field["started"]), 2)}
                                for field in ground_effects if field.get("region") == rid]}


def drop_client(pid: str, *, save: bool = True) -> dict[str, Any] | None:
    """Remove a player from the live world and persist their progress.

    Called both by the WebSocket handler (clean disconnect) and by the idle
    watchdog (a tab was closed but the TCP connection stayed half-open).
    Returns the removed player so the caller can announce the departure, or
    ``None`` when the slot was already freed by someone else.
    """
    player = players.pop(pid, None)
    clients.pop(pid, None)
    snapshot_profiles_sent.discard(pid)
    last_seen_at.pop(pid, None)
    last_ping_at.pop(pid, None)
    if player is not None and save:
        try:
            save_character(player)
        except sqlite3.Error:
            pass
    return player


async def sweep_stale_clients() -> None:
    """One watchdog pass: ping live sockets and evict silent ones."""
    now = time.monotonic()
    for pid, socket in list(clients.items()):
        last_seen = float(last_seen_at.get(pid, now))
        if now - last_seen > IDLE_TIMEOUT:
            player = drop_client(pid)
            if player is not None:
                await send_event({"type": "notice",
                                  "text": f"{player['name']} потерял(а) связь и был(а) "
                                          f"выгружен(а) из мира."})
            try:
                await socket.send_json({"type": "kick",
                                        "message": "Связь с миром потеряна — войди снова, чтобы продолжить."})
            except Exception:
                pass
            try:
                await socket.close(code=1000, reason="IDLE_TIMEOUT")
            except Exception:
                pass
            continue
        if now - float(last_ping_at.get(pid, 0)) >= HEARTBEAT_INTERVAL:
            last_ping_at[pid] = now
            try:
                await socket.send_json({"type": "ping", "t": round(now, 2)})
            except Exception:
                # The transport is already broken: free the slot right away.
                player = drop_client(pid)
                if player is not None:
                    await send_event({"type": "notice", "text": f"{player['name']} покинул(а) мир."})


async def close_stale_clients_once() -> None:
    """Immediate sweep used when the world looks full but someone wants in.

    Ghost connections of closed tabs are usually older than the heartbeat
    interval, so a quick double ping flushes their buffers and reveals the dead
    transports; anything still silent afterwards gets evicted.
    """
    await sweep_stale_clients()
    await asyncio.sleep(0.35)
    await sweep_stale_clients()


async def close_stale_clients() -> None:
    """Periodically kick connections that stopped answering the heartbeat.

    A browser tab that is closed (or a device that loses network) does not
    always send a TCP FIN/RST, so the endpoint stays blocked in
    ``receive_text()`` forever and keeps occupying one of the MAX_PLAYERS slots.
    Every CLEANUP_INTERVAL we ping such sockets; when a client stays silent
    longer than IDLE_TIMEOUT we force-close it and free its slot.
    """
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        await sweep_stale_clients()


async def send_event(event: dict[str, Any]) -> None:
    payload = json.dumps(event, ensure_ascii=False)
    target, region = event.get("target"), event.get("region")
    for pid, socket in list(clients.items()):
        if target and pid != target:
            continue
        if region and pid in players and players[pid].get("region") != region:
            continue
        try:
            await socket.send_text(payload)
        except Exception:
            # Broken transport: free the world slot instead of leaving a ghost.
            drop_client(pid)


async def announce_departure(name: str) -> None:
    await send_event({"type": "notice", "text": f"{name} покинул(а) мир."})


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
    p = {**p, "stats": enriched}
    return _upgrades_view_core(p)


def player_crit_chance(p: dict[str, Any]) -> float:
    prec = max(1, int(p.get("stats", {}).get("precision", 1)))
    # Up to 30% from first 13 precision, then +1.2% per extra point up to 55% base
    raw = min(0.30, (prec - 1) * 0.025) + max(0, prec - 13) * 0.012
    if p.get("class") == "ranger" and mastery_level(p, "ranger") >= 5:
        raw += 0.08
    streak = int(p.get("combat_streak", 0) or 0) if float(p.get("streak_until", 0) or 0) > time.monotonic() else 0
    raw += min(0.10, streak * 0.006)
    raw += equipment_bonuses(p)["crit_pct"]
    return min(0.90, max(0.0, raw))


def _upgrades_view_core(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stats = p.get("stats", {})
    prec = max(1, int(stats.get("precision", 1)))
    crit_pct = (min(0.30, (prec - 1) * 0.025) + max(0, prec - 13) * 0.012) * 100
    fort = max(1, int(stats.get("fortune", 1)))
    loot_pct = (min(0.20, (fort - 1) * 0.025) + max(0, fort - 9) * 0.012) * 100
    ins = max(0, int(p.get("insight_level", 0) or 0))
    cdr_pct = min(25.0, ins * 0.65)
    ten = max(0, int(p.get("tenacity_level", 0) or 0))
    fer = max(0, int(p.get("ferocity_level", 0) or 0))
    return {
        "might": {"level": int(stats.get("might", 1)), "max": STAT_CAPS["might"], "effect": f"+{(int(stats.get('might', 1))-1)*2.2:.1f} к урону оружия"},
        "vitality": {"level": int(stats.get("vitality", 1)), "max": STAT_CAPS["vitality"], "effect": f"{int(p.get('max_hp', 100))} макс. здоровья"},
        "agility": {"level": int(stats.get("agility", 1)), "max": STAT_CAPS["agility"], "effect": f"{int(p.get('max_stamina', 100))} выносливости · скорость +{(int(stats.get('agility', 1))-1)*3.2:.0f}"},
        "mana_regen": {"level": int(p.get("mana_regen_level", 0)), "max": STAT_CAPS["mana_regen"], "effect": f"+{9 + 1.5*int(p.get('mana_regen_level', 0)):.1f} маны/с"},
        "magic_damage": {"level": int(p.get("magic_damage_level", 0)), "max": STAT_CAPS["magic_damage"], "effect": f"+{int(p.get('magic_damage_level', 0))*8}% урона заклинаний"},
        "insight": {"level": ins, "max": STAT_CAPS["insight"], "effect": f"опыт ×{1 + 0.04*ins:.2f} · монеты +{min(120, ins*3)}% · КД -{cdr_pct:.1f}%"},
        "precision": {"level": prec, "max": STAT_CAPS["precision"], "effect": f"+{crit_pct:.1f}% шанс крита · крит ×{1.75 + max(0, prec - 13)*0.02:.2f}"},
        "fortune": {"level": fort, "max": STAT_CAPS["fortune"], "effect": f"+{loot_pct:.1f}% шанс редкой добычи"},
        "tenacity": {"level": ten, "max": STAT_CAPS["tenacity"], "effect": f"+{ten*4} HP · -{ten*0.5:.1f}% входящего урона · -{ten}% стан"},
        "ferocity": {"level": fer, "max": STAT_CAPS["ferocity"], "effect": f"+{fer*0.5:.1f}% урона · +{fer*1.5:.1f}% крит. урона · +{fer}% ошеломления"},
    }


def mastery_required_xp(level: int) -> int:
    level = max(1, min(MASTERY_MAX_LEVEL, int(level)))
    if level >= MASTERY_MAX_LEVEL:
        return 0
    return 80 + level * 40 + max(0, level - 5) * 18


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
        xp = max(0, min(500000, int(entry.get("xp", 0) or 0)))
        needed = mastery_required_xp(level)
        if needed and xp >= needed:
            xp = max(0, needed - 1)
        result[tree] = {
            "level": level, "xp": xp, "next": needed,
            "total_xp": max(0, min(5000000, int(entry.get("total_xp", xp) or xp))),
            "unlocked": [aid for aid, spec in ABILITY_CATALOG.items()
                         if spec["tree"] == tree and spec["mastery"] <= level],
        }
    return result


def mastery_level(p: dict[str, Any], tree: str) -> int:
    entry = p.get("mastery", {}).get(tree, {}) if isinstance(p.get("mastery"), dict) else {}
    return max(1, min(MASTERY_MAX_LEVEL, int(entry.get("level", 1) or 1)))


def class_perks_view(p: dict[str, Any], tree: str) -> list[dict[str, Any]]:
    lvl = mastery_level(p, tree)
    return [{**perk, "unlocked": lvl >= int(perk["level"])} for perk in CLASS_PERKS.get(tree, [])]


def has_class_perk(p: dict[str, Any], tree: str, min_level: int) -> bool:
    return p.get("class") == tree and mastery_level(p, tree) >= min_level


def mastery_view(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    view: dict[str, dict[str, Any]] = {}
    for tree in MASTERY_TREES:
        entry = p.get("mastery", {}).get(tree, {}) if isinstance(p.get("mastery"), dict) else {}
        level = mastery_level(p, tree)
        unlocked = [aid for aid, spec in ABILITY_CATALOG.items()
                    if spec["tree"] == tree and spec["mastery"] <= level]
        view[tree] = {"name": MASTERY_NAMES[tree], "level": level, "max": MASTERY_MAX_LEVEL,
                      "xp": max(0, int(entry.get("xp", 0) or 0)),
                      "next": mastery_required_xp(level), "unlocked": unlocked,
                      "power_bonus_pct": round((level - 1) * 2.5, 1),
                      "perks": class_perks_view(p, tree)}
    return view


def ability_unlocked(p: dict[str, Any], ability_id: str) -> bool:
    spec = ABILITY_CATALOG.get(ability_id)
    return bool(spec and spec["mastery"] <= mastery_level(p, spec["tree"]))


def ability_rank(p: dict[str, Any], ability_id: str) -> int:
    levels = p.get("ability_levels") if isinstance(p.get("ability_levels"), dict) else {}
    raw = int(levels.get(ability_id, 1) or 1)
    return max(1, min(ABILITY_MAX_LEVEL, raw))


def ability_rank_mult(rank: int) -> float:
    return 1.0 + 0.09 * max(0, int(rank) - 1)


def ability_cooldown_seconds(p: dict[str, Any], ability_id: str,
                             eq_bonuses: dict[str, float] | None = None) -> float:
    spec = ABILITY_CATALOG.get(ability_id, {})
    mastery = mastery_level(p, str(spec.get("tree", "warrior")))
    rank = ability_rank(p, ability_id)
    ins_cdr = min(0.25, max(0, int(p.get("insight_level", 0) or 0)) * 0.0065)
    bonuses = eq_bonuses if eq_bonuses is not None else equipment_bonuses(p)
    eq_cdr = bonuses["cdr_pct"]
    mastery_cdr = min(0.35, 0.025 * (mastery - 1))
    rank_cdr = 0.025 * (rank - 1)
    total_factor = max(0.30, (1.0 - mastery_cdr) * (1.0 - rank_cdr) * (1.0 - ins_cdr) * (1.0 - eq_cdr))
    return round(max(1.0, float(spec.get("cooldown", 8.0)) * total_factor), 2)


def count_spent_talent_points(p: dict[str, Any]) -> int:
    spent = 0
    ab_levels = p.get("ability_levels") if isinstance(p.get("ability_levels"), dict) else {}
    for aid, rk in ab_levels.items():
        if aid in ABILITY_CATALOG:
            spent += max(0, min(ABILITY_MAX_LEVEL, int(rk or 1)) - 1)
    sp_upgrades = p.get("spell_upgrades") if isinstance(p.get("spell_upgrades"), dict) else {}
    for sid, up in sp_upgrades.items():
        spent += max(0, min(SPELL_MAX_LEVEL, int(up or 0)))
    paid_with_gold = max(0, int(p.get("gold_skill_upgrades", 0) or 0))
    return max(0, spent - paid_with_gold)


def reconcile_talent_points(p: dict[str, Any]) -> None:
    """Recompute available skill/spell upgrade points from level, mastery and defeated bosses."""
    earned = max(0, int(p.get("level", 1)) - 1)
    for tree in MASTERY_TREES:
        earned += max(0, mastery_level(p, tree) - 1) // 3
    earned += len(p.get("bosses_defeated") or []) * 2
    earned += max(0, int(p.get("bonus_talent_points", 0) or 0))
    p["talent_points"] = max(0, earned - count_spent_talent_points(p))


def weapon_kind(p: dict[str, Any]) -> str:
    return str(weapon_spec_for(p, p.get("weapon", "")).get("kind", "melee"))


def action_tree(p: dict[str, Any]) -> str:
    return WEAPON_TREE.get(weapon_kind(p), "warrior")


def class_compatible(p: dict[str, Any], tree: str | None = None) -> bool:
    tree = tree or action_tree(p)
    chosen = p.get("class")
    if not chosen:
        # No qualification yet: nothing is available — neither abilities nor magic.
        return False
    return chosen == tree


def spells_allowed(p: dict[str, Any]) -> tuple[bool, str]:
    """Magic is reserved for the Mage qualification (server side gate)."""
    if p.get("class") != "mage":
        return False, "Сначала выбери квалификацию «Маг» — заклинания доступны только магам."
    if weapon_kind(p) != "staff":
        return False, "Для заклинаний нужен посох. Сейчас в руках другое оружие."
    return True, ""


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
    ward_until = float(p.get("ward_until", 0) or 0)
    if ward_until > now:
        effects.append({"kind": "ward", "name": "Чародейский щит", "remaining": round(ward_until - now, 2)})
    counter_until = float(p.get("counter_until", 0) or 0)
    if counter_until > now:
        effects.append({"kind": "counter", "name": "Контратака (+40%)", "remaining": round(counter_until - now, 2)})
    for bf, bkind, bname in (
        ("rage_until", "rage", "Ярость берсерка"),
        ("ironskin_until", "ironskin", "Каменная кожа"),
        ("haste_until", "haste", "Стремительный ветер"),
        ("arcane_tonic_until", "arcane_tonic", "Звёздный тоник"),
    ):
        bu = float(p.get(bf, 0) or 0)
        if bu > now:
            effects.append({"kind": bkind, "name": bname, "remaining": round(bu - now, 2)})
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


def ability_effective_cost(p: dict[str, Any], ability_id: str,
                           eq_bonuses: dict[str, float] | None = None) -> int:
    spec = ABILITY_CATALOG.get(ability_id, {})
    base = float(spec.get("cost", 0))
    if base <= 0:
        return 0
    rank = ability_rank(p, ability_id)
    if rank >= 5:
        base *= 0.88
    eq = eq_bonuses if eq_bonuses is not None else equipment_bonuses(p)
    res_kind = str(spec.get("resource") or "stamina")
    base *= (1.0 - eq["mana_cost_pct"]) if res_kind == "mana" else (1.0 - eq["stamina_cost_pct"])
    return max(1, round(base))


def abilities_view(p: dict[str, Any], now: float,
                   eq_bonuses: dict[str, float] | None = None) -> dict[str, dict[str, Any]]:
    eq_bonuses = eq_bonuses if eq_bonuses is not None else equipment_bonuses(p, now)
    cooldowns = p.get("ability_cooldowns", {}) if isinstance(p.get("ability_cooldowns"), dict) else {}
    uses_map = p.get("ability_uses", {}) if isinstance(p.get("ability_uses"), dict) else {}
    result: dict[str, dict[str, Any]] = {}
    for ability_id, spec in ABILITY_CATALOG.items():
        until = float(cooldowns.get(ability_id, 0) or 0)
        rank = ability_rank(p, ability_id)
        radius_mult = 1.15 if rank >= 5 else 1.0
        result[ability_id] = {
            "id": ability_id, "tree": spec["tree"], "name": spec["name"], "icon": spec.get("icon", "✦"),
            "desc": spec["desc"], "cost": ability_effective_cost(p, ability_id, eq_bonuses), "arrows": int(spec.get("arrows", 0)),
            "resource": str(spec.get("resource") or "stamina"),
            "mastery_required": int(spec["mastery"]), "unlocked": ability_unlocked(p, ability_id),
            "level": rank, "max_level": ABILITY_MAX_LEVEL,
            "uses": int(uses_map.get(ability_id, 0) or 0),
            "power_bonus_pct": round((ability_rank_mult(rank) - 1.0) * 100),
            "awakened": rank >= 10,
            "key": spec.get("key", ""), "cooldown": ability_cooldown_seconds(p, ability_id, eq_bonuses),
            "range": round(float(spec.get("range", 0) or 0) * radius_mult, 1),
            "radius": round(float(spec.get("radius", 0) or 0) * radius_mult, 1),
            "distance": float(spec.get("distance", 0) or 0), "width": float(spec.get("width", 0) or 0),
            "telegraph": float(spec.get("telegraph", 0) or 0),
            "remaining": max(0.0, round(until - now, 2)),
        }
    return result


def weapon_power(p: dict[str, Any]) -> float:
    wid = str(p.get("weapon") or "")
    spec = weapon_spec_for(p, wid)
    upgrade = 0 if spec.get("kind") == "staff" else 6 * item_upgrade_level(p, "weapon", wid)
    base = (float(spec.get("damage", 0)) + float(spec.get("bonus", 0)) * .55
            + (int(p.get("stats", {}).get("might", 1)) - 1) * 2.2
            + 8 * enchant_level(p, "weapon", wid, "sharpness") + upgrade)
    eq = equipment_bonuses(p)
    kind = spec.get("kind", "melee")
    arch_pct = eq["bow_pct"] if kind == "bow" else eq["spell_power_pct"] if kind == "staff" else eq["melee_pct"]
    if kind == "staff" and p.get("class") == "mage":
        # Staff abilities scale with spell power and magic damage upgrades as well
        staff_up = 6 * item_upgrade_level(p, "weapon", wid)
        base = (base + staff_up) * (1.0 + 0.04 * int(p.get("magic_damage_level", 0) or 0))
    return max(1.0, base * (1.0 + eq["damage_pct"] + arch_pct))


def award_mastery(p: dict[str, Any], tree: str, amount: int) -> bool:
    if tree not in MASTERY_TREES or amount <= 0:
        return False
    mastery = p.setdefault("mastery", normalize_mastery({}))
    entry = mastery.setdefault(tree, {"level": 1, "xp": 0, "total_xp": 0, "unlocked": []})
    old_level = max(1, min(MASTERY_MAX_LEVEL, int(entry.get("level", 1) or 1)))
    entry["level"] = old_level
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
    if entry["level"] >= MASTERY_MAX_LEVEL:
        entry["xp"] = 0
    entry["next"] = mastery_required_xp(entry["level"])
    entry["unlocked"] = [aid for aid, spec in ABILITY_CATALOG.items()
                         if spec["tree"] == tree and spec["mastery"] <= entry["level"]]
    if leveled:
        reconcile_talent_points(p)
        update_derived(p)
        broadcast({
            "type": "mastery_update", "target": p.get("id"), "tree": tree,
            "mastery": mastery_view(p), "level": entry["level"],
            "unlocked": entry["unlocked"],
            "talent_points": int(p.get("talent_points", 0) or 0),
        })
        names = [ABILITY_CATALOG[aid]["name"] for aid in entry["unlocked"]
                 if old_level < ABILITY_CATALOG[aid]["mastery"] <= entry["level"]]
        perks = [pk["name"] for pk in CLASS_PERKS.get(tree, [])
                 if old_level < int(pk["level"]) <= entry["level"]]
        text = (f"Мастерство «{MASTERY_NAMES[tree]}» достигло {entry['level']}/{MASTERY_MAX_LEVEL} ур."
                + (f" Открыто: {', '.join(names)}." if names else "")
                + (f" Талант класса: «{', '.join(perks)}»!" if perks else ""))
        broadcast({"type": "notice", "target": str(p.get("id", "")), "text": text})
    return leveled


def stats_updated_event(pid: str, p: dict[str, Any]) -> dict[str, Any]:
    """Build one authoritative update for the characteristics panel."""
    reconcile_talent_points(p)
    return {
        "type": "stats_updated", "target": pid,
        "stats": {key: int(p.get("stats", {}).get(key, 1)) for key in stat_names},
        "stat_values": {key: int(p.get("stats", {}).get(key, 1)) for key in stat_names},
        "skill_points": max(0, int(p.get("skill_points", 0))),
        "talent_points": max(0, int(p.get("talent_points", 0) or 0)),
        "xp": max(0, int(p.get("xp", 0))),
        "xp_next": xp_for_next_level(int(p.get("level", 1))),
        "level": max(1, int(p.get("level", 1))),
        "max_level": PLAYER_MAX_LEVEL,
        "mana_regen_level": max(0, int(p.get("mana_regen_level", 0))),
        "magic_damage_level": max(0, int(p.get("magic_damage_level", 0))),
        "insight_level": max(0, int(p.get("insight_level", 0) or 0)),
        "tenacity_level": max(0, int(p.get("tenacity_level", 0) or 0)),
        "ferocity_level": max(0, int(p.get("ferocity_level", 0) or 0)),
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
    eq = equipment_bonuses(p)
    p["max_hp"] = max(20, round(100 + (p["level"] - 1) * 7 + (p["stats"]["vitality"] - 1) * 12 + eq["hp_flat"]))
    p["max_stamina"] = max(30, round(100 + (p["stats"]["agility"] - 1) * 5 + (p["stats"]["might"] - 1) * 2 + eq["stamina_flat"]))
    previous_max_mana = p.get("max_mana", 60)
    mage_perk_mana = 25 if has_class_perk(p, "mage", 5) else 0
    p["max_mana"] = max(20, round(60 + (p["level"] - 1) * 5 + (p["stats"]["vitality"] - 1) * 3
                        + int(p.get("mana_regen_level", 0)) * 2 + mana_growth_bonus(p) + mage_perk_mana + eq["mana_flat"]))
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
    if int(p.get("level", 1)) >= PLAYER_MAX_LEVEL:
        p["level"] = PLAYER_MAX_LEVEL
        p["xp"] = 0
        return
    p["xp"] += amount
    changed = False
    while p["level"] < PLAYER_MAX_LEVEL and p["xp"] >= p["level"] * 120:
        p["xp"] -= p["level"] * 120
        p["level"] += 1
        p["skill_points"] += 1
        reconcile_talent_points(p)
        update_derived(p)
        p["hp"] = min(p["max_hp"], p["hp"] + 24)
        changed = True
    if p["level"] >= PLAYER_MAX_LEVEL:
        p["xp"] = 0
    if changed:
        p["stats_revision"] = int(p.get("stats_revision", 0)) + 1
        for pid, current in list(players.items()):
            if current is p:
                broadcast(stats_updated_event(pid, p))
                break
        broadcast({"type": "notice", "text": f"{p['name']} достиг(ла) {p['level']} уровня — +1 очко развития и +1 очко навыков!"})
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
    return near_npc(p, "camp-guide", "quest") is not None


def region_quest_view(p: dict[str, Any], region_id: str) -> dict[str, Any]:
    spec = REGION_QUESTS[region_id]
    state = p.setdefault("region_quests", {}).get(region_id, {"active": False, "done": False, "gather": {}, "kills": {}})
    return {**spec, **state, "region": region_id}


async def npc_dialog(p: dict[str, Any], npc: dict[str, Any]) -> None:
    await send_event({"type": "npc_dialog", "target": p["id"], "npc": npc,
                      "quest": region_quest_view(p, p["region"]) if "quest" in npc["services"] else None,
                      "herald_story": herald_story_view(p) if npc.get("id") == "camp-guide" else None})


async def interact_keeper(p: dict[str, Any]) -> None:
    npc = nearest_npc(p)
    if npc:
        await npc_dialog(p, npc)
        return
    portal = next((v for v in PORTALS.values() if same_region(p, v) and
                   math.hypot(p["x"] - v["x"], p["y"] - v["y"]) <= PORTAL_RADIUS), None)
    if portal:
        await send_event({"type": "portal_dialog", "target": p["id"], "portal": portal})
        return
    if any(n["active"] and same_region(p, n) and math.hypot(p["x"] - n["x"], p["y"] - n["y"]) < 75 for n in nodes):
        start_gather(p, time.monotonic())
        return
    await tell(p["id"], "Подойди к жителю, дорожному камню или ресурсу. Жители отмечены в атласе.")


async def npc_quest_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    npc = near_npc(p, str(msg.get("npc_id", "")), "quest")
    if not npc:
        await tell(p["id"], "Хранитель истории должен быть рядом, на этой же карте."); return
    rid = p["region"]
    q = region_quest_view(p, rid)
    action = str(msg.get("action", ""))
    if rid == "camp" and str(msg.get("quest_kind", "story")) != "region":
        quest_kind = str(msg.get("quest_kind", "story"))
        if quest_kind == "herald_story":
            chapter = herald_story_view(p)
            if action == "accept" and chapter["stage"] < chapter["total"] and not chapter["active"]:
                p["herald_story_active"] = True
                p["herald_story_kills"] = 0
                current = HERALD_QUESTS[chapter["stage"]]
                await tell(p["id"], f"Новая охота: «{current['title']}». Ищи: {MONSTERS[current['mob']]['name']}.")
            elif action == "claim" and chapter["active"] and chapter["kills"] >= 1:
                stage = chapter["stage"]
                reward = HERALD_QUESTS[stage]
                p["herald_story_active"] = False
                p["herald_story_stage"] = stage + 1
                p["herald_story_kills"] = 0
                if str(p.get("tracked_quest") or "") == f"herald:{stage}":
                    p["tracked_quest"] = ""
                p["gold"] += reward["gold"]
                add_xp(p, reward["xp"])
                p["skill_points"] = int(p.get("skill_points", 0)) + 1
                p["quest_points"] = int(p.get("quest_points", 0)) + 1
                unlock = " Сеть эха открыта магам!" if p["herald_story_stage"] == len(HERALD_QUESTS) else ""
                await tell(p["id"], f"Глава завершена: +{reward['gold']} монет, +{reward['xp']} опыта и +1 очко развития.{unlock}")
            else:
                await tell(p["id"], "Сначала прими текущую охоту, затем одолей указанного вестника.")
        # The original 13-stage story remains available at the camp guide.
        elif action == "accept" and not p["quest_active"] and p["quest_stage"] < len(QUESTS):
            p["quest_active"] = True; p["quest_kills"] = {}; p["quest_gather"] = {}
            await tell(p["id"], f"Новое поручение: {quest_requirements(p['quest_stage'])[4]}.")
        elif action == "claim" and p["quest_active"] and quest_complete(p):
            stage = p["quest_stage"]; p["quest_active"] = False; p["quest_stage"] += 1
            if str(p.get("tracked_quest") or "") == f"story:{stage}":
                p["tracked_quest"] = ""   # сданное не висит в трекере — журнал подскажет следующее
            gold, xp, rewards = QUEST_REWARDS[stage]
            p["gold"] += gold; add_xp(p, xp)
            p["skill_points"] = int(p.get("skill_points", 0)) + 1
            p["quest_points"] = int(p.get("quest_points", 0)) + 1
            for reward_type, item_id, amount in rewards:
                if reward_type == "potion": p["inventory"]["potion"] += amount
                elif reward_type == "gear":
                    for _ in range(amount): grant_gear(p, item_id)
                elif reward_type == "weapon":
                    for _ in range(amount): grant_weapon(p, item_id)
            await tell(p["id"], f"Поручение завершено: +{gold} монет, +{xp} опыта, +1 очко развития и награда.")
        else:
            await tell(p["id"], "Поговори с Хранителем: сначала прими поручение, затем выполни его цели.")
    elif action == "accept" and not q["active"] and not q["done"]:
        p["region_quests"][rid] = {"active": True, "done": False, "gather": {}, "kills": {}}
        await tell(p["id"], f"Принято поручение «{q['title']}». Оно засчитывается только в этом регионе.")
    elif action == "claim" and q["active"] and not q["done"]:
        ready = (q["gather"].get(q["resource"], 0) >= q["count"] and
                 (not q["resource2"] or q["count2"] <= 0 or q["gather"].get(q["resource2"], 0) >= q["count2"]) and
                 (not q["mob"] or q["kills"].get(q["mob"], 0) >= q["mob_count"]))
        if not ready:
            await tell(p["id"], "Цели местного поручения ещё не выполнены."); return
        # Progress is not ownership: materials may have been sold or crafted since.
        if p["inventory"].get(q["resource"], 0) < q["count"] or (q["resource2"] and q["count2"] > 0 and p["inventory"].get(q["resource2"], 0) < q["count2"]):
            await tell(p["id"], "Для сдачи поручения принеси материалы в рюкзаке. Часть уже потрачена."); return
        # Completion consumes gathered materials, never the player's entire stock.
        p["inventory"][q["resource"]] -= q["count"]
        if q["resource2"] and q["count2"] > 0: p["inventory"][q["resource2"]] -= q["count2"]
        p["region_quests"][rid]["active"] = False; p["region_quests"][rid]["done"] = True
        if str(p.get("tracked_quest") or "") == f"region:{rid}":
            p["tracked_quest"] = ""
        p["gold"] += q["gold"]; add_xp(p, q["xp"]); p["inventory"]["potion"] += 2
        p["skill_points"] = int(p.get("skill_points", 0)) + 1
        await tell(p["id"], f"«{q['title']}» завершено: +{q['gold']} монет, +{q['xp']} опыта, настойки и очко развития.")
    else:
        await tell(p["id"], "Это поручение уже выполнено или ещё не принято.")
    await sync_station_state(p)
    await npc_dialog(p, npc)


def record_region_progress(p: dict[str, Any], kind: str, amount: int, *, kill: bool = False,
                           region_id: str | None = None) -> None:
    rid = region_id or p.get("region", "camp")
    state = p.setdefault("region_quests", {}).get(rid)
    if not state or not state.get("active") or state.get("done"):
        return
    bucket = state.setdefault("kills" if kill else "gather", {})
    bucket[kind] = int(bucket.get(kind, 0)) + amount


async def enter_region(p: dict[str, Any], region_id: str, x: float, y: float, reason: str = "travel") -> None:
    """Atomic map change: no old-map projectiles, gathering or combat can follow."""
    now = time.monotonic()
    r = REGIONS[region_id]
    p.update(region=region_id, zone=region_id, x=float(x), y=float(y), mx=0.0, my=0.0,
             attack=None, gathering=None, ability_lock_until=now + .35,
             travel_lock_until=now + 1.2, last_combat=0.0)
    p.setdefault("visited_regions", [])
    if region_id not in p["visited_regions"]: p["visited_regions"].append(region_id)
    arrows[:] = [a for a in arrows if a.get("owner") != p["id"]]
    thorn_fields[:] = [f for f in thorn_fields if f.get("owner") != p["id"]]
    ground_effects[:] = [f for f in ground_effects if f.get("owner") != p["id"]]
    p["eagle_marks"] = {}
    for key in ("slow_until", "stun_until", "poison_until", "burn_until"):
        p[key] = 0.0
    save_character(p)
    await send_event({"type": "region_changed", "target": p["id"], "region_id": region_id,
                      "name": r["name"], "reason": reason, "x": x, "y": y})
    await send_event({**snapshot(p["id"]), "target": p["id"]})


async def travel_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    now = time.monotonic()
    if p.get("respawn_at", 0) > now:
        await tell(p["id"], "Дождись возвращения в лагерь."); return
    if now < float(p.get("travel_lock_until", 0)):
        return
    if now - float(p.get("last_combat", 0)) < COMBAT_LOCK:
        await tell(p["id"], "Дорожный камень недоступен в бою. Отступи и подожди 6 секунд."); return
    portal = PORTALS.get(str(msg.get("portal_id", "")))
    if not portal or not same_region(p, portal) or math.hypot(p["x"] - portal["x"], p["y"] - portal["y"]) > PORTAL_RADIUS:
        await tell(p["id"], "Подойди к дорожному камню на краю текущей карты."); return
    target = REGIONS[portal["target"]]
    if p["level"] < target["min_level"]:
        await tell(p["id"], f"Для «{target['name']}» нужен уровень {target['min_level']}. Сейчас: {p['level']}."); return
    arrival = next(v for v in PORTALS.values() if v["region"] == target["id"] and v["target"] == p["region"])
    x = arrival["x"] + (155 if arrival["side"] == "west" else -155)
    await enter_region(p, target["id"], x, arrival["y"])
    await tell(p["id"], f"Открыта дорога: {target['name']}. У каждого края — свой дорожный камень.")


async def recall_action(p: dict[str, Any]) -> None:
    now = time.monotonic()
    if p.get("respawn_at", 0) > now: return
    if now - float(p.get("last_combat", 0)) < COMBAT_LOCK:
        await tell(p["id"], "Возвращение недоступно в бою. Подожди 6 секунд после последнего удара."); return
    if now < float(p.get("recall_at", 0)):
        await tell(p["id"], f"Камень возвращения восстановится через {math.ceil(p['recall_at'] - now)} с."); return
    if p["region"] == "camp":
        await tell(p["id"], "Ты уже в лагере. Отдохни у костра."); return
    p["recall_at"] = now + 20
    await enter_region(p, "camp", *SPAWN, reason="recall")


def safe_region_arrival(region_id: str) -> tuple[float, float]:
    """Safe arrival coordinates in any region for free world travel."""
    if region_id == "camp":
        return SPAWN
    guide = NPCS.get(f"{region_id}-guide")
    if guide:
        return resolve_collision(region_id, float(guide["x"]) + 42.0, float(guide["y"]) + 36.0, 15.0)
    portal = next((v for v in PORTALS.values() if v["region"] == region_id and v["side"] == "west"), None)
    if portal is None:
        portal = next((v for v in PORTALS.values() if v["region"] == region_id), None)
    if portal:
        offset = 155.0 if portal["side"] == "west" else -155.0
        return resolve_collision(region_id, float(portal["x"]) + offset, float(portal["y"]), 15.0)
    return SPAWN


async def world_travel_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    """Free teleportation to any world/region after defeating the main boss (ancient_warden)."""
    now = time.monotonic()
    if p.get("respawn_at", 0) > now:
        await tell(p["id"], "Дождись возрождения перед перемещением между мирами."); return
    if now < float(p.get("travel_lock_until", 0)):
        return
    if now - float(p.get("last_combat", 0)) < COMBAT_LOCK:
        await tell(p["id"], "Межмировой переход недоступен в бою. Отступи и подожди 6 секунд."); return
    if not has_free_world_travel(p):
        await tell(p["id"], "Свободное перемещение между мирами откроется после победы над главным боссом — Хранителем Первозданного сада!"); return
    target_id = str(msg.get("region") or msg.get("region_id") or "")
    if target_id not in REGIONS:
        await tell(p["id"], "Неизвестный мир для перемещения."); return
    if target_id == p.get("region"):
        await tell(p["id"], f"Ты уже находишься в мире «{REGIONS[target_id]['name']}»."); return
    ax, ay = safe_region_arrival(target_id)
    await enter_region(p, target_id, ax, ay, reason="world_travel")
    await tell(p["id"], f"Межмировой переход совершён: {REGIONS[target_id]['name']}.")


def loot_chance(p: dict[str, Any], base_chance: float) -> bool:
    luck = max(0, int(p.get("stats", {}).get("fortune", 1)) - 1)
    bonus = min(.20, luck * .025) + max(0, luck - 8) * .012 + equipment_bonuses(p)["luck_pct"]
    return random.random() < min(.95, base_chance + bonus)


def insight_level(p: dict[str, Any]) -> int:
    return max(0, int(p.get("insight_level", 0) or 0))


MOB_CONTRIBUTION_WINDOW = 120.0
MOB_CONTRIBUTION_MIN_FRACTION = 0.05


def record_mob_contribution(p: dict[str, Any], mob: dict[str, Any], damage: float, now: float) -> None:
    """Record capped, recent player damage used for co-op kill eligibility."""
    try:
        dealt = max(0.0, min(float(damage), float(mob.get("hp", 0) or 0)))
        max_hp = max(0.0, float(mob.get("max_hp", 0) or 0))
    except (TypeError, ValueError):
        return
    player_id = str(p.get("id") or "")
    if not player_id or dealt <= 0 or max_hp <= 0:
        return
    contributions = mob.setdefault("_contributors", {})
    if not isinstance(contributions, dict):
        contributions = mob["_contributors"] = {}
    now = float(now)
    for old_id, entry in list(contributions.items()):
        try:
            expired = now - float(entry.get("last_hit", 0)) > MOB_CONTRIBUTION_WINDOW
        except (AttributeError, TypeError, ValueError):
            expired = True
        if expired or (old_id != player_id and old_id not in players):
            contributions.pop(old_id, None)
    if player_id not in contributions and len(contributions) >= MAX_PLAYERS:
        weakest = min(contributions, key=lambda key: float(contributions[key].get("damage", 0) or 0))
        contributions.pop(weakest, None)
    entry = contributions.setdefault(player_id, {"damage": 0.0})
    entry["damage"] = min(max_hp, float(entry.get("damage", 0) or 0) + dealt)
    entry["last_hit"] = now
    entry["region"] = str(mob.get("region", "camp"))


def _eligible_mob_contributors(killer: dict[str, Any], mob: dict[str, Any], now: float
                                ) -> dict[str, tuple[dict[str, Any], float]]:
    """Return the killer plus online players with 5% recent mob damage."""
    max_hp = max(0.0, float(mob.get("max_hp", 0) or 0))
    required = max(1.0, max_hp * MOB_CONTRIBUTION_MIN_FRACTION)
    region_id = str(mob.get("region", "camp"))
    contributions = mob.get("_contributors") if isinstance(mob.get("_contributors"), dict) else {}
    recipients: dict[str, tuple[dict[str, Any], float]] = {}
    for player_id, entry in contributions.items():
        if not isinstance(entry, dict) or str(entry.get("region", "")) != region_id:
            continue
        try:
            damage = min(max_hp, max(0.0, float(entry.get("damage", 0) or 0)))
            age = float(now) - float(entry.get("last_hit", 0) or 0)
        except (TypeError, ValueError):
            continue
        if damage < required or age < 0 or age > MOB_CONTRIBUTION_WINDOW:
            continue
        contributor = killer if str(killer.get("id")) == str(player_id) else players.get(str(player_id))
        if contributor is not None:
            recipients[str(player_id)] = (contributor, damage)
    killer_id = str(killer.get("id") or "")
    if killer_id and killer_id not in recipients:
        killer_entry = contributions.get(killer_id, {}) if isinstance(contributions, dict) else {}
        try:
            killer_damage = max(1.0, float(killer_entry.get("damage", 0) or 0))
        except (AttributeError, TypeError, ValueError):
            killer_damage = 1.0
        recipients[killer_id] = (killer, killer_damage)
    return recipients


def _split_kill_reward(total: int, weights: dict[str, float]) -> dict[str, int]:
    """Split an integer reward pool proportionally, with exact total conservation."""
    pool = max(0, int(total))
    weight_total = sum(max(0.0, float(weight)) for weight in weights.values())
    if not weights or weight_total <= 0:
        return {}
    exact = {key: pool * max(0.0, float(weight)) / weight_total for key, weight in weights.items()}
    shares = {key: math.floor(value) for key, value in exact.items()}
    remainder = pool - sum(shares.values())
    order = sorted(weights, key=lambda key: (-(exact[key] - shares[key]), key))
    for key in order[:remainder]:
        shares[key] += 1
    return shares


def award_drop(p: dict[str, Any], mob: dict[str, Any], now: float | None = None) -> None:
    """Award one kill once: shared credit/rewards, with personal loot for the finisher.

    Contributors must deal at least 5% of max HP within 120 seconds. XP and gold
    are each split by actual contribution from one pool, capped at the largest
    solo award any eligible contributor would have received. Guaranteed and
    random item drops stay with the final hitter; herald seals are progression
    currency, so every eligible contributor gets one.
    """
    if mob.get("_kill_rewarded"):
        return
    mob["_kill_rewarded"] = True
    now = time.monotonic() if now is None else float(now)
    kind = mob["kind"]
    region_id = str(mob.get("region", p.get("region", "camp")))
    recipients = _eligible_mob_contributors(p, mob, now)
    weights = {player_id: damage for player_id, (_, damage) in recipients.items()}
    newly_defeated: list[dict[str, Any]] = []
    discoveries: list[str] = []

    for member, _damage in recipients.values():
        collection = sanitize_kills(member.get("bestiary_kills"), MONSTERS, member.get("bosses_defeated"))
        if not collection.get(kind, 0):
            discoveries.append(str(member["id"]))
        collection[kind] = min(MAX_BESTIARY_KILLS, collection.get(kind, 0) + 1)
        member["bestiary_kills"] = collection
        record_region_progress(member, kind, 1, kill=True, region_id=region_id)
        member["kills"] = int(member.get("kills", 0) or 0) + 1
        if member.get("quest_active"):
            quest_kills = member.setdefault("quest_kills", {})
            quest_kills[kind] = int(quest_kills.get(kind, 0) or 0) + 1
        if mob.get("mini_boss"):
            inventory = member.setdefault("inventory", {})
            inventory["champion_seal"] = max(0, int(inventory.get("champion_seal", 0) or 0)) + 1
            stage = max(0, min(len(HERALD_QUESTS), int(member.get("herald_story_stage", 0) or 0)))
            if (member.get("herald_story_active") and stage < len(HERALD_QUESTS)
                    and kind == HERALD_QUESTS[stage]["mob"]):
                member["herald_story_kills"] = min(1, max(0, int(member.get("herald_story_kills", 0) or 0)) + 1)
            broadcast({"type": "notice", "target": member["id"],
                       "text": f"Победа над {MONSTERS[kind]['name']}: получена Печать вестника.",
                       "item": "champion_seal"})
        if mob.get("boss"):
            defeated = member.setdefault("bosses_defeated", [])
            if kind not in defeated:
                defeated.append(kind)
                reconcile_talent_points(member)
                newly_defeated.append(member)
            if kind == MAIN_BOSS_KIND:
                member["world_travel_unlocked"] = True
                for rid in REGIONS:
                    if rid not in member.setdefault("visited_regions", []):
                        member["visited_regions"].append(rid)

    spec = MONSTERS[kind]
    broadcast({"type": "mob_defeated", "region": region_id, "mob": mob["id"],
               "kind": kind, "name": spec["name"], "level": mob["level"],
               "x": mob["x"], "y": mob["y"], "boss": bool(mob.get("boss")),
               "mini_boss": bool(mob.get("mini_boss")), "color": spec["color"], "size": spec["size"],
               "participants": list(recipients), "discoveries": discoveries})

    if mob.get("boss") and newly_defeated:
        names = ", ".join(member["name"] for member in newly_defeated)
        broadcast({"type": "notice", "region": region_id,
                   "text": f"{names} одолели {MONSTERS[kind]['name']}! (+2 очка навыков каждому)"})
    if mob.get("boss") and kind == MAIN_BOSS_KIND and newly_defeated:
        broadcast({"type": "notice",
                   "text": "✦ Хранитель Первозданного сада повержен! Участникам боя открыто свободное перемещение между мирами в Атласе (M)!"})

    base_xp = MONSTERS[kind]["xp"] + max(0, mob["level"] - MONSTERS[kind]["zone"]) * 7
    base_gold = random.randint(4, 11) + mob["level"]
    xp_nominal: dict[str, int] = {}
    gold_nominal: dict[str, int] = {}
    for player_id, (member, _damage) in recipients.items():
        eq = equipment_bonuses(member, now)
        insight = insight_level(member)
        xp_nominal[player_id] = int(round(base_xp * (1 + 0.04 * insight + eq["xp_pct"])))
        gold_nominal[player_id] = int(round(base_gold * (1 + 0.03 * insight + eq["gold_pct"])))
    xp_awards = _split_kill_reward(max(xp_nominal.values(), default=0), weights)
    gold_awards = _split_kill_reward(max(gold_nominal.values(), default=0), weights)
    for player_id, (member, _damage) in recipients.items():
        add_xp(member, xp_awards.get(player_id, 0))
        member["gold"] = int(member.get("gold", 0) or 0) + gold_awards.get(player_id, 0)

    # Item and material drops remain personal to the final hitter.
    inv = p["inventory"]
    for _rk in ("essence", "rune_dust", "mithril"):
        inv.setdefault(_rk, 0)
    if kind == "slime":
        inv["slime"] += 1
        if random.random() < .45: inv["herb"] += 1
        if loot_chance(p, .06): grant_accessory(p, "copper_band")
    elif kind == "wolf":
        inv["hide"] += random.randint(1, 2)
        if loot_chance(p, .12): grant_gear(p, random.choice(["wolf_cloak", "moss_guard", "scout_tunic"]))
        if loot_chance(p, .03): grant_weapon(p, random.choice(["moonblade", "twinblades"]))
        if loot_chance(p, .08): grant_accessory(p, random.choice(["wolf_tooth_amulet", "emerald_ring"]))
    elif kind == "boar":
        inv["hide"] += 2; inv["ore"] += 1
        if loot_chance(p, .07): grant_accessory(p, "bog_amber_torc")
    elif kind == "wisp":
        inv["crystal"] += random.randint(1, 2); inv["herb"] += 1
        if random.random() < .40: inv["essence"] += 1
        if loot_chance(p, .08): grant_accessory(p, random.choice(["moon_dew_pendant", "sapphire_mana_ring"]))
    elif kind == "stone":
        inv["ore"] += random.randint(2, 4)
        if random.random() < .35: inv["rune_dust"] += 1
        if loot_chance(p, .18): grant_gear(p, random.choice(["marsh_armor", "moonweave", "iron_cuirass"]))
        if loot_chance(p, .04): grant_weapon(p, random.choice(["moonblade", "starfall_bow", "hunter_crossbow"]))
        if loot_chance(p, .07): grant_accessory(p, "cross_necklace")
    elif kind == "ashling":
        inv["crystal"] += random.randint(1, 2); inv["ore"] += 1
        inv["shard"] += 1
        if random.random() < .45: inv["rune_dust"] += 1
        if loot_chance(p, .07): grant_accessory(p, "ruby_fang_ring")
    elif kind == "ashguard":
        inv["crystal"] += 3; inv["ore"] += 3; inv["shard"] += random.randint(2, 3); inv["rune_dust"] += 1
        if loot_chance(p, .35): grant_gear(p, random.choice(["ash_plate", "colossus_core", "runic_vestments"]))
        if loot_chance(p, .09): grant_weapon(p, random.choice(["ember_greatsword", "starfall_bow", "thunder_fists", "runic_claymore"]))
        if loot_chance(p, .11): grant_accessory(p, random.choice(["ember_signet", "pyre_talisman", "feral_claws_art"]))
    elif kind == "colossus":
        inv["crystal"] += 12; inv["ore"] += 10; inv["shard"] += 10; inv["rune_dust"] += 4; inv["mithril"] += 2
        grant_gear(p, "colossus_core")
        grant_weapon(p, "ember_greatsword")
        grant_accessory(p, random.choice(["titan_gauntlet", "ember_signet"]))
    elif kind == "frost_wyrm":
        inv["crystal"] += 4; inv["shard"] += random.randint(2, 4); inv["essence"] += 1
        if loot_chance(p, .14): grant_gear(p, random.choice(["glacier_mantle", "hunter_brigandine"]))
        if loot_chance(p, .06): grant_weapon(p, random.choice(["frostfang", "frost_spear", "frost_crown_staff"]))
        if loot_chance(p, .10): grant_accessory(p, random.choice(["frost_band", "glacier_heart_amulet", "mana_flower", "magic_quiver"]))
    elif kind == "blueflame_siren":
        inv["crystal"] += 8; inv["essence"] += 2; inv["shard"] += 3
        grant_accessory(p, "glacier_heart_amulet")
        if loot_chance(p, .16): grant_gear(p, "glacier_mantle")
        if loot_chance(p, .10): grant_weapon(p, "frost_crown_staff")
    elif kind == "rift_knight":
        inv["crystal"] += 6; inv["shard"] += random.randint(3, 5); inv["mithril"] += 1; inv["rune_dust"] += 1
        if loot_chance(p, .20): grant_gear(p, random.choice(["rift_plate", "shadow_garb", "stormweaver_coat"]))
        if loot_chance(p, .08): grant_weapon(p, random.choice(["void_edge", "katana", "storm_bow", "storm_scepter"]))
        if loot_chance(p, .12): grant_accessory(p, random.choice(["void_signet", "storm_mirror", "greedy_coin"]))
    elif kind == "echo_dragon":
        inv["crystal"] += 30; inv["shard"] += 24; inv["mithril"] += 6; inv["essence"] += 5; inv["rune_dust"] += 5
        grant_gear(p, "rift_plate")
        grant_weapon(p, "void_edge")
        grant_accessory(p, random.choice(["dragon_fang_necklace", "prism_core"]))
    elif kind == "void_wraith":
        inv["crystal"] += random.randint(1, 3); inv["shard"] += random.randint(2, 5); inv["essence"] += 1
        if loot_chance(p, .09): grant_weapon(p, random.choice(["stormbrand", "shadow_repeater", "blood_tome"]))
        if loot_chance(p, .10): grant_accessory(p, random.choice(["astral_compass_amulet", "shadow_cloak_art"]))
    elif kind == "astral_titan":
        inv["crystal"] += 28; inv["shard"] += 32; inv["mithril"] += 8; inv["essence"] += 6; inv["rune_dust"] += 6
        grant_gear(p, "obsidian_shell"); grant_weapon(p, "obsidian_axe")
        grant_accessory(p, random.choice(["chrono_hourglass", "celestial_band"]))
    elif kind == "obsidian_sentinel":
        inv["ore"] += random.randint(3, 6); inv["crystal"] += random.randint(2, 4); inv["shard"] += random.randint(1, 3); inv["mithril"] += random.randint(1, 2)
        if loot_chance(p, .15): grant_gear(p, random.choice(["obsidian_shell", "crimson_plate", "dragonscale_mail"]))
        if loot_chance(p, .10): grant_weapon(p, random.choice(["obsidian_axe", "blood_reaper", "dragonbone_bow"]))
        if loot_chance(p, .12): grant_accessory(p, random.choice(["obsidian_bastion_ring", "reaper_choker", "blood_chalice"]))
    elif kind == "glass_inquisitor":
        inv["ore"] += 6; inv["shard"] += 4; inv["mithril"] += 2; inv["rune_dust"] += 1
        grant_accessory(p, "obsidian_bastion_ring")
        if loot_chance(p, .16): grant_gear(p, "obsidian_shell")
        if loot_chance(p, .10): grant_weapon(p, "obsidian_axe")
    elif kind == "starseer":
        inv["crystal"] += random.randint(4, 7); inv["shard"] += random.randint(3, 6); inv["essence"] += random.randint(1, 2); inv["rune_dust"] += 1
        if loot_chance(p, .16): grant_gear(p, random.choice(["starseer_robe", "archmage_regalia", "phantom_shroud"]))
        if loot_chance(p, .09): grant_weapon(p, random.choice(["sunfall_bow", "cosmos_staff", "eclipse_katana"]))
        if loot_chance(p, .12): grant_accessory(p, random.choice(["celestial_band", "prism_core", "chrono_hourglass"]))
    elif kind == "ancient_warden":
        inv["herb"] += 8; inv["crystal"] += 18; inv["shard"] += 20; inv["mithril"] += 10; inv["essence"] += 8; inv["rune_dust"] += 8
        grant_gear(p, "elder_mantle"); grant_weapon(p, "elder_staff")
        grant_accessory(p, random.choice(["eden_seed_amulet", "ankh_shield"]))
    broadcast({"type": "notice", "target": p["id"], "text": f"Победа над {MONSTERS[kind]['name']}: добыча собрана."})


def register_combat_hit(p: dict[str, Any], now: float) -> tuple[int, float]:
    """Advance combat streak and return (streak_count, streak_multiplier)."""
    if float(p.get("streak_until", 0) or 0) > now:
        streak = min(20, int(p.get("combat_streak", 0) or 0) + 1)
    else:
        streak = 1
    p["combat_streak"] = streak
    p["streak_until"] = now + 5.0
    return streak, 1.0 + min(0.25, (streak - 1) * 0.015)


def advance_weapon_combo(p: dict[str, Any], now: float) -> tuple[int, bool, float]:
    """Advance 3-step weapon combo chain; returns (step, is_finisher, combo_mult)."""
    if float(p.get("combo_until", 0) or 0) > now:
        step = int(p.get("combo_step", 0) or 0) + 1
        if step > 3:
            step = 1
    else:
        step = 1
    p["combo_step"] = step
    p["combo_until"] = now + 3.4
    finisher = step == 3
    mult = 1.30 if step == 3 else (1.12 if step == 2 else 1.0)
    return step, finisher, mult


def consume_counter_buff(p: dict[str, Any], now: float) -> tuple[bool, float]:
    """Consume Perfect Dodge riposte window if active (+40% damage)."""
    if float(p.get("counter_until", 0) or 0) > now:
        p["counter_until"] = 0.0
        return True, 1.40
    return False, 1.0


def build_mob_stagger(mob: dict[str, Any], amount: float, now: float) -> bool:
    """Accumulate poise damage; when reaching 100, stagger the target and interrupt telegraphs."""
    if amount <= 0 or mob["hp"] <= 0:
        return False
    if float(mob.get("staggered_until", 0) or 0) > now:
        return False
    resist = 0.48 if mob.get("boss") else 1.0
    mob["stagger"] = float(mob.get("stagger", 0.0) or 0.0) + amount * resist
    if mob["stagger"] >= 100.0:
        mob["stagger"] = 0.0
        mob["staggered_until"] = now + 3.2
        mob["stun_until"] = max(float(mob.get("stun_until", 0) or 0), now + (1.3 if mob.get("boss") else 1.8))
        mob["telegraph_until"] = 0.0
        broadcast({"type": "combat_fx", "region": mob["region"], "kind": "stagger",
                   "mob": mob["id"], "x": round(mob["x"], 1), "y": round(mob["y"], 1),
                   "text": "ПРОБИТИЕ!"})
        return True
    return False


def evaluate_combat_reaction(p: dict[str, Any], mob: dict[str, Any], element: str,
                             heavy: bool, now: float) -> tuple[float, str]:
    """Elemental and tactical status synergies on enemies."""
    mult = 1.0
    tags: list[str] = []
    if float(mob.get("staggered_until", 0) or 0) > now:
        mult *= 1.25
    if float(mob.get("sunder_until", 0) or 0) > now:
        mult *= 1.15
    burning = float(mob.get("burn_until", 0) or 0) > now
    slowed = float(mob.get("slow_until", 0) or 0) > now
    stunned = float(mob.get("stun_until", 0) or 0) > now
    poisoned = float(mob.get("poison_until", 0) or 0) > now
    elem = element.lower() if element else ""
    if (slowed or stunned) and (heavy or elem in ("lightning", "молния")):
        mult *= 1.26
        mob["slow_until"] = 0.0
        tags.append("РАСКОЛ")
    elif burning and elem in ("lightning", "молния", "arcane", "аркана", "всплеск"):
        mult *= 1.24
        tags.append("ПЕРЕГРУЗКА")
    elif burning and elem in ("ice", "лёд"):
        mult *= 1.22
        mob["burn_until"] = 0.0
        tags.append("ТАЯНИЕ")
    elif slowed and elem in ("fire", "огонь", "звёзды"):
        mult *= 1.22
        mob["slow_until"] = 0.0
        tags.append("ПАРОВОЙ ВЗРЫВ")
    elif poisoned and elem in ("fire", "огонь"):
        mult *= 1.24
        mob["poison_until"] = 0.0
        tags.append("ДЕТОНАЦИЯ")
    if heavy and mob["max_hp"] > 0 and mob["hp"] / mob["max_hp"] <= 0.25:
        mult *= 1.18
        if not tags:
            tags.append("КАЗНЬ")
    tag = tags[0] if tags else ""
    if tag:
        eq_react = equipment_bonuses(p, now)["reaction_pct"]
        if eq_react > 0:
            mult *= 1.0 + eq_react
        broadcast({"type": "combat_fx", "region": mob["region"], "kind": "reaction",
                   "mob": mob["id"], "x": round(mob["x"], 1), "y": round(mob["y"], 1),
                   "text": f"{tag}!"})
    return mult, tag


def attack_release(p: dict[str, Any], now: float, ax: float, ay: float) -> None:
    attack = p.get("attack")
    if not attack:
        return
    if float(p.get("stun_until", 0) or 0) > now:
        p["attack"] = None
        return
    weapon_id = attack["weapon"]
    spec = weapon_spec_for(p, weapon_id)
    eq = equipment_bonuses(p, now)
    eff_charge_time = max(0.16, float(spec["charge"]) / max(0.45, 1.0 + eq["attack_speed_pct"]))
    elapsed = now - attack["started"]
    charge = min(1.0, max(0.0, elapsed / eff_charge_time))
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
    if spec["kind"] == "bow" and p["inventory"]["arrows"] <= 0:
        broadcast({"type": "notice", "target": p["id"], "text": "Колчан пуст. Стрелы можно изготовить из дерева и руды."})
        return
    cost = spec["stamina"] * (.50 + .35 * charge if spec["kind"] == "staff" else .62 + .38 * charge) * (1.0 - eq["stamina_cost_pct"])
    if p["stamina"] < cost:
        broadcast({"type": "notice", "target": p["id"], "text": "Слишком мало выносливости — отступи на мгновение."})
        return
    p["stamina"] -= cost
    p["last_combat"] = now
    combo_step, finisher, combo_mult = advance_weapon_combo(p, now)
    countered, counter_mult = consume_counter_buff(p, now)
    power_bonus = (p["stats"]["might"] - 1) * 2.2
    weapon_upgrade = item_upgrade_level(p, "weapon", weapon_id)
    physical_upgrade = 0 if spec["kind"] == "staff" else 6 * weapon_upgrade
    base_damage = (spec["damage"] + spec["bonus"] * charge + power_bonus
                   + 8 * enchant_level(p, "weapon", weapon_id, "sharpness")
                   + physical_upgrade)
    if spec["kind"] == "melee" and has_class_perk(p, "warrior", 5):
        base_damage *= 1.10
    arch_mult = 1.0 + eq["damage_pct"] + (eq["bow_pct"] if spec["kind"] == "bow" else eq["melee_pct"] if spec["kind"] == "melee" else 0.0)
    base_damage = max(1.0, base_damage * arch_mult)
    crit_chance = player_crit_chance(p) + (0.35 if countered else 0.0) + (0.10 if finisher else 0.0)
    if countered and has_class_perk(p, "ranger", 15) and spec["kind"] == "bow":
        crit_chance = 1.0
    critical = random.random() < min(0.95, crit_chance)
    prec = max(1, int(p.get("stats", {}).get("precision", 1)))
    crit_mult = 1.75 + max(0, prec - 13) * 0.02 + eq["crit_mult_bonus"]
    damage = max(1, round(base_damage * combo_mult * counter_mult * (crit_mult if critical else 1.0)))
    w_elem = str(spec.get("element") or "")
    if spec["kind"] == "bow":
        if eq["ammo_save_pct"] <= 0 or random.random() >= eq["ammo_save_pct"]:
            p["inventory"]["arrows"] -= 1
        broadcast({"type": "weapon_action", "region": p["region"], "action": "attack", "id": p["id"],
                                        "weapon": weapon_id, "weapon_kind": spec["kind"],
                                        "x": p["x"], "y": p["y"], "aim_x": ax, "aim_y": ay,
                                        "charge": charge, "combo": combo_step, "finisher": finisher})
        charge_factor = .26 + .74 * charge
        speed_mult = 1.12 if has_class_perk(p, "ranger", 5) else 1.0
        speed = (210 + 500 * charge + (p["stats"]["agility"] - 1) * 8) * speed_mult
        arrow_range = 180 + 620 * charge
        charged_damage = max(1, round(damage * charge_factor))
        arrows.append({"region": p["region"], "x": p["x"] + ax * 18, "y": p["y"] + ay * 18,
                       "vx": ax * speed, "vy": ay * speed, "damage": charged_damage,
                       "owner": p["id"], "life": arrow_range / max(1, speed),
                       "max_distance": arrow_range, "travelled": 0.0, "kind": "arrow", "critical": critical,
                       "heavy": charge >= .65 or finisher, "combo": combo_step, "element": w_elem,
                       "reaction_tag": "КОНТРАТАКА" if countered else "",
                       "hit_ids": []})
        if charge >= .65 and has_class_perk(p, "ranger", 20):
            # Владыка Ветров: дополнительная призрачная стрела с лёгким смещением
            ca, sa = math.cos(0.06), math.sin(0.06)
            px_aim, py_aim = ax * ca - ay * sa, ax * sa + ay * ca
            arrows.append({"region": p["region"], "x": p["x"] + px_aim * 18, "y": p["y"] + py_aim * 18,
                           "vx": px_aim * speed * 1.05, "vy": py_aim * speed * 1.05,
                           "damage": max(1, round(charged_damage * 0.45)),
                           "owner": p["id"], "life": arrow_range / max(1, speed),
                           "max_distance": arrow_range, "travelled": 0.0, "kind": "ability_arrow",
                           "element": "arcane", "spell_kind": "Эхо", "pierce": 1, "hit_ids": []})
        award_mastery(p, "ranger", 5 + int(charge * 3))
        return
    if spec["kind"] == "staff":
        # Магический посох выпускает эфирный снаряд при базовой атаке и восстанавливает ману при попадании!
        staff_power = float(spec.get("spell_power", 0))
        mage_mult = (1.0 + staff_power + eq["spell_power_pct"] + eq["damage_pct"] * 0.5
                     + 0.08 * int(p.get("magic_damage_level", 0) or 0)
                     + 0.025 * (mastery_level(p, "mage") - 1)
                     + (0.12 if has_class_perk(p, "mage", 5) else 0.0))
        orb_base = (spec["damage"] + 6 * weapon_upgrade + spec["bonus"] * charge) * max(0.4, mage_mult)
        orb_damage = max(1, round(orb_base * combo_mult * counter_mult * (crit_mult if critical else 1.0)))
        orb_speed = 560.0 + 180.0 * charge
        orb_range = 340.0 + 220.0 * charge
        broadcast({"type": "weapon_action", "region": p["region"], "action": "cast", "id": p["id"],
                   "weapon": weapon_id, "weapon_kind": "staff",
                   "x": p["x"], "y": p["y"], "aim_x": ax, "aim_y": ay,
                   "charge": charge, "combo": combo_step, "finisher": finisher})
        arrows.append({
            "region": p["region"], "x": p["x"] + ax * 20, "y": p["y"] + ay * 20,
            "vx": ax * orb_speed, "vy": ay * orb_speed, "damage": orb_damage,
            "owner": p["id"], "life": orb_range / orb_speed + .06,
            "max_distance": orb_range, "travelled": 0.0, "kind": "ability_arrow",
            "element": w_elem or "arcane", "spell_kind": "Аркана",
            "pierce": 2 if (charge >= .75 or finisher) else 1, "hit_ids": [],
            "mana_on_hit": round(5 + 6 * charge + (4 if finisher else 0)),
            "splash_radius": 58.0 if (charge >= .75 or finisher) else 0.0,
            "critical": critical,
        })
        award_mastery(p, "mage", 4 + int(charge * 3))
        return
    broadcast({"type": "weapon_action", "region": p["region"], "action": "attack", "id": p["id"],
                                    "weapon": weapon_id, "weapon_kind": spec["kind"],
                                    "x": p["x"], "y": p["y"], "aim_x": ax, "aim_y": ay,
                                    "charge": charge, "combo": combo_step, "finisher": finisher})
    reach = (float(spec.get("range", 44)) + 12 * charge + (10 if finisher else 0)) * melee_reach_factor(p)
    arc_threshold = spec["arc"] - (0.14 if finisher else 0.0)
    hits = []
    for mob in mobs:
        if mob["hp"] <= 0 or not same_region(p, mob): continue
        dx, dy = mob["x"] - p["x"], mob["y"] - p["y"]
        dist = math.hypot(dx, dy)
        if dist <= reach and dist > .01 and (dx * ax + dy * ay) / dist >= arc_threshold:
            hits.append((dist, mob))
    hits.sort(key=lambda row: row[0])
    arch_id = spec.get("archetype") or weapon_id
    max_hits = 5 if arch_id in ("scythe", "blood_reaper", "solar_halberd") else 4 if arch_id in ("axe", "greatsword", "astral_blade", "obsidian_axe", "runic_claymore") else 3 if arch_id in ("iron_sword", "katana", "eclipse_katana", "archon_staff", "elder_staff") else 2 if arch_id in ("spear", "frost_spear", "daggers", "twinblades", "thunder_fists", "stormbrand") else 1
    if finisher:
        max_hits += 2
        p["stamina"] = min(p["max_stamina"], p["stamina"] + 6.0)
    heavy_hit = charge >= .65 or finisher
    for _, mob in hits[:max_hits]:
        _, streak_mult = register_combat_hit(p, now)
        react_mult, react_tag = evaluate_combat_reaction(p, mob, w_elem, heavy_hit, now)
        flanked = spec["kind"] == "melee" and backstab(mob, p)
        final_dmg = max(1, round(damage * streak_mult * react_mult * (1.30 if flanked else 1.0)))
        record_mob_contribution(p, mob, final_dmg, now)
        mob["hp"] -= final_dmg
        stagger_base = (14.0 + 22.0 * charge + (18.0 if finisher else 0.0)) * (1.0 + eq["stagger_pct"])
        build_mob_stagger(mob, stagger_base, now)
        if w_elem == "fire" and mob["hp"] > 0:
            mob["burn_until"] = max(float(mob.get("burn_until", 0) or 0), now + 2.8)
            mob["burn_next"] = min(float(mob.get("burn_next", now) or now), now + .15)
            mob["burn_owner"] = p["id"]
            mob["burn_damage"] = max(2.0, round(final_dmg * 0.12))
        elif w_elem == "ice" and mob["hp"] > 0:
            mob["slow_until"] = max(float(mob.get("slow_until", 0) or 0), now + 2.4)
            mob["slow_factor"] = 0.50
        if finisher:
            mob["sunder_until"] = max(float(mob.get("sunder_until", 0) or 0), now + 4.0)
        kick = (9.0 + 17.0 * charge + (10.0 if finisher else 0.0)) * (0.6 if spec["kind"] == "staff" else 1.0)
        if mob.get("boss"):
            kick *= .35
        pdx, pdy = mob["x"] - p["x"], mob["y"] - p["y"]
        pdist = max(.01, math.hypot(pdx, pdy))
        mob["x"], mob["y"] = resolve_collision(
            mob["region"], mob["x"] + pdx / pdist * kick, mob["y"] + pdy / pdist * kick,
            max(9.0, mob_hit_radius(mob) * .5))
        vampirism = enchant_level(p, "weapon", weapon_id, "vampirism")
        total_vamp = 0.06 * vampirism + eq["vampirism_pct"]
        if total_vamp > 0:
            p["hp"] = min(p["max_hp"], p["hp"] + max(1, round(final_dmg * total_vamp)))
        if combo_step >= 2 and has_class_perk(p, "warrior", 10):
            p["hp"] = min(p["max_hp"], p["hp"] + max(2, round(final_dmg * 0.04)))
        if float(p.get("bloodhunt_until", 0) or 0) > now:
            heal = round(int(ABILITY_CATALOG["bloodhunt"].get("heal_per_hit", 12)) * ability_rank_mult(ability_rank(p, "bloodhunt")))
            p["hp"] = min(p["max_hp"], p["hp"] + heal)
            broadcast({"type": "hit_player_heal", "region": p["region"], "id": p["id"], "heal": heal})
        mob["alert_until"] = now + 4
        add_damage_score(p, final_dmg, "mob", now)
        if finisher and has_class_perk(p, "warrior", 20):
            for extra in mobs:
                if extra is not mob and extra["hp"] > 0 and same_region(p, extra) and math.hypot(extra["x"] - mob["x"], extra["y"] - mob["y"]) <= 85:
                    cleave_dmg = max(1, round(final_dmg * 0.25))
                    record_mob_contribution(p, extra, cleave_dmg, now)
                    extra["hp"] -= cleave_dmg
                    if extra["hp"] <= 0:
                        extra["hp"] = 0; extra["respawn_at"] = now + random.uniform(24, 40); award_drop(p, extra, now)
                    broadcast({"type": "hit", "region": extra["region"], "mob": extra["id"], "x": extra["x"], "y": extra["y"], "damage": cleave_dmg})
        if mob["hp"] <= 0:
            mob["hp"] = 0
            mob["respawn_at"] = now + random.uniform(24, 40)
            award_drop(p, mob, now)
        broadcast({"type": "hit", "region": mob["region"], "mob": mob["id"], "x": mob["x"], "y": mob["y"],
                   "damage": final_dmg, "critical": critical, "combo": combo_step, "finisher": finisher,
                   "reaction": react_tag or ("КОНТРАТАКА" if countered else "") or ("В СПИНУ" if flanked else "")})
    # Player-versus-player combat is enabled outside the safe camp.
    if not is_safe(p):
        candidates = []
        for other in players.values():
            if other["id"] == p["id"] or other["respawn_at"] > now or not same_region(p, other):
                continue
            if is_safe(other):
                continue
            dx, dy = other["x"] - p["x"], other["y"] - p["y"]
            dist = math.hypot(dx, dy)
            if dist <= reach and dist > .01 and (dx * ax + dy * ay) / dist >= arc_threshold:
                candidates.append((dist, other))
        candidates.sort(key=lambda row: row[0])
        for _, other in candidates[:max_hits]:
            defense = player_defense(other)
            actual = max(1, round(damage * PVP_DAMAGE_FACTOR) - defense)
            other["hp"] = max(0, other["hp"] - actual)
            add_damage_score(p, actual, "pvp", now)
            broadcast({"type": "pvp_hit", "region": p["region"], "attacker": p["id"], "id": other["id"],
                                            "damage": actual, "x": other["x"], "y": other["y"], "critical": critical})
            if other["hp"] <= 0:
                other["respawn_at"] = now + 5
                other["attack"] = None
                other["gathering"] = None
                clear_player_combat_status(other)
                broadcast({"type": "notice", "target": other["id"], "text": f"Ты пал в дуэли с {p['name']}. Через несколько секунд вернёшься в лагерь."})
                broadcast({"type": "notice", "target": p["id"], "text": f"Победа в дуэли над {other['name']}!"})
    award_mastery(p, "warrior", 4 + min(6, len(hits)))


def start_attack(p: dict[str, Any], now: float, ax: float, ay: float) -> None:
    if float(p.get("stun_until", 0) or 0) > now:
        p["attack"] = None
        return
    wspec = weapon_spec_for(p, p["weapon"])
    eff_cd = max(0.08, float(wspec["cooldown"]) / max(0.45, 1.0 + equipment_bonuses(p, now)["attack_speed_pct"]))
    if p["attack"] or p["respawn_at"] > now or now - p["last_attack"] < eff_cd:
        return
    if p["stamina"] < 5: return
    if math.hypot(ax, ay) > .01:
        length = math.hypot(ax, ay)
        p["face_x"], p["face_y"] = ax / length, ay / length
    p["gathering"] = None
    p["attack"] = {"weapon": p["weapon"], "started": now,
                    "aim_x": p["face_x"], "aim_y": p["face_y"]}


def start_gather(p: dict[str, Any], now: float) -> None:
    if p["gathering"] is not None or p["attack"] or p["respawn_at"] > now or float(p.get("stun_until", 0) or 0) > now:
        return
    nearest = min((n for n in nodes if n["active"] and same_region(p, n) and math.hypot(n["x"] - p["x"], n["y"] - p["y"]) < 64),
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
    target_gear_id = "marsh_armor" if recipe == "armor" else recipe
    if recipe in WEAPONS and recipe in p["weapons"]:
        return "Такое оружие уже выковано."
    if target_gear_id in GEAR and (target_gear_id == p["gear"] or target_gear_id in p["gear_inventory"]):
        return "Такая броня уже есть в сумке."
    if recipe in ACCESSORIES and recipe in all_owned_accessories(p):
        return "Такая реликвия или украшение уже есть в коллекции."
    for resource, need in spec["cost"].items():
        inv[resource] = int(inv.get(resource, 0)) - need
    # Consumables and ammunition simply fill the backpack.
    if recipe in {"arrows", "potion"} or recipe in CONSUMABLES or recipe in {"bandage", "throwing_knife"}:
        amount = {"arrows": 8, "bandage": 3, "throwing_knife": 5}.get(recipe, 1)
        inv[recipe] = int(inv.get(recipe, 0)) + amount
        return f"Изготовлено: {spec['name']}" + (f" ×{amount}." if amount > 1 else ".")
    if recipe in WEAPONS:
        p["weapons"].append(recipe)
        return f"Сковано: {WEAPONS[recipe]['name']}. Открой инвентарь, чтобы экипировать."
    if target_gear_id in GEAR:
        grant_gear(p, target_gear_id)
        return f"Собрано: {GEAR[target_gear_id]['name']}. Открой инвентарь, чтобы надеть."
    if recipe in ACCESSORIES:
        grant_accessory(p, recipe)
        return f"Сотворена реликвия: {ACCESSORIES[recipe]['name']}. Открой инвентарь, чтобы экипировать."
    return "Рецепт не найден."


def enchant_level(p: dict[str, Any], target: str, item_id: str, enchant_id: str) -> int:
    return int(p.get("enchantments", {}).get(target, {}).get(item_id, {}).get(enchant_id, 0))


# Station positions now belong to NPCs on each individual map.
MAX_ITEM_UPGRADE = 15
FORGE_SUCCESS_CHANCES = (
    1.00, 0.94, 0.88, 0.82, 0.75,
    0.68, 0.60, 0.53, 0.47, 0.42,
    0.37, 0.32, 0.28, 0.24, 0.20,
)


def all_spells(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = dict(SPELLS)
    custom = p.get("custom_spells", {})
    if isinstance(custom, dict):
        for spell_id, spell in custom.items():
            if isinstance(spell, dict) and str(spell_id).startswith("custom_"):
                catalog[str(spell_id)] = spell
    return catalog


def spell_unlocked(p: dict[str, Any], spell_id: str,
                   catalog: dict[str, dict[str, Any]] | None = None) -> bool:
    catalog = catalog if catalog is not None else all_spells(p)
    spec = catalog.get(spell_id)
    return bool(spec and p.get("level", 1) >= spec.get("unlock_level", 1)
                and p.get("magic_mana_spent", 0) >= spec.get("unlock_spent", 0)
                and int(p.get("herald_story_stage", 0) or 0) >= int(spec.get("unlock_story_stage", 0) or 0))


def spell_upgrade_rank(p: dict[str, Any], spell_id: str) -> int:
    upgrades = p.get("spell_upgrades") if isinstance(p.get("spell_upgrades"), dict) else {}
    return max(0, min(SPELL_MAX_LEVEL - 1, int(upgrades.get(spell_id, 0) or 0)))


def spell_mastery_level(p: dict[str, Any], spell_id: str) -> int:
    uses = max(0, int(p.get("spell_uses", {}).get(spell_id, 0)))
    practice = min(5, uses // 5)
    upgraded = spell_upgrade_rank(p, spell_id)
    return min(SPELL_MAX_LEVEL, 1 + practice + upgraded)


def spell_rank_mult(level: int) -> float:
    return 1.0 + 0.07 * max(0, int(level) - 1)


def spell_effective_mana(p: dict[str, Any], spell_id: str,
                         catalog: dict[str, dict[str, Any]] | None = None,
                         eq_bonuses: dict[str, float] | None = None) -> int:
    catalog = catalog if catalog is not None else all_spells(p)
    spec = catalog.get(spell_id, {})
    base = float(spec.get("mana", 0) or 0)
    if base <= 0:
        return 0
    lvl = spell_mastery_level(p, spell_id)
    if lvl >= 6:
        base *= 0.90
    bonuses = eq_bonuses if eq_bonuses is not None else equipment_bonuses(p)
    base *= 1.0 - bonuses["mana_cost_pct"]
    return max(1, round(base))


def spell_cooldown_seconds(p: dict[str, Any], spell_id: str,
                           catalog: dict[str, dict[str, Any]] | None = None,
                           eq_bonuses: dict[str, float] | None = None) -> float:
    catalog = catalog if catalog is not None else all_spells(p)
    spec = catalog.get(spell_id, {})
    mastery = spell_mastery_level(p, spell_id)
    ins_cdr = min(0.25, max(0, int(p.get("insight_level", 0) or 0)) * 0.0065)
    bonuses = eq_bonuses if eq_bonuses is not None else equipment_bonuses(p)
    eq_cdr = bonuses["cdr_pct"]
    factor = max(0.32, (1.0 - 0.035 * (mastery - 1)) * (1.0 - ins_cdr) * (1.0 - eq_cdr))
    return round(max(1.0, float(spec.get("cooldown", 0)) * factor), 2)


SPELL_ICONS = {"fireball": "✦", "lightning": "ϟ", "heal": "✚", "thorns": "❖", "ice_lance": "❄",
               "arcane_burst": "◉", "meteor": "☄", "frost_nova": "✧", "shadow_bolt": "◈",
               "frost_ring": "❅", "root_bind": "🌿", "mind_chill": "☾"}


def spells_view(p: dict[str, Any], now: float,
                eq_bonuses: dict[str, float] | None = None,
                catalog: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Spell deck for the Mage, shaped like abilities_view() so the client can render
    every spell as a card with name, icon, key, cost, cooldown and unlock conditions."""
    allowed, reason = spells_allowed(p)
    catalog = catalog if catalog is not None else all_spells(p)
    eq_bonuses = eq_bonuses if eq_bonuses is not None else equipment_bonuses(p, now)
    cooldowns = p.get("spell_cooldowns", {}) if isinstance(p.get("spell_cooldowns"), dict) else {}
    order = list(SPELLS) + [sid for sid in catalog if sid not in SPELLS]
    result: dict[str, dict[str, Any]] = {}
    for spell_id in order:
        spec = catalog.get(spell_id)
        if not isinstance(spec, dict):
            continue
        until = float(cooldowns.get(spell_id, 0) or 0)
        is_custom = str(spell_id).startswith("custom_")
        lvl = spell_mastery_level(p, spell_id)
        mult = spell_rank_mult(lvl)
        base_val = int(spec.get("heal") or spec.get("damage") or 0)
        eff_val = round(base_val * mult)
        ctrl_note = ""
        if spec.get("stun_duration"):
            ctrl_note = f" · стан {float(spec['stun_duration']):.1f} с"
        result[spell_id] = {
            "id": spell_id, "tree": "mage", "name": spec.get("name", spell_id),
            "icon": spec.get("icon") or SPELL_ICONS.get(spell_id, "✧" if is_custom else "✦"),
            "kind": spec.get("kind", "Аркана"), "rarity": int(spec.get("rarity", 1) or 1),
            "desc": f"{spec.get('kind', 'Аркана')} · {'лечение' if spec.get('heal') else 'урон'} "
                    f"{eff_val} · область {int(spec.get('radius', 0) or 0)}{ctrl_note}",
            "cost": spell_effective_mana(p, spell_id, catalog, eq_bonuses), "base_cost": int(spec.get("mana", 0)),
            "key": spec.get("key", "") if is_custom else "",
            "unlocked": spell_unlocked(p, spell_id, catalog), "allowed": allowed, "reason": reason,
            "unlock_level": int(spec.get("unlock_level", 1) or 1),
            "unlock_spent": int(spec.get("unlock_spent", 0) or 0),
            "unlock_story_stage": int(spec.get("unlock_story_stage", 0) or 0),
            "level": lvl, "max_level": SPELL_MAX_LEVEL,
            "upgrade_rank": spell_upgrade_rank(p, spell_id),
            "power_bonus_pct": round((mult - 1.0) * 100),
            "uses": int(p.get("spell_uses", {}).get(spell_id, 0) or 0),
            "cooldown": spell_cooldown_seconds(p, spell_id, catalog, eq_bonuses),
            "remaining": max(0.0, round(until - now, 2)),
            "crafted": bool(is_custom or spec.get("crafted")),
        }
    return result


def item_upgrade_level(p: dict[str, Any], target: str, item_id: str) -> int:
    cap = MAX_ACCESSORY_UPGRADE if target == "accessory" else MAX_ITEM_UPGRADE
    return max(0, min(cap, int(p.get("upgrades", {}).get(target, {}).get(item_id, 0))))


def player_defense(p: dict[str, Any]) -> int:
    gear_id = p.get("gear", "traveler")
    base = GEAR.get(gear_id, GEAR["traveler"])["defense"]
    now = time.monotonic()
    guard = int(p.get("guard_armor", 14) or 14) if float(p.get("guard_until", 0) or 0) > now else 0
    ward = int(p.get("ward_armor", 12) or 12) if float(p.get("ward_until", 0) or 0) > now else 0
    warrior_perk = 6 if has_class_perk(p, "warrior", 5) else 0
    eq_def = round(equipment_bonuses(p, now)["defense_flat"])
    return max(0, base + 3 * item_upgrade_level(p, "gear", gear_id)
               + 2 * enchant_level(p, "gear", gear_id, "protection") + guard + ward + warrior_perk + eq_def)


def near_wizard(p: dict[str, Any]) -> bool:
    return any(near_npc(p, n["id"], "wizard") for n in region_for(p)["npcs"])


def near_forge(p: dict[str, Any]) -> bool:
    return any(near_npc(p, n["id"], "forge") for n in region_for(p)["npcs"])

async def market_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    if not near_npc(p, str(msg.get("npc_id", "")), "shop"):
        await tell(p["id"], "Подойди к местному торговцу. В каждом регионе своя лавка."); return
    action, item_id = str(msg.get("action", "")), str(msg.get("id", ""))
    inv = p["inventory"]
    if action == "buy":
        offer = REGION_SHOPS[p["region"]].get(item_id)
        if not offer:
            await tell(p["id"], "Такого товара нет в каталоге лавки."); return
        if p["gold"] < offer["price"]:
            await tell(p["id"], f"Не хватает монет: нужно {offer['price']}, у тебя {p['gold']}."); return
        kind = offer["kind"]
        if kind == "weapon" and item_id in p["weapons"]:
            await tell(p["id"], "Это оружие уже есть в сумке."); return
        if kind == "gear" and (item_id == p["gear"] or item_id in p["gear_inventory"]):
            await tell(p["id"], "Эта броня уже есть в сумке."); return
        if kind == "accessory" and item_id in all_owned_accessories(p):
            await tell(p["id"], "Эта реликвия уже есть у тебя."); return
        p["gold"] -= offer["price"]
        if kind == "potion": inv["potion"] = inv.get("potion", 0) + 1
        elif kind == "arrows": inv["arrows"] = inv.get("arrows", 0) + 8
        elif kind == "crystal": inv["crystal"] = inv.get("crystal", 0) + 3
        elif kind == "shard": inv["shard"] = inv.get("shard", 0) + 1
        elif kind == "rune_dust": inv["rune_dust"] = inv.get("rune_dust", 0) + 3
        elif kind == "essence": inv["essence"] = inv.get("essence", 0) + 2
        elif kind == "mithril": inv["mithril"] = inv.get("mithril", 0) + 2
        elif kind in CONSUMABLES: inv[kind] = inv.get(kind, 0) + 1
        elif kind == "throwing_knife": inv["throwing_knife"] = inv.get("throwing_knife", 0) + 5
        elif kind == "weapon": p["weapons"].append(item_id)
        elif kind == "gear": p["gear_inventory"].append(item_id)
        elif kind == "accessory": p.setdefault("accessories", []).append(item_id)
        update_derived(p)
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
            await sync_station_state(p)
            await tell(p["id"], f"Продано: {count} × {item_id} за {earnings} монет."); return
        if item_type == "weapon":
            w_all = all_weapons(p)
            if item_id not in w_all or item_id not in p["weapons"]:
                await tell(p["id"], "Оружие не найдено в сумке."); return
            if item_id == p["weapon"]:
                await tell(p["id"], "Сначала экипируй другое оружие."); return
            if len(p["weapons"]) <= 1:
                await tell(p["id"], "Нельзя продать последнее оружие."); return
            w_name = w_all[item_id]["name"]
            earnings = weapon_sell_price(item_id, p)
            p["weapons"].remove(item_id)
            p.get("enchantments", {}).get("weapon", {}).pop(item_id, None)
            p.get("upgrades", {}).get("weapon", {}).pop(item_id, None)
            p.get("reforges", {}).get("weapon", {}).pop(item_id, None)
            if item_id in (p.get("custom_weapons") or {}):
                p["custom_weapons"].pop(item_id, None)
            p["gold"] += earnings
            await sync_station_state(p)
            await tell(p["id"], f"Продано: {w_name} за {earnings} монет."); return
        if item_type == "gear":
            if item_id not in GEAR or item_id not in p["gear_inventory"]:
                await tell(p["id"], "Надетую броню или отсутствующий предмет продать нельзя."); return
            p["gear_inventory"].remove(item_id)
            p.get("enchantments", {}).get("gear", {}).pop(item_id, None)
            p.get("reforges", {}).get("gear", {}).pop(item_id, None)
            earnings = gear_sell_price(item_id); p["gold"] += earnings
            await sync_station_state(p)
            await tell(p["id"], f"Продано: {GEAR[item_id]['name']} за {earnings} монет."); return
        if item_type == "accessory":
            bag = p.setdefault("accessories", [])
            if item_id not in ACCESSORIES or item_id not in bag:
                await tell(p["id"], "Сначала сними реликвию в инвентаре, прежде чем продавать её."); return
            bag.remove(item_id)
            p.get("upgrades", {}).get("accessory", {}).pop(item_id, None)
            p.get("reforges", {}).get("accessory", {}).pop(item_id, None)
            earnings = accessory_sell_price(item_id); p["gold"] += earnings
            await sync_station_state(p)
            await tell(p["id"], f"Продано: {ACCESSORIES[item_id]['name']} за {earnings} монет."); return
        await tell(p["id"], "Не удалось определить предмет для продажи."); return
    if action == "enchant":
        await apply_enchantment(p, item_id, str(msg.get("item_id", "")) or None, str(msg.get("npc_id", "")))
        return
    await tell(p["id"], "Неизвестная операция лавки.")


async def apply_enchantment(p: dict[str, Any], enchant_id: str, selected_item: str | None = None, npc_id: str = "") -> None:
    if not near_npc(p, npc_id, "wizard"):
        await tell(p["id"], "Подойди к местному мастеру чар."); return
    spec = ENCHANT_CATALOG.get(enchant_id)
    if not spec:
        await tell(p["id"], "Такого зачарования нет."); return
    target = spec["target"]
    catalog = all_weapons(p) if target == "weapon" else GEAR
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
    update_derived(p)
    await sync_station_state(p)
    await tell(p["id"], f"Зачарование «{spec['name']}» {current + 1}-го уровня наложено на {catalog[item_id]['name']}. Списано: {price} монет и {crystal_cost} эхо-кристалл(а).")


def name_weapon_resonance(name: str) -> float:
    """Deterministic power resonance (+0%..+12%) from fantasy weapon naming."""
    words = [w for w in re.findall(r"[а-яёa-z]+", name.casefold()) if w]
    power_roots = ("плам", "огн", "мороз", "лед", "гром", "шторм", "буря", "звезд", "звёзд",
                   "тень", "кров", "дракон", "вечн", "пустот", "солнц", "лун", "эхо", "титан", "рассвет")
    hits = sum(1 for w in words if any(r in w for r in power_roots))
    return min(0.12, len(words) * 0.02 + hits * 0.03)


def reforge_cost_for(p: dict[str, Any], target: str, item_id: str) -> int:
    if target == "weapon":
        spec = weapon_spec_for(p, item_id)
    elif target == "gear":
        spec = GEAR.get(item_id, {})
    else:
        spec = ACCESSORIES.get(item_id, {})
    rarity = str(spec.get("rarity", "common"))
    base = {"common": 45, "uncommon": 75, "rare": 120, "epic": 185, "legendary": 270}.get(rarity, 90)
    up_lvl = item_upgrade_level(p, target, item_id)
    cost = base + up_lvl * 15
    cur_ref = item_reforge_spec(p, target, item_id)
    if cur_ref and int(cur_ref.get("tier", 0)) < 0:
        # Как у Гоблина-изобретателя в Террарии: сломанные предметы дешевле перековывать!
        cost = max(20, round(cost * 0.65))
    return cost


def roll_reforge_prefix(target: str, weapon_kind_str: str = "melee", current_prefix: str = "",
                        catalysed: bool = False, tier_floor: int | None = None) -> tuple[str, dict[str, Any]]:
    candidates: list[tuple[str, dict[str, Any], float]] = []
    for pid, spec in REFORGE_PREFIXES.items():
        if spec.get("group") != target:
            continue
        if pid == current_prefix:
            continue
        if target == "weapon" and weapon_kind_str not in spec.get("allowed", ("melee", "bow", "staff")):
            continue
        tier = int(spec.get("tier", 1))
        if catalysed and tier < 0:
            continue
        if tier_floor is not None and tier < tier_floor:
            continue
        weight = float(spec.get("weight", 8))
        if catalysed and tier >= 3:
            weight *= 1.65
        candidates.append((pid, spec, weight))
    if not candidates:
        if tier_floor is not None:
            # A seal may reroll to the same elite prefix when it is the only
            # eligible option for this weapon archetype.
            eligible = [(pid, spec) for pid, spec in REFORGE_PREFIXES.items()
                        if spec.get("group") == target and int(spec.get("tier", 1)) >= tier_floor
                        and (target != "weapon" or weapon_kind_str in spec.get("allowed", ("melee", "bow", "staff")))]
            if eligible:
                return random.choice(eligible)
        pid = "keen" if target == "weapon" else "sturdy" if target == "gear" else "hard"
        return pid, REFORGE_PREFIXES[pid]
    total_w = sum(c[2] for c in candidates)
    pick = random.uniform(0, total_w)
    acc = 0.0
    for pid, spec, w in candidates:
        acc += w
        if pick <= acc:
            return pid, spec
    return candidates[-1][0], candidates[-1][1]


FORGE_BLUEPRINTS: dict[str, tuple[dict[str, int], str, str]] = {
    # (cost, display_name, kind: weapon | gear | accessory)
    "forest_bow": ({"wood": 8, "hide": 3, "ore": 2}, "Лук следопыта", "weapon"),
    "thorn_staff": ({"wood": 6, "crystal": 5, "herb": 4}, "Посох живых терний", "weapon"),
    "twinblades": ({"ore": 5, "wood": 3, "hide": 2}, "Парные серпы ветра", "weapon"),
    "thunder_fists": ({"ore": 7, "crystal": 4, "essence": 2}, "Кастеты Громовержца", "weapon"),
    "stormbrand": ({"ore": 8, "crystal": 4, "shard": 3}, "Клинок Грозового кедра", "weapon"),
    "runic_claymore": ({"ore": 10, "mithril": 3, "rune_dust": 2}, "Рунный двуручник Титана", "weapon"),
    "katana": ({"mithril": 4, "shard": 4, "essence": 2}, "Клинок Багрового Рассвета", "weapon"),
    "storm_bow": ({"wood": 8, "mithril": 3, "essence": 3}, "Лук Грозового Шторма", "weapon"),
    "storm_scepter": ({"crystal": 6, "mithril": 3, "essence": 3}, "Скипетр Буревестника", "weapon"),
    "obsidian_axe": ({"ore": 14, "crystal": 10, "shard": 12, "hide": 4}, "Топор Чёрного стекла", "weapon"),
    "elder_staff": ({"wood": 16, "crystal": 12, "shard": 8, "herb": 6}, "Посох Первозданного корня", "weapon"),
    "solar_halberd": ({"mithril": 9, "shard": 10, "essence": 6, "rune_dust": 4}, "Глефа Солнечного Зенита", "weapon"),
    "zenith_bow": ({"wood": 12, "mithril": 8, "crystal": 12, "essence": 6}, "Лук Звёздного Горизонта", "weapon"),
    "cosmos_staff": ({"crystal": 14, "mithril": 8, "essence": 8, "rune_dust": 5}, "Посох Ткача Созвездий", "weapon"),
    # Доспехи
    "iron_cuirass": ({"ore": 9, "hide": 3}, "Кираса железного бастиона", "gear"),
    "shadow_garb": ({"hide": 6, "shard": 3, "essence": 2}, "Облачение ночного клинка", "gear"),
    "runic_vestments": ({"crystal": 5, "rune_dust": 3, "essence": 2}, "Облачение рунного мага", "gear"),
    "crimson_plate": ({"mithril": 6, "shard": 5, "essence": 3}, "Багровый латный доспех", "gear"),
    "sunforged_aegis": ({"mithril": 10, "shard": 10, "rune_dust": 6, "essence": 5}, "Эгида Солнечной Кузни", "gear"),
    # Кольца, ожерелья и артефакты
    "copper_band": ({"ore": 4, "wood": 2}, "Медное кольцо путника", "accessory"),
    "wolf_tooth_amulet": ({"hide": 3, "ore": 2}, "Ожерелье волчьего клыка", "accessory"),
    "sapphire_mana_ring": ({"ore": 4, "crystal": 4}, "Сапфировое кольцо прилива", "accessory"),
    "hawk_eye_ring": ({"ore": 5, "crystal": 3, "hide": 2}, "Перстень соколиного взора", "accessory"),
    "cross_necklace": ({"ore": 6, "crystal": 4, "shard": 2}, "Звёздный оберег стража", "accessory"),
    "hermes_boots": ({"hide": 6, "essence": 2, "crystal": 3}, "Сапоги Стремительного Ветра", "accessory"),
    "greedy_coin": ({"ore": 6, "crystal": 4, "rune_dust": 2}, "Золотой Компас Удачи", "accessory"),
    "blood_chalice": ({"mithril": 4, "essence": 4, "shard": 3}, "Алый Грааль Жизни", "accessory"),
    "titan_gauntlet": ({"mithril": 6, "shard": 6, "essence": 4}, "Рукавица Огненного Титана", "accessory"),
    "prism_core": ({"crystal": 8, "essence": 5, "rune_dust": 4}, "Призма Стихийного Резонанса", "accessory"),
    "ankh_shield": ({"mithril": 8, "shard": 8, "rune_dust": 5, "crystal": 6}, "Реликвия Несокрушимого Эха", "accessory"),
}


async def forge_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    if not near_npc(p, str(msg.get("npc_id", "")), "forge"):
        await tell(p["id"], "Подойди к кузнецу этой карты."); return
    action, recipe_id = str(msg.get("action", "")), str(msg.get("id", ""))
    inv = p["inventory"]

    if action == "craft":
        bp = FORGE_BLUEPRINTS.get(recipe_id)
        if not bp:
            await tell(p["id"], "Такого чертежа в кузнице нет."); return
        cost, display_name, bp_kind = bp
        if bp_kind == "weapon" and recipe_id in p["weapons"]:
            await tell(p["id"], f"{display_name} уже изготовлен."); return
        if bp_kind == "gear" and (recipe_id == p["gear"] or recipe_id in p["gear_inventory"]):
            await tell(p["id"], f"{display_name} уже есть в коллекции."); return
        if bp_kind == "accessory" and recipe_id in all_owned_accessories(p):
            await tell(p["id"], f"{display_name} уже сотворён."); return
        if any(inv.get(k, 0) < v for k, v in cost.items()):
            await tell(p["id"], "Не хватает материалов для изготовления."); return
        for key, value in cost.items():
            inv[key] = inv.get(key, 0) - value
        if bp_kind == "weapon":
            p["weapons"].append(recipe_id)
        elif bp_kind == "gear":
            p["gear_inventory"].append(recipe_id)
        elif bp_kind == "accessory":
            p.setdefault("accessories", []).append(recipe_id)
        await sync_station_state(p)
        await tell(p["id"], f"{display_name} изготовлен. Материалы списаны, предмет добавлен в рюкзак.")
        return

    if action == "craft_custom_weapon":
        name = " ".join(str(msg.get("name", "")).strip().split())[:28]
        archetype_id = str(msg.get("archetype", "sword"))
        core_id = str(msg.get("core", "physical"))
        try:
            tier = int(msg.get("tier", 1))
        except (TypeError, ValueError):
            tier = 1
        if len(name) < 3:
            await tell(p["id"], "Дай своему оружию имя от 3 до 28 символов."); return
        arch = CUSTOM_WEAPON_ARCHETYPES.get(archetype_id)
        core = CUSTOM_WEAPON_CORES.get(core_id)
        tier_spec = CUSTOM_WEAPON_TIERS.get(tier)
        if not arch or not core or not tier_spec:
            await tell(p["id"], "Неверные параметры чертежа собственного оружия."); return
        customs = p.setdefault("custom_weapons", {})
        if len(customs) >= 24:
            await tell(p["id"], "Арсенал авторского оружия полон (макс. 24). Продай старое у торговца."); return
        cost_map = tier_spec["cost"]
        need_gold = int(cost_map.get("gold", 0))
        if p["gold"] < need_gold:
            await tell(p["id"], f"Не хватает золота: нужно {need_gold}, сейчас {p['gold']}."); return
        for res_k, res_v in cost_map.items():
            if res_k == "gold":
                continue
            if int(inv.get(res_k, 0)) < res_v:
                await tell(p["id"], f"Не хватает материала ({res_k}): нужно {res_v}."); return
        p["gold"] -= need_gold
        for res_k, res_v in cost_map.items():
            if res_k != "gold":
                inv[res_k] = int(inv.get(res_k, 0)) - res_v
        scale = float(tier_spec["scale"]) * float(core.get("dmg_mult", 1.0)) * (1.0 + name_weapon_resonance(name))
        speed_mult = float(core.get("speed_mult", 1.0))
        wid = "cw_" + uuid.uuid4().hex[:10]
        w_entry: dict[str, Any] = {
            "id": wid, "name": name, "custom": True,
            "archetype": archetype_id, "core": core_id, "tier": tier,
            "kind": arch["kind"], "rarity": tier_spec["rarity"],
            "damage": max(10, round(arch["damage"] * scale)),
            "bonus": max(10, round(arch["bonus"] * scale)),
            "charge": round(max(0.28, arch["charge"] * speed_mult), 2),
            "cooldown": round(max(0.11, arch["cooldown"] * speed_mult), 2),
            "stamina": arch["stamina"],
            "range": arch["range"], "arc": arch["arc"],
            "color": core["color"], "element": core["element"],
            "vampirism": float(core.get("vampirism", 0.0)),
            "crit_bonus": float(core.get("crit_bonus", 0.0)),
            "spell_power": round(float(arch.get("spell_power", 0.0)) * (1.0 + (tier - 1) * 0.35) + float(core.get("spell_bonus", 0.0)), 2) if arch["kind"] == "staff" else 0.0,
            "lore": f"Выковано на заказ ({arch['label']} · {core['label']}). {core['desc']}.",
        }
        customs[wid] = w_entry
        p["weapons"].append(wid)
        # Подарочная первая перековка без негативных префиксов!
        init_pid, init_pref = roll_reforge_prefix("weapon", arch["kind"], "", catalysed=True)
        p.setdefault("reforges", {}).setdefault("weapon", {})[wid] = init_pid
        update_derived(p)
        await sync_station_state(p)
        await send_event({
            "type": "custom_weapon_created", "target": p["id"],
            "weapon_id": wid, "weapon": w_entry,
            "prefix_id": init_pid, "prefix_name": init_pref["name"], "prefix_summary": init_pref["summary"],
        })
        await tell(p["id"], f"Выковано авторское оружие: «{init_pref['name']} {name}» (урон {w_entry['damage']}+{w_entry['bonus']})!")
        return

    if action == "reforge":
        ref_target = str(msg.get("reforge_target") or "weapon")
        if ref_target not in ("weapon", "gear", "accessory"):
            await tell(p["id"], "Для перековки выбери оружие, броню или реликвию."); return
        item_id = str(msg.get("item_id") or "")
        w_all = all_weapons(p)
        if ref_target == "weapon":
            item_id = item_id or str(p.get("weapon") or "")
            if item_id not in w_all or item_id not in p.get("weapons", []):
                await tell(p["id"], "Оружие для перековки не найдено."); return
            item_name = w_all[item_id]["name"]
            w_kind = w_all[item_id]["kind"]
        elif ref_target == "gear":
            item_id = item_id or str(p.get("gear") or "")
            if item_id not in GEAR or (item_id != p.get("gear") and item_id not in p.get("gear_inventory", [])):
                await tell(p["id"], "Броня для перековки не найдена."); return
            item_name = GEAR[item_id]["name"]
            w_kind = "melee"
        else:
            if item_id not in ACCESSORIES or item_id not in all_owned_accessories(p):
                await tell(p["id"], "Выбери кольцо, ожерелье или артефакт для перековки."); return
            item_name = ACCESSORIES[item_id]["name"]
            w_kind = "melee"

        gold_cost = reforge_cost_for(p, ref_target, item_id)
        use_catalyst = bool(msg.get("use_catalyst"))
        use_seal = bool(msg.get("use_champion_seal"))
        if use_catalyst and use_seal:
            await tell(p["id"], "Выбери только один катализатор: рунную пыль или Печать вестника."); return
        if p["gold"] < gold_cost:
            await tell(p["id"], f"Для перековки нужно {gold_cost} монет (сейчас {p['gold']})."); return
        if use_catalyst and int(inv.get("rune_dust", 0)) < 1:
            await tell(p["id"], "Для рунного катализатора перековки нужна 1 рунная пыль."); return
        if use_seal and int(inv.get("champion_seal", 0)) < 1:
            await tell(p["id"], "Для высшей перековки нужна 1 Печать вестника."); return
        cur_pid = item_reforge_id(p, ref_target, item_id)
        new_pid, new_spec = roll_reforge_prefix(ref_target, w_kind, cur_pid,
                                                catalysed=use_catalyst, tier_floor=3 if use_seal else None)
        # All constraints are checked and the replacement is resolved before
        # any resource changes, so rejected operations never charge the player.
        p["gold"] -= gold_cost
        if use_catalyst:
            inv["rune_dust"] = int(inv.get("rune_dust", 0)) - 1
        if use_seal:
            inv["champion_seal"] = int(inv.get("champion_seal", 0)) - 1
        p.setdefault("reforges", {}).setdefault(ref_target, {})[item_id] = new_pid
        update_derived(p)
        await sync_station_state(p)
        tier = int(new_spec.get("tier", 1))
        await send_event({
            "type": "reforge_result", "target": p["id"],
            "reforge_target": ref_target, "item_id": item_id, "item_name": item_name,
            "prefix_id": new_pid, "prefix_name": new_spec["name"],
            "tier": tier, "summary": new_spec["summary"],
            "gold_spent": gold_cost, "gold": int(p["gold"]),
            "catalyst": "champion_seal" if use_seal else "rune_dust" if use_catalyst else "",
        })
        badge = "✦ МИФИЧЕСКАЯ УДАЧА! " if tier >= 4 else "⚠ Неудачная ковка: " if tier < 0 else "Перековка: "
        await tell(p["id"], f"{badge}{new_spec['name']} {item_name} ({new_spec['summary']}).")
        return

    target = ("weapon" if action == "upgrade_weapon"
              else "gear" if action == "upgrade_armor"
              else "accessory" if action == "upgrade_accessory" else "")
    if not target:
        await tell(p["id"], "Неизвестная операция кузницы."); return
    catalog = all_weapons(p) if target == "weapon" else GEAR if target == "gear" else ACCESSORIES
    selected_id = str(msg.get("item_id", ""))
    item_id = selected_id or (p.get("weapon") if target == "weapon" else p.get("gear") if target == "gear" else "")
    if target == "weapon":
        owned = item_id in p.get("weapons", [])
    elif target == "gear":
        owned = item_id == p.get("gear") or item_id in p.get("gear_inventory", [])
    else:
        owned = item_id in all_owned_accessories(p)
    if item_id not in catalog or not owned:
        await tell(p["id"], "Выбранный предмет не найден в инвентаре."); return
    level = item_upgrade_level(p, target, item_id)
    max_up = MAX_ACCESSORY_UPGRADE if target == "accessory" else MAX_ITEM_UPGRADE
    if level >= max_up:
        await tell(p["id"], f"Предмет уже достиг предела +{max_up}."); return
    gold_cost = (75 if target == "weapon" else 65 if target == "gear" else 85) + level * (55 if target == "weapon" else 50)
    ore_cost = 2 + level
    crystal_cost = 0 if level < 2 else 1 + level // 2
    mithril_cost = 0 if level < 10 else 1 + (level - 10) // 2
    use_catalyst = bool(msg.get("use_catalyst"))
    if p["gold"] < gold_cost or inv.get("ore", 0) < ore_cost or inv.get("crystal", 0) < crystal_cost or inv.get("mithril", 0) < mithril_cost:
        extra_m = f" и {mithril_cost} мифрила" if mithril_cost else ""
        await tell(p["id"], f"Нужно {gold_cost} монет, {ore_cost} руды, {crystal_cost} эхо-кристаллов{extra_m}."); return
    if use_catalyst and (inv.get("rune_dust", 0) < 1 or inv.get("shard", 0) < 1):
        await tell(p["id"], "Для катализатора закалки нужны 1 рунная пыль и 1 осколок разлома."); return
    chance = FORGE_SUCCESS_CHANCES[min(level, len(FORGE_SUCCESS_CHANCES) - 1)]
    if use_catalyst:
        chance = min(1.0, chance + 0.20)
        inv["rune_dust"] -= 1
        inv["shard"] -= 1
    p["gold"] -= gold_cost; inv["ore"] -= ore_cost; inv["crystal"] -= crystal_cost
    if mithril_cost:
        inv["mithril"] -= mithril_cost
    success = random.random() < chance
    if success:
        p.setdefault("upgrades", {}).setdefault(target, {})[item_id] = level + 1
        update_derived(p)
    await sync_station_state(p)
    benefit_str = (
        "+8% к характеристикам реликвии" if target == "accessory"
        else ("+6 к урону заклинаний" if catalog[item_id].get("kind") == "staff"
              else "+6 к урону стрел" if catalog[item_id].get("kind") == "bow"
              else "+6 к урону ближней атаки") if target == "weapon"
        else "+3 защиты"
    )
    await send_event({
        "type": "forge_result", "target": p["id"], "success": success,
        "upgrade_type": target, "item_id": item_id, "item_name": catalog[item_id]["name"],
        "level_before": level, "level_after": level + (1 if success else 0),
        "chance": round(chance * 100), "gold": int(p["gold"]), "inventory": dict(inv),
        "upgrades": {key: dict(value) for key, value in p.get("upgrades", {}).items()},
        "weapon": p.get("weapon"), "gear": p.get("gear"),
        "benefit": benefit_str,
        "cost": {"gold": gold_cost, "ore": ore_cost, "crystal": crystal_cost, "mithril": mithril_cost},
    })
    await tell(p["id"], (f"Успех: {catalog[item_id]['name']} улучшено до +{level + 1}." if success
                         else f"Неудача: улучшение не наложено. Списано {gold_cost} монет и {ore_cost} руды."))


async def wizard_action(p: dict[str, Any], msg: dict[str, Any]) -> None:
    if not near_npc(p, str(msg.get("npc_id", "")), "wizard"):
        await tell(p["id"], "Подойди к местному мастеру чар."); return
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
        await apply_enchantment(p, item_id, str(msg.get("item_id", "")) or None, str(msg.get("npc_id", "")))
        return
    await tell(p["id"], "Неизвестная операция волшебника.")


def spell_damage(p: dict[str, Any], mob: dict[str, Any], damage: float, now: float, *,
                 element: str = "", can_crit: bool = False, heavy: bool = False,
                 stagger_amt: float = 12.0, precomputed_critical: bool = False) -> int:
    if mob["hp"] <= 0 or not same_region(p, mob):
        return 0
    eq = equipment_bonuses(p, now)
    # «Метка орла» усиливает весь урон владельца метки по помеченной цели.
    mark = p.get("eagle_marks") if isinstance(p.get("eagle_marks"), dict) else {}
    if float(mark.get(mob["id"], 0) or 0) > now:
        mark_bonus = 0.35 if has_class_perk(p, "ranger", 10) else float(ABILITY_CATALOG.get("eagle_mark", {}).get("bonus_mult", .25))
        damage *= 1 + mark_bonus * ability_rank_mult(ability_rank(p, "eagle_mark"))
    react_mult, react_tag = evaluate_combat_reaction(p, mob, element, heavy, now)
    damage *= react_mult
    # Weapon projectiles already include their release-time critical multiplier.
    critical = precomputed_critical
    if can_crit and not critical:
        crit_chance = player_crit_chance(p) + (0.10 if has_class_perk(p, "mage", 20) else 0.0)
        if random.random() < min(0.88, crit_chance):
            critical = True
            damage *= 1.65 + eq["crit_mult_bonus"]
    dealt = max(1, round(damage))
    record_mob_contribution(p, mob, dealt, now)
    mob["hp"] -= dealt
    mob["alert_until"] = now + 4
    build_mob_stagger(mob, stagger_amt * (1.0 + eq["stagger_pct"]), now)
    if eq["vampirism_pct"] > 0:
        p["hp"] = min(p["max_hp"], p["hp"] + max(1, round(dealt * eq["vampirism_pct"])))
    add_damage_score(p, dealt, "mob", now)
    if mob["hp"] <= 0:
        mob["hp"] = 0; mob["respawn_at"] = now + random.uniform(24, 40); award_drop(p, mob, now)
    hit_payload: dict[str, Any] = {"type": "hit", "region": mob["region"], "mob": mob["id"],
                                   "x": mob["x"], "y": mob["y"], "damage": dealt}
    if critical:
        hit_payload["critical"] = True
    if react_tag:
        hit_payload["reaction"] = react_tag
    broadcast(hit_payload)
    return dealt

def _ignite(p: dict[str, Any], mob: dict[str, Any], spec: dict[str, Any], now: float, power: float) -> None:
    """Set a monster on fire from an area ability (never stacks, only refreshes)."""
    duration = float(spec.get("burn_duration", 0) or 0)
    if duration <= 0:
        return
    until = now + duration
    if until > float(mob.get("burn_until", 0) or 0):
        mob["burn_until"] = until
    mob["burn_next"] = min(float(mob.get("burn_next", now) or now), now + .05)
    mob["burn_owner"] = p["id"]
    mob["burn_damage"] = max(1, round(power * float(spec.get("burn_mult", .14) or .14)))
    mob["burn_tick"] = float(spec.get("burn_tick", .8) or .8)


def spell_visual(p: dict[str, Any], spell_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    mastery = spell_mastery_level(p, spell_id)
    kind = str(spec.get("kind", "Аркана"))
    palette = ELEMENT_FX.get(kind, ELEMENT_FX["Аркана"])
    stable = f"{spell_id}:{p.get('id', '')}:{int(p.get('spell_uses', {}).get(spell_id, 0))}"
    variant = int(hashlib.sha256(stable.encode("utf-8")).hexdigest()[:8], 16) % 1000000
    return {"mastery": mastery, "variant": variant, "palette": palette}


def spell_fx_event(p: dict[str, Any], spell_id: str, spec: dict[str, Any], x: float, y: float) -> dict[str, Any]:
    return {"type": "spell_fx", "region": p["region"], "spell": spell_id, "x": x, "y": y,
            "radius": spec.get("radius", 100), "owner": p.get("id"),
            "kind": spec.get("kind", spell_id), "name": spec.get("name", spell_id),
            "rarity": spec.get("rarity", 1), **spell_visual(p, spell_id, spec)}


def _ability_event(p: dict[str, Any], ability_id: str, target_x: float, target_y: float,
                   aim_x: float, aim_y: float, **extra: Any) -> dict[str, Any]:
    spec = ABILITY_CATALOG[ability_id]
    return {"type": "ability_cast", "region": p["region"], "id": p["id"], "ability": ability_id,
            "tree": spec["tree"], "name": spec["name"], "icon": spec.get("icon", "✦"),
            "x": round(p["x"], 1), "y": round(p["y"], 1),
            "from_x": round(p["x"], 1), "from_y": round(p["y"], 1),
            "target_x": round(target_x, 1), "target_y": round(target_y, 1),
            "aim_x": aim_x, "aim_y": aim_y,
            "radius": spec.get("radius", 0), "duration": spec.get("duration", 0), **extra}


def _damage_players_around(p: dict[str, Any], now: float, x: float, y: float, radius: float,
                           damage: float, source: str = "ability") -> None:
    if is_safe(p):
        return
    for other in list(players.values()):
        if other["id"] == p["id"] or other.get("respawn_at", 0) > now or not same_region(p, other):
            continue
        if is_safe(other):
            continue
        if math.hypot(other["x"] - x, other["y"] - y) > radius:
            continue
        actual = max(1, round(damage * .72) - player_defense(other))
        other["hp"] = max(0, other["hp"] - actual)
        broadcast({"type": "pvp_hit", "region": p["region"], "attacker": p["id"], "id": other["id"],
                                        "damage": actual, "x": other["x"], "y": other["y"], "source": source})
        if other["hp"] <= 0:
            other["respawn_at"] = now + 5
            other["attack"] = None
            other["gathering"] = None
            clear_player_combat_status(other)
            broadcast({"type": "notice", "target": other["id"], "text": f"Ты пал в бою с {p['name']}. Через несколько секунд вернёшься в лагерь."})
            broadcast({"type": "notice", "target": p["id"], "text": f"Победа над {other['name']}!"})


STAT_CAPS = {"might": 100, "vitality": 100, "agility": 100,
             "precision": 30, "fortune": 25,
             "mana_regen": 50, "magic_damage": 60, "insight": 40,
             "tenacity": 40, "ferocity": 40}
LEVEL_BASED_STATS = {"mana_regen": "mana_regen_level", "magic_damage": "magic_damage_level",
                     "insight": "insight_level", "tenacity": "tenacity_level", "ferocity": "ferocity_level"}


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
    if chosen == "mage":
        # A Mage is nothing without a staff: grant and equip one so the spell deck
        # becomes usable right after the qualification is picked.
        if "apprentice_staff" not in p["weapons"]:
            p["weapons"].append("apprentice_staff")
        p["weapon"] = "apprentice_staff"
    bonus = CLASSES[chosen].get("stat_bonus", {})
    bonus_total = sum(max(0, min(20, int(value))) for value in bonus.values())
    # The class grants a one-time bundle of development points; the signature
    # characteristics are invested automatically so the fantasy stays intact.
    # Because those automatic investments never cost the player anything, they
    # are recorded in a dedicated ledger ("class_bonus_spent") that
    # count_spent_points subtracts — otherwise every "+" click would silently
    # mint the pool back out of the class bonus and nothing would be spent.
    p["class_bonus_points"] = int(p.get("class_bonus_points", 0) or 0) + bonus_total
    p["skill_points"] = int(p.get("skill_points", 0) or 0) + bonus_total
    ledger = p.get("class_bonus_spent") if isinstance(p.get("class_bonus_spent"), dict) else {}
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
                ledger[key] = int(ledger.get(key, 0) or 0) + take
        elif key == "mana_regen":
            current = max(0, int(p.get("mana_regen_level", 0) or 0))
            take = min(amount, max(0, cap - current))
            if take:
                p["mana_regen_level"] = current + take
                applied.append(f"восстановление маны +{take}")
                spent_on_bonus += take
                ledger[key] = int(ledger.get(key, 0) or 0) + take
        elif key == "magic_damage":
            current = max(0, int(p.get("magic_damage_level", 0) or 0))
            take = min(amount, max(0, cap - current))
            if take:
                p["magic_damage_level"] = current + take
                applied.append(f"сила магии +{take * 8}%")
                spent_on_bonus += take
                ledger[key] = int(ledger.get(key, 0) or 0) + take
    p["class_bonus_spent"] = ledger
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
    if float(p.get("stun_until", 0) or 0) > now:
        await tell(p["id"], "Оглушение не даёт применить способность.")
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
    rank = ability_rank(p, ability_id)
    rank_mult = ability_rank_mult(rank)
    radius_mult = 1.15 if rank >= 5 else 1.0
    cost = ability_effective_cost(p, ability_id)
    # Магические способности расплачиваются маной, остальные — выносливостью.
    resource = str(spec.get("resource") or "stamina")
    if resource not in ("stamina", "mana"):
        resource = "stamina"
    resource_name = "маны" if resource == "mana" else "выносливости"
    if float(p.get(resource, 0)) < cost:
        await tell(p["id"], f"Мало {resource_name}: нужно {cost}, сейчас {int(p.get(resource, 0))}.")
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
    max_range = float(spec.get("range", 0) or 0) * radius_mult
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
    p[resource] = float(p.get(resource, 0)) - cost
    ab_elem = str(spec.get("spell_kind") or spec.get("element") or "")
    if ab_elem and p.get("class") == "mage":
        prev_elem = str(p.get("last_element") or "")
        if prev_elem and prev_elem != ab_elem and has_class_perk(p, "mage", 10):
            p["mana"] = min(float(p["max_mana"]), float(p["mana"]) + 6.0)
        p["last_element"] = ab_elem
    p["last_combat"] = now
    if arrow_cost:
        p["inventory"]["arrows"] = max(0, int(p["inventory"].get("arrows", 0)) - arrow_cost)
    p.setdefault("ability_uses", {})[ability_id] = int(p.get("ability_uses", {}).get(ability_id, 0) or 0) + 1
    cooldowns[ability_id] = now + ability_cooldown_seconds(p, ability_id)
    p["ability_lock_until"] = now + .18
    p["gathering"] = None
    p["attack"] = None
    p["face_x"], p["face_y"] = aim_x, aim_y
    p["last_ability"] = ability_id
    event = _ability_event(p, ability_id, tx, ty, aim_x, aim_y, rank=rank)
    _, countered_mult = consume_counter_buff(p, now)
    power = weapon_power(p) * float(spec.get("mult", 1.0)) * rank_mult * countered_mult
    hits = 0
    if ability_id == "roar":
        dur = float(spec["duration"]) + (rank - 1) * 0.4
        p["roar_until"] = max(float(p.get("roar_until", 0) or 0), now + dur)
        if rank >= 5:
            p["stamina"] = min(float(p["max_stamina"]), float(p["stamina"]) + 18.0)
        if rank >= 10:
            p["counter_until"] = max(float(p.get("counter_until", 0) or 0), now + 4.0)
        await send_event(event)
        await tell(p["id"], f"Свирепый рык (ур. {rank}): регенерация здоровья на {dur:.1f} с.")
    elif ability_id == "iron_guard":
        dur = float(spec["duration"]) + (rank - 1) * 0.35
        armor_gain = round(int(spec.get("armor", 14)) * rank_mult)
        p["guard_until"] = max(float(p.get("guard_until", 0) or 0), now + dur)
        p["guard_armor"] = armor_gain
        p["parry_until"] = now + .22
        await send_event(event)
        await tell(p["id"], f"Железная стойка (ур. {rank}): +{armor_gain} брони на {dur:.1f} с.")
    elif ability_id == "lunge":
        start_x, start_y = p["x"], p["y"]
        travel = float(spec["distance"]) * (1.0 + 0.025 * (rank - 1))
        end_x = max(25.0, min(WORLD_W - 25.0, start_x + aim_x * travel))
        end_y = max(25.0, min(WORLD_H - 25.0, start_y + aim_y * travel))
        steps = max(1, int(math.ceil(math.hypot(end_x - start_x, end_y - start_y) / 12)))
        for step in range(1, steps + 1):
            nx = start_x + (end_x - start_x) * step / steps
            ny = start_y + (end_y - start_y) * step / steps
            p["x"] = max(25.0, min(WORLD_W - 25.0, nx))
            p["y"] = max(25.0, min(WORLD_H - 25.0, ny))
        seg_x, seg_y = p["x"] - start_x, p["y"] - start_y
        seg_len = max(.01, math.hypot(seg_x, seg_y))
        for mob in list(mobs):
            if mob["hp"] <= 0 or not same_region(p, mob):
                continue
            rel_x, rel_y = mob["x"] - start_x, mob["y"] - start_y
            projection = (rel_x * seg_x + rel_y * seg_y) / seg_len
            if projection < -8 or projection > seg_len + 12:
                continue
            perp = abs(rel_x * seg_y - rel_y * seg_x) / seg_len
            if perp <= float(spec["width"]) * radius_mult + (52 if mob.get("boss") else 18):
                spell_damage(p, mob, power, now, heavy=True, stagger_amt=26.0); hits += 1
        _damage_players_around(p, now, p["x"], p["y"], 58 * radius_mult, power, "lunge")
        event["from_x"], event["from_y"] = round(start_x, 1), round(start_y, 1)
        event["x"], event["y"] = round(p["x"], 1), round(p["y"], 1)
        event["target_x"], event["target_y"] = round(p["x"], 1), round(p["y"], 1)
        await send_event(event)
    elif ability_id == "whirlwind":
        rad = float(spec["radius"]) * radius_mult
        for mob in list(mobs):
            if mob["hp"] > 0 and same_region(p, mob) and math.hypot(mob["x"] - p["x"], mob["y"] - p["y"]) <= rad:
                spell_damage(p, mob, power, now, heavy=rank >= 5, stagger_amt=22.0); hits += 1
                if rank >= 10 and mob["hp"] > 0:
                    mob["bleed_until"] = max(float(mob.get("bleed_until", 0) or 0), now + 3.2)
                    mob["bleed_next"] = min(float(mob.get("bleed_next", now) or now), now + 0.4)
                    mob["bleed_owner"] = p["id"]
                    mob["bleed_damage"] = max(2, round(power * 0.16))
        _damage_players_around(p, now, p["x"], p["y"], rad, power, "whirlwind")
        event["radius"] = rad
        await send_event(event)
    elif ability_id == "arrow_rain":
        rad = float(spec["radius"]) * radius_mult
        field = {"region": p["region"], "id": f"rain-{uuid.uuid4().hex[:8]}", "kind": "arrow_rain", "owner": p["id"],
                 "x": tx, "y": ty, "radius": rad, "damage": power,
                 "started": now, "activate_at": now + float(spec["telegraph"]),
                 "until": now + float(spec["telegraph"]) + float(spec["duration"]) + (0.6 if rank >= 10 else 0.0),
                 "next_hit": now + float(spec["telegraph"]), "tick": float(spec["tick"])}
        ground_effects.append(field)
        event["ground"] = {"id": field["id"], "kind": "arrow_rain", "x": round(tx, 1), "y": round(ty, 1),
                           "radius": field["radius"], "telegraph": field["activate_at"] - now,
                           "duration": field["until"] - field["activate_at"]}
        await send_event(event)
    elif ability_id in {"piercing_shot", "fire_arrow", "ice_arrow", "double_shot"}:
        shots = int(spec.get("shots", 1)) + (1 if ability_id == "double_shot" and rank >= 10 else 0)
        spread = float(spec.get("spread", 0))
        speed = 760.0 * (1.12 if has_class_perk(p, "ranger", 5) else 1.0)
        extra_pierce = (1 if rank >= 5 else 0) + (1 if rank >= 10 else 0)
        for index in range(shots):
            offset = (index - (shots - 1) / 2) * spread
            ca, sa = math.cos(offset), math.sin(offset)
            sx, sy = aim_x * ca - aim_y * sa, aim_x * sa + aim_y * ca
            max_distance = float(spec.get("range", 760)) * radius_mult
            arrow = {"region": p["region"], "x": p["x"] + sx * 18, "y": p["y"] + sy * 18,
                     "vx": sx * speed, "vy": sy * speed, "damage": max(1, round(power)),
                     "owner": p["id"], "life": max_distance / speed + .08,
                     "max_distance": max_distance, "travelled": 0.0, "kind": "ability_arrow",
                     "element": "fire" if ability_id == "fire_arrow" else "ice" if ability_id == "ice_arrow" else "",
                     "pierce": int(spec.get("pierce", 0)) + extra_pierce, "hit_ids": [],
                     "burn_duration": float(spec.get("burn_duration", 0) or 0),
                     "burn_tick": float(spec.get("burn_tick", .75) or .75),
                     "burn_damage": max(1, round(power * float(spec.get("burn_mult", .16) or .16))),
                     "slow_duration": float(spec.get("slow_duration", 0) or 0),
                     "slow_factor": float(spec.get("slow_factor", .45) or .45)}
            arrows.append(arrow)
        await send_event(event)
    elif ability_id == "bash":
        rad = float(spec["radius"]) * radius_mult
        stun_dur = float(spec.get("stun_duration", 1.6)) + (rank - 1) * 0.12
        for mob in list(mobs):
            if mob["hp"] <= 0 or not same_region(p, mob):
                continue
            if math.hypot(mob["x"] - p["x"], mob["y"] - p["y"]) <= rad + (40 if mob.get("boss") else 12):
                spell_damage(p, mob, power, now, heavy=True, stagger_amt=38.0); hits += 1
                if mob["hp"] > 0:
                    mob["stun_until"] = now + stun_dur
                    if rank >= 10:
                        mob["sunder_until"] = max(float(mob.get("sunder_until", 0) or 0), now + 5.0)
                    knock = float(spec.get("knockback", 70.0))
                    ddx, ddy = mob["x"] - p["x"], mob["y"] - p["y"]
                    dd = max(.01, math.hypot(ddx, ddy))
                    mob["x"] = max(25.0, min(WORLD_W - 25.0, mob["x"] + ddx / dd * knock))
                    mob["y"] = max(25.0, min(WORLD_H - 25.0, mob["y"] + ddy / dd * knock))
        _damage_players_around(p, now, p["x"], p["y"], rad, power, "bash")
        await send_event(event)
    elif ability_id == "bloodhunt":
        dur = float(spec["duration"]) + (rank - 1) * 0.4
        heal_amt = round(int(spec["heal_per_hit"]) * rank_mult)
        p["bloodhunt_until"] = max(float(p.get("bloodhunt_until", 0) or 0), now + dur)
        await send_event(event)
        await tell(p["id"], f"Жажда крови (ур. {rank}): каждый удар восстановит {heal_amt} здоровья на {dur:.1f} с.")
    elif ability_id == "seismic_slam":
        rad = float(spec["radius"]) * radius_mult
        for mob in list(mobs):
            if mob["hp"] <= 0 or not same_region(p, mob):
                continue
            if math.hypot(mob["x"] - p["x"], mob["y"] - p["y"]) <= rad + (48 if mob.get("boss") else 12):
                spell_damage(p, mob, power, now, heavy=True, stagger_amt=42.0); hits += 1
                if mob["hp"] > 0:
                    mob["slow_until"] = now + float(spec.get("slow_duration", 2.5))
                    mob["slow_factor"] = float(spec.get("slow_factor", .5))
                    mob["sunder_until"] = max(float(mob.get("sunder_until", 0) or 0), now + 4.5)
        _damage_players_around(p, now, p["x"], p["y"], rad, power, "seismic_slam")
        event["radius"] = rad
        await send_event(event)
    elif ability_id == "poison_arrow":
        spd = 760.0 * (1.12 if has_class_perk(p, "ranger", 5) else 1.0)
        rng = float(spec.get("range", 760)) * radius_mult
        arrow = {"region": p["region"], "x": p["x"] + aim_x * 18, "y": p["y"] + aim_y * 18,
                 "vx": aim_x * spd, "vy": aim_y * spd, "damage": max(1, round(power)),
                 "owner": p["id"], "life": rng / spd + .08,
                 "max_distance": rng, "travelled": 0.0, "kind": "ability_arrow",
                 "element": "poison", "pierce": int(spec.get("pierce", 0)) + (1 if rank >= 5 else 0), "hit_ids": [],
                 "poison_duration": float(spec.get("poison_duration", 4.0)) + (1.0 if rank >= 10 else 0.0),
                 "poison_tick": float(spec.get("poison_tick", .8)),
                 "poison_damage": max(1, round(power * float(spec.get("poison_mult", .14))))}
        arrows.append(arrow)
        await send_event(event)
    elif ability_id == "blackout_bolt":
        spd = 760.0 * (1.12 if has_class_perk(p, "ranger", 5) else 1.0)
        rng = float(spec.get("range", 700)) * radius_mult
        arrow = {"region": p["region"], "x": p["x"] + aim_x * 18, "y": p["y"] + aim_y * 18,
                 "vx": aim_x * spd, "vy": aim_y * spd, "damage": max(1, round(power)),
                 "owner": p["id"], "life": rng / spd + .08,
                 "max_distance": rng, "travelled": 0.0, "kind": "ability_arrow",
                 "element": "shadow", "pierce": int(spec.get("pierce", 0)) + (1 if rank >= 5 else 0), "hit_ids": [],
                 "stun_duration": float(spec.get("stun_duration", 1.8)) + (rank - 1) * 0.1}
        arrows.append(arrow)
        await send_event(event)
    elif ability_id == "eagle_mark":
        marked = None
        candidates = [m for m in mobs if m["hp"] > 0 and same_region(p, m) and math.hypot(m["x"] - tx, m["y"] - ty) <= 96 * radius_mult]
        if candidates:
            marked = min(candidates, key=lambda m: math.hypot(m["x"] - tx, m["y"] - ty))
        marks = p.setdefault("eagle_marks", {})
        if marked is not None:
            dur = float(spec["duration"]) + (rank - 1) * 0.6
            marks[marked["id"]] = now + dur
            event["target_x"], event["target_y"] = round(marked["x"], 1), round(marked["y"], 1)
            await send_event(event)
            bonus_pct = round(float(spec["bonus_mult"]) * rank_mult * 100)
            await tell(p["id"], f"Метка орла (ур. {rank}): урон по цели +{bonus_pct}% на {dur:.0f} с.")
        else:
            await send_event(event)
            await tell(p["id"], "Метку не удалось нанести: рядом с точкой прицела нет живой цели.")
    elif ability_id in {"arcane_bolt", "frost_lance"}:
        rng = float(spec.get("range", 720)) * radius_mult
        bolt = {"region": p["region"], "x": p["x"] + aim_x * 18, "y": p["y"] + aim_y * 18,
                "vx": aim_x * 820.0, "vy": aim_y * 820.0, "damage": max(1, round(power)),
                "owner": p["id"], "life": rng / 820.0 + .08,
                "max_distance": rng, "travelled": 0.0,
                "kind": "ability_arrow", "element": str(spec.get("element", "")),
                "spell_kind": str(spec.get("spell_kind", "")),
                "pierce": (2 if rank >= 10 else (1 if rank >= 5 else 0)), "hit_ids": [],
                "slow_duration": float(spec.get("slow_duration", 0) or 0),
                "slow_factor": float(spec.get("slow_factor", .45) or .45)}
        arrows.append(bolt)
        await send_event(event)
    elif ability_id in {"flame_burst", "meteor_fall"}:
        radius = float(spec["radius"]) * radius_mult
        for mob in list(mobs):
            if mob["hp"] <= 0 or not same_region(p, mob):
                continue
            if math.hypot(mob["x"] - tx, mob["y"] - ty) > radius + (34 if mob.get("boss") else 12):
                continue
            spell_damage(p, mob, power, now, element="fire", heavy=ability_id == "meteor_fall",
                         stagger_amt=34.0 if ability_id == "meteor_fall" else 18.0)
            hits += 1
            if mob["hp"] > 0:
                _ignite(p, mob, spec, now, power)
        _damage_players_around(p, now, tx, ty, radius, power, ability_id)
        event["radius"] = radius
        await send_event(event)
    elif ability_id == "chain_lightning":
        jumps = int(spec.get("jumps", 3)) + (1 if rank >= 5 else 0) + (1 if rank >= 10 else 0)
        falloff = float(spec.get("falloff", .78))
        radius = float(spec.get("radius", 155)) * radius_mult
        reachable = [m for m in mobs if m["hp"] > 0 and same_region(p, m)
                     and math.hypot(m["x"] - tx, m["y"] - ty) <= radius + (44 if m.get("boss") else 18)]
        reachable.sort(key=lambda m: math.hypot(m["x"] - tx, m["y"] - ty))
        chain = []
        current = power
        for mob in reachable[:jumps]:
            spell_damage(p, mob, current, now, element="lightning"); hits += 1
            chain.append({"x": round(mob["x"], 1), "y": round(mob["y"], 1)})
            current *= falloff
        event["chain"] = chain
        if not chain:
            await tell(p["id"], "Молнии некуда прыгать: у точки прицела нет врагов.")
        await send_event(event)
    elif ability_id == "blink":
        start_x, start_y = p["x"], p["y"]
        travel = float(spec.get("distance", 190.0)) * (1.0 + 0.03 * (rank - 1))
        end_x = max(25.0, min(WORLD_W - 25.0, start_x + aim_x * travel))
        end_y = max(25.0, min(WORLD_H - 25.0, start_y + aim_y * travel))
        p["x"], p["y"] = end_x, end_y
        if rank >= 5:
            p["dodge_until"] = max(float(p.get("dodge_until", 0) or 0), now + 0.35)
        if rank >= 10:
            for mob in list(mobs):
                if mob["hp"] > 0 and same_region(p, mob) and math.hypot(mob["x"] - end_x, mob["y"] - end_y) <= 115:
                    spell_damage(p, mob, weapon_power(p) * 0.65 * rank_mult, now, element="arcane")
        event["from_x"], event["from_y"] = round(start_x, 1), round(start_y, 1)
        event["x"], event["y"] = round(end_x, 1), round(end_y, 1)
        event["target_x"], event["target_y"] = round(end_x, 1), round(end_y, 1)
        await send_event(event)
    elif ability_id == "arcane_shield":
        dur = float(spec["duration"]) + (rank - 1) * 0.4
        armor_gain = round(int(spec.get("armor", 12)) * rank_mult)
        p["ward_until"] = max(float(p.get("ward_until", 0) or 0), now + dur)
        p["ward_armor"] = armor_gain
        await send_event(event)
        await tell(p["id"], f"Чародейский щит: +{armor_gain} брони на {dur:.0f} с.")
    elif ability_id == "mana_surge":
        before = float(p.get("mana", 0))
        restore_amt = round(float(spec.get("restore", 28)) * rank_mult)
        p["mana"] = min(float(p.get("max_mana", before)), before + restore_amt)
        gained = int(round(float(p["mana"]) - before))
        await send_event(event)
        await tell(p["id"], f"Прилив маны: +{gained} маны." if gained > 0 else "Мана уже полна — прилив не дал ничего.")
        for pid, current_player in list(players.items()):
            if current_player is p:
                broadcast(stats_updated_event(pid, p))
                break
    award_mastery(p, tree, 8 + int(spec["mastery"]) * 2)
    if hits:
        try:
            save_character(p)
        except sqlite3.Error:
            pass


async def cast_spell(p: dict[str, Any], now: float, spell_id: str, aim_x: float, aim_y: float,
                     target_x: float | None = None, target_y: float | None = None) -> None:
    allowed, reason = spells_allowed(p)
    catalog = all_spells(p)
    spec = catalog.get(spell_id)
    if not spec: await tell(p["id"], "Неизвестное заклинание."); return
    if not allowed:
        await tell(p["id"], reason)
        return
    if not spell_unlocked(p, spell_id):
        story_gate = int(spec.get("unlock_story_stage", 0) or 0)
        if story_gate > int(p.get("herald_story_stage", 0) or 0):
            await tell(p["id"], "Заклинание откроется после завершения главы «Зов трёх вестников»."); return
        await tell(p["id"], f"Заклинание откроется на уровне {spec['unlock_level']} после расхода {spec['unlock_spent']} маны. Потрачено: {int(p.get('magic_mana_spent', 0))}."); return
    if p.get("respawn_at", 0) > now: await tell(p["id"], "Нельзя колдовать во время возвращения в лагерь."); return
    if float(p.get("stun_until", 0) or 0) > now: await tell(p["id"], "Оглушение прерывает заклинание."); return
    cooldowns = p.setdefault("spell_cooldowns", {})
    if cooldowns.get(spell_id, 0) > now: await tell(p["id"], f"Заклинание перезаряжается: {cooldowns[spell_id] - now:.1f} с."); return
    mana_cost = spell_effective_mana(p, spell_id)
    if p.get("mana", 0) < mana_cost: await tell(p["id"], f"Мало маны: нужно {mana_cost}, сейчас {int(p.get('mana', 0))}."); return
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
    p["mana"] -= mana_cost
    sp_elem = str(spec.get("kind") or "")
    if sp_elem and p.get("class") == "mage":
        prev_elem = str(p.get("last_element") or "")
        if prev_elem and prev_elem != sp_elem and has_class_perk(p, "mage", 10):
            p["mana"] = min(float(p["max_mana"]), float(p["mana"]) + 6.0)
        p["last_element"] = sp_elem
    p["last_combat"] = now
    p.setdefault("spell_uses", {})[spell_id] = int(p.get("spell_uses", {}).get(spell_id, 0)) + 1
    cooldowns[spell_id] = now + spell_cooldown_seconds(p, spell_id)
    old_spent = int(p.get("magic_mana_spent", 0))
    p["magic_mana_spent"] = old_spent + int(spec["mana"])
    equipped_weapon = weapon_spec_for(p, p.get("weapon", ""))
    eq = equipment_bonuses(p, now)
    staff_power = float(equipped_weapon.get("spell_power", 0))
    staff_upgrade = (6 * item_upgrade_level(p, "weapon", p.get("weapon", ""))
                     if equipped_weapon.get("kind") == "staff" else 0)
    spell_lvl = spell_mastery_level(p, spell_id)
    rank_mult = spell_rank_mult(spell_lvl)
    _, countered_mult = consume_counter_buff(p, now)
    power = max(0.35, (1.0 + staff_power + eq["spell_power_pct"] + eq["damage_pct"] * 0.5
                       + 0.08 * int(p.get("magic_damage_level", 0))
                       + 0.025 * (mastery_level(p, "mage") - 1)
                       + (0.12 if has_class_perk(p, "mage", 5) else 0.0))) * rank_mult * countered_mult
    spell_damage_base = float(spec.get("damage", 0)) + staff_upgrade
    rad_mult = 1.15 if spell_lvl >= 10 else 1.0
    eff_radius = round(float(spec.get("radius", 100)) * rad_mult, 1)
    update_derived(p)
    if equipped_weapon.get("kind") == "staff":
        award_mastery(p, "mage", 4 + int(spec.get("mana", 0)) // 8)
    for unlocked_id, unlocked_spec in catalog.items():
        threshold = int(unlocked_spec.get("unlock_spent", 0))
        if threshold and old_spent < threshold <= p["magic_mana_spent"]:
            broadcast({"type": "notice", "target": p["id"], "text": f"Открыто заклинание «{unlocked_spec['name']}»! Требуется также уровень {unlocked_spec['unlock_level']}."})
    p["face_x"], p["face_y"] = aim_x, aim_y
    weapon_spec = equipped_weapon
    await send_event({"type": "weapon_action", "region": p["region"], "action": "cast", "id": p["id"],
                      "weapon": p.get("weapon", ""), "weapon_kind": weapon_spec.get("kind", "melee"),
                      "x": p["x"], "y": p["y"], "aim_x": aim_x, "aim_y": aim_y,
                      "spell": spell_id})
    visual = spell_visual(p, spell_id, spec)
    if spell_id in {"fireball", "ice_lance", "meteor", "shadow_bolt"} or spec.get("crafted") and spec.get("kind") in {"Огонь", "Лёд", "Тень", "Аркана"}:
        distance = max(1.0, math.hypot(tx - p["x"], ty - p["y"]))
        speed = 420 if spell_id == "fireball" else 500 if spell_id in {"ice_lance", "shadow_bolt"} else 250
        arrows.append({"region": p["region"], "x": p["x"] + aim_x * 18, "y": p["y"] + aim_y * 18,
                       "vx": (tx - p["x"]) / distance * speed, "vy": (ty - p["y"]) / distance * speed,
                       "damage": round(spell_damage_base * power), "owner": p["id"],
                       "life": distance / speed + .08, "max_distance": distance, "travelled": 0.0, "kind": "spell_projectile",
                       "spell_id": spell_id, "spell_kind": spec.get("kind", spell_id), "spell_name": spec.get("name", spell_id),
                       "spell_rarity": spec.get("rarity", 1), "spell_mastery": visual["mastery"],
                       "spell_variant": visual["variant"], "spell_palette": visual["palette"], "radius": eff_radius})
    elif spell_id == "lightning" or spec.get("chain") or spec.get("crafted") and spec.get("kind") in {"Молния", "Эхо", "Звёзды"}:
        candidates = sorted((m for m in mobs if m["hp"] > 0 and same_region(p, m) and math.hypot(m["x"] - tx, m["y"] - ty) <= eff_radius),
                           key=lambda m: math.hypot(m["x"] - tx, m["y"] - ty))
        max_jumps = int(spec.get("jumps", 5 if spell_lvl >= 8 else 4))
        falloff = max(.1, min(1.0, float(spec.get("falloff", .72))))
        for index, mob in enumerate(candidates[:max_jumps]):
            spell_damage(p, mob, spell_damage_base * power * (falloff ** index), now, element=sp_elem, can_crit=True)
            if mob["hp"] > 0 and (spec.get("stun_duration") or spec.get("slow_duration")):
                spell_control(spec, mob, now, spec.get("name", spell_id))
        await send_event(spell_fx_event(p, spell_id, spec, tx, ty))
    elif spell_id in {"frost_nova", "frost_ring"} or spec.get("crafted") and spec.get("kind") == "Лёд":
        for mob in mobs:
            if mob["hp"] > 0 and same_region(p, mob) and math.hypot(mob["x"] - p["x"], mob["y"] - p["y"]) <= eff_radius:
                spell_damage(p, mob, spell_damage_base * power, now, element="Лёд", can_crit=True)
                if mob["hp"] > 0:
                    spell_control(spec, mob, now, spec.get("name", spell_id))
                    if spell_id == "frost_nova" and not spec.get("slow_duration"):
                        mob["slow_until"] = max(float(mob.get("slow_until", 0) or 0), now + 2.8)
                        mob["slow_factor"] = 0.45
        await send_event(spell_fx_event(p, spell_id, spec, p["x"], p["y"]))
    elif spell_id == "root_bind":
        for mob in mobs:
            if mob["hp"] > 0 and same_region(p, mob) and math.hypot(mob["x"] - tx, mob["y"] - ty) <= eff_radius:
                spell_damage(p, mob, spell_damage_base * power, now, element="Терни", can_crit=True, stagger_amt=22.0)
                if mob["hp"] > 0:
                    spell_control(spec, mob, now, spec.get("name", spell_id))
        await send_event(spell_fx_event(p, spell_id, spec, tx, ty))
    elif spell_id == "mind_chill":
        for mob in mobs:
            if mob["hp"] > 0 and same_region(p, mob) and math.hypot(mob["x"] - tx, mob["y"] - ty) <= eff_radius:
                mob["sunder_until"] = max(float(mob.get("sunder_until", 0) or 0), now + 4.5)
                spell_damage(p, mob, spell_damage_base * power, now, element="Тень", can_crit=True, heavy=True, stagger_amt=28.0)
                if mob["hp"] > 0:
                    spell_control(spec, mob, now, spec.get("name", spell_id))
        await send_event(spell_fx_event(p, spell_id, spec, tx, ty))
    elif spell_id == "arcane_burst" or spec.get("crafted") and spec.get("kind") == "Всплеск":
        for mob in mobs:
            distance = math.hypot(mob["x"] - tx, mob["y"] - ty)
            if mob["hp"] > 0 and same_region(p, mob) and distance <= eff_radius:
                spell_damage(p, mob, spell_damage_base * power * max(.55, 1.0 - distance / (2 * eff_radius)), now, element="Всплеск", can_crit=True)
        await send_event(spell_fx_event(p, spell_id, spec, tx, ty))
    elif spell_id == "thorns" or spec.get("crafted") and spec.get("kind") in {"Терни", "Яд"}:
        thorn_fields.append({"region": p["region"], "x": tx, "y": ty, "radius": eff_radius, "damage": round(spell_damage_base * power),
                             "owner": p["id"], "until": now + 3.2 + (0.8 if spell_lvl >= 8 else 0.0), "next_hit": now})
        await send_event(spell_fx_event(p, spell_id, spec, tx, ty))
    elif spell_id == "heal" or spec.get("crafted") and spec.get("kind") == "Исцеление":
        healed = 0
        for ally in players.values():
            if same_region(ally, p) and math.hypot(ally["x"] - p["x"], ally["y"] - p["y"]) <= eff_radius and ally.get("respawn_at", 0) <= now:
                before = ally["hp"]; ally["hp"] = min(ally["max_hp"], ally["hp"] + round(spec["heal"] * power)); healed += ally["hp"] - before
        await send_event(spell_fx_event(p, spell_id, spec, p["x"], p["y"]))
        await tell(p["id"], f"Исцеление восстановило {healed} здоровья группе в радиусе {int(eff_radius)}."); return
    await tell(p["id"], f"Применено: {spec['name']} (ур. {spell_lvl}) · область {int(eff_radius)} ед.")

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
    allowed, reason = spells_allowed(p)
    if not allowed:
        await tell(p["id"], reason + " Сотворение чар доступно только Магу."); return
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
    """Every point above a stat's starting value was paid for with a development point.

    Class signature bonuses (``class_bonus_spent``) are granted automatically by
    ``choose_class`` and never cost the player anything, so they are subtracted
    here; otherwise the pool would silently refill itself after every click.
    """
    spent = sum(max(0, int(value or 1) - 1) for value in p.get("stats", {}).values())
    spent += max(0, int(p.get("mana_regen_level", 0) or 0))
    spent += max(0, int(p.get("magic_damage_level", 0) or 0))
    spent += max(0, int(p.get("insight_level", 0) or 0))
    spent += max(0, int(p.get("tenacity_level", 0) or 0))
    spent += max(0, int(p.get("ferocity_level", 0) or 0))
    ledger = p.get("class_bonus_spent")
    if isinstance(ledger, dict):
        for key, value in ledger.items():
            if key in LEVEL_BASED_STATS:
                current = max(0, int(p.get(LEVEL_BASED_STATS[key], 0) or 0))
            else:
                current = max(1, int(p.get("stats", {}).get(key, 1) or 1)) - 1
            spent -= min(max(0, int(value or 0)), max(0, current))
    elif isinstance(ledger, (int, float)):
        # Old single-number ledgers were recorded before any cap clamp.
        spent -= max(0, int(ledger or 0))
    return max(0, spent)


def reconcile_skill_points(p: dict[str, Any]) -> None:
    """Never lose earned points: recompute what remains after all purchases.

    Level-ups grant one point per level, quests and the class choice grant their
    own bonus points, and every raised statistic spends exactly one point. The
    pool is recomputed from this ledger (never just raised to a floor), so a
    spent point can never be minted back out of nothing on the next click.
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
    p["skill_points"] = max(0, earned - count_spent_points(p))


async def apply_stat_upgrade(pid: str, p: dict[str, Any], stat: str, count: int = 1) -> None:
    """Spend one or more development points on a characteristic — single source of truth."""
    if stat not in STAT_CAPS:
        await tell(pid, "Неизвестная характеристика для улучшения.")
        return
    try:
        steps = max(1, min(10, int(count)))
    except (TypeError, ValueError):
        steps = 1
    reconcile_skill_points(p)
    if int(p.get("skill_points", 0)) <= 0:
        await tell(pid, "Нет свободных очков развития. Получай уровни за бой и поручения.")
        return
    current_level = stat_current_level(p, stat)
    if current_level >= STAT_CAPS[stat]:
        await tell(pid, "Эта характеристика уже достигла предела.")
        return
    applied = min(steps, int(p.get("skill_points", 0)), STAT_CAPS[stat] - current_level)
    if applied <= 0:
        return
    level_based = LEVEL_BASED_STATS
    if stat in level_based:
        p[level_based[stat]] = current_level + applied
    else:
        p["stats"][stat] = current_level + applied
    p["skill_points"] = max(0, int(p.get("skill_points", 0)) - applied)
    update_derived(p, heal=stat in ("vitality", "tenacity"))
    if stat == "mana_regen":
        await tell(pid, f"Восстановление маны улучшено до уровня {p['mana_regen_level']}.")
    elif stat == "magic_damage":
        await tell(pid, f"Сила магии улучшена: +{p['magic_damage_level'] * 8}% урона от заклинаний.")
    elif stat == "insight":
        await tell(pid, f"Прозорливость повышена: опыт от побед ×{1 + 0.04 * p['insight_level']:.2f}, добыча монет +{min(120, p['insight_level'] * 3)}%.")
    elif stat == "tenacity":
        await tell(pid, f"Стойкость повышена до {p['tenacity_level']}: +{p['tenacity_level'] * 4} HP и -{p['tenacity_level'] * 0.5:.1f}% входящего урона.")
    elif stat == "ferocity":
        await tell(pid, f"Свирепость повышена до {p['ferocity_level']}: +{p['ferocity_level'] * 0.5:.1f}% урона и +{p['ferocity_level'] * 1.5:.1f}% крит. урона.")
    else:
        await tell(pid, f"Развитие улучшено: {stat_names[stat]} · теперь {p['stats'][stat]}.")
    p["stats_revision"] = int(p.get("stats_revision", 0)) + 1
    try:
        save_character(p)
    except sqlite3.Error:
        pass
    await send_event(stats_updated_event(pid, p))
    if players.get(pid) is p:
        try:
            await send_event({"type": "player_update", "target": pid,
                              "player": player_row(pid, p, time.monotonic())})
        except Exception:
            pass


def skill_gold_upgrade_cost(current_rank: int) -> tuple[int, int]:
    """Fallback Gold + Echo Crystal cost when upgrading a skill without talent points."""
    return 90 + current_rank * 55, 1 + current_rank // 3


async def apply_skill_upgrade(pid: str, p: dict[str, Any], msg: dict[str, Any]) -> None:
    """Upgrade an ability (Rank 1 -> 10) or spell (up to Level 12) using talent points or Gold + Crystals."""
    kind = str(msg.get("kind") or "ability")
    skill_id = str(msg.get("id") or msg.get("skill") or "")
    reconcile_talent_points(p)
    talent_pool = int(p.get("talent_points", 0) or 0)
    use_gold = bool(msg.get("use_gold")) or talent_pool <= 0

    if kind == "ability":
        spec = ABILITY_CATALOG.get(skill_id)
        if not spec:
            await tell(pid, "Неизвестный навык для улучшения.")
            return
        if not p.get("class") or p.get("class") != spec["tree"]:
            await tell(pid, f"Навык «{spec['name']}» принадлежит классу «{MASTERY_NAMES[spec['tree']]}».")
            return
        if not ability_unlocked(p, skill_id):
            await tell(pid, f"Сначала открой «{spec['name']}» на {spec['mastery']}-м уровне мастерства класса.")
            return
        current = ability_rank(p, skill_id)
        if current >= ABILITY_MAX_LEVEL:
            await tell(pid, f"Навык «{spec['name']}» уже достиг максимального {ABILITY_MAX_LEVEL}-го ранга!")
            return
        if not use_gold:
            p.setdefault("ability_levels", {})[skill_id] = current + 1
            reconcile_talent_points(p)
            cost_note = "1 очко навыков"
        else:
            gold_cost, crystal_cost = skill_gold_upgrade_cost(current)
            inv = p.setdefault("inventory", {})
            if int(p.get("gold", 0)) < gold_cost or int(inv.get("crystal", 0)) < crystal_cost:
                await tell(pid, f"Нужно 1 очко навыков ИЛИ {gold_cost} монет и {crystal_cost} эхо-кристалл(а).")
                return
            p["gold"] = int(p["gold"]) - gold_cost
            inv["crystal"] = int(inv.get("crystal", 0)) - crystal_cost
            p["gold_skill_upgrades"] = int(p.get("gold_skill_upgrades", 0) or 0) + 1
            p.setdefault("ability_levels", {})[skill_id] = current + 1
            reconcile_talent_points(p)
            cost_note = f"{gold_cost} монет и {crystal_cost} эхо-крист."
        new_rank = ability_rank(p, skill_id)
        milestone = ""
        if new_rank == 5:
            milestone = " ✦ Эволюция V ранга: усилена область/пробивание и снижен расход ресурса!"
        elif new_rank == 10:
            milestone = " ✦ ПРОБУЖДЕНИЕ X ранга: раскрыт высший эффект техники!"
        await tell(pid, f"Навык «{spec['name']}» улучшен до {new_rank}/{ABILITY_MAX_LEVEL} ранга ({cost_note})!{milestone}")
    elif kind == "spell":
        catalog = all_spells(p)
        spec = catalog.get(skill_id)
        if not spec:
            await tell(pid, "Неизвестное заклинание для улучшения.")
            return
        if p.get("class") != "mage":
            await tell(pid, "Улучшение заклинаний доступно классу «Маг».")
            return
        if not spell_unlocked(p, skill_id):
            await tell(pid, f"Сначала изучи «{spec['name']}» (нужен ур. {spec.get('unlock_level', 1)} и расход {spec.get('unlock_spent', 0)} маны).")
            return
        cur_total = spell_mastery_level(p, skill_id)
        if cur_total >= SPELL_MAX_LEVEL:
            await tell(pid, f"Заклинание «{spec['name']}» уже достигло высшего {SPELL_MAX_LEVEL}-го уровня!")
            return
        cur_up = spell_upgrade_rank(p, skill_id)
        if not use_gold:
            p.setdefault("spell_upgrades", {})[skill_id] = cur_up + 1
            reconcile_talent_points(p)
            cost_note = "1 очко навыков"
        else:
            gold_cost, crystal_cost = skill_gold_upgrade_cost(cur_total)
            inv = p.setdefault("inventory", {})
            if int(p.get("gold", 0)) < gold_cost or int(inv.get("crystal", 0)) < crystal_cost:
                await tell(pid, f"Нужно 1 очко навыков ИЛИ {gold_cost} монет и {crystal_cost} эхо-кристалл(а).")
                return
            p["gold"] = int(p["gold"]) - gold_cost
            inv["crystal"] = int(inv.get("crystal", 0)) - crystal_cost
            p["gold_skill_upgrades"] = int(p.get("gold_skill_upgrades", 0) or 0) + 1
            p.setdefault("spell_upgrades", {})[skill_id] = cur_up + 1
            reconcile_talent_points(p)
            cost_note = f"{gold_cost} монет и {crystal_cost} эхо-крист."
        new_lvl = spell_mastery_level(p, skill_id)
        await tell(pid, f"Заклинание «{spec['name']}» усилено до {new_lvl}/{SPELL_MAX_LEVEL} ур. ({cost_note})!")
    else:
        await tell(pid, "Неизвестный тип улучшения навыка.")
        return

    p["stats_revision"] = int(p.get("stats_revision", 0)) + 1
    try:
        save_character(p)
    except sqlite3.Error:
        pass
    await send_event(stats_updated_event(pid, p))
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
        # Movement modes: running drains stamina, sneaking is slow but quiet.
        p["sneaking"] = bool(msg.get("sneak"))
        p["running"] = bool(msg.get("run")) and length > .1 and not p["sneaking"]
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
    elif kind == "npc_quest":
        await npc_quest_action(p, msg)
    elif kind == "travel":
        await travel_action(p, msg)
    elif kind == "world_travel":
        await world_travel_action(p, msg)
    elif kind == "recall":
        await recall_action(p)
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
        w_all = all_weapons(p)
        if weapon in p["weapons"] and weapon in w_all:
            if now < float(p.get("ability_lock_until", 0) or 0):
                await tell(pid, "Дождись завершения текущей способности, затем смени оружие.")
                return
            p["weapon"] = weapon
            # Changing a weapon cancels an unfinished wind-up instead of letting it fire
            # with the old weapon's data.
            p["attack"] = None
            p["gathering"] = None
            p["ability_lock_until"] = now + .12
            update_derived(p)
            await sync_station_state(p)
            tree = action_tree(p)
            if p.get("class") and p.get("class") != tree:
                if tree == "mage":
                    await tell(pid, "Оружие экипировано, но заклинания доступны только классу «Маг».")
                else:
                    await tell(pid, f"Оружие экипировано, но способности «{MASTERY_NAMES.get(tree, tree)}» недоступны твоему классу.")
        else:
            await tell(pid, "Оружие не найдено в сумке.")
    elif kind == "quest_track":
        wanted = str(msg.get("id", ""))
        known = {q["id"] for q in quest_journal(p)}
        if wanted in known:
            p["tracked_quest"] = wanted
        elif not wanted:
            p["tracked_quest"] = ""      # снять закрепление: трекер выберет сам
        else:
            await tell(pid, "Это поручение ещё не принято — сначала поговори с Хранителем.")
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
            update_derived(p)
            await sync_station_state(p)
            await tell(pid, f"Экипировано: {GEAR[gear_id]['name']} · защита {GEAR[gear_id]['defense']}.")
        else:
            await tell(pid, "Предмет не найден в рюкзаке. Обнови инвентарь и попробуй снова.")
    elif kind == "equip_accessory":
        acc_id = str(msg.get("id", ""))
        req_slot = str(msg.get("slot", ""))
        spec = ACCESSORIES.get(acc_id)
        if not spec:
            await tell(pid, "Такая реликвия не найдена.")
        else:
            bag = p.setdefault("accessories", [])
            eq_map = equipped_accessories_map(p)
            if acc_id in eq_map.values():
                await tell(pid, f"Уже экипировано: {spec['name']}.")
            elif acc_id not in bag:
                await tell(pid, "Эта реликвия не найдена в рюкзаке.")
            else:
                slot_type = spec["slot"]
                if slot_type == "ring":
                    target_slot = "ring"
                elif slot_type == "amulet":
                    target_slot = "amulet"
                else:
                    if req_slot in ("artifact_1", "artifact_2"):
                        target_slot = req_slot
                    elif not eq_map.get("artifact_1"):
                        target_slot = "artifact_1"
                    elif not eq_map.get("artifact_2"):
                        target_slot = "artifact_2"
                    else:
                        target_slot = "artifact_1"
                bag.remove(acc_id)
                prev_id = eq_map.get(target_slot)
                if prev_id and prev_id in ACCESSORIES and prev_id not in bag:
                    bag.append(prev_id)
                eq_map[target_slot] = acc_id
                p["equipped_accessories"] = eq_map
                update_derived(p)
                await sync_station_state(p)
                await tell(pid, f"Экипировано: {spec['name']} ({spec['description']}).")
    elif kind == "unequip_accessory":
        slot = str(msg.get("slot", ""))
        eq_map = equipped_accessories_map(p)
        if slot not in ACCESSORY_SLOTS or not eq_map.get(slot):
            await tell(pid, "В этом слоте ничего не экипировано.")
        else:
            prev_id = str(eq_map[slot])
            eq_map[slot] = None
            p["equipped_accessories"] = eq_map
            bag = p.setdefault("accessories", [])
            if prev_id in ACCESSORIES and prev_id not in bag:
                bag.append(prev_id)
            update_derived(p)
            await sync_station_state(p)
            await tell(pid, f"Снято: {ACCESSORIES[prev_id]['name']}.")
    elif kind in ("use_potion", "use_consumable"):
        item_id = str(msg.get("id") or ("potion" if kind == "use_potion" else "potion"))
        used, text, effects = consumable_use(p, item_id)
        await tell(pid, text)
        if used:
            p["last_combat"] = max(float(p.get("last_combat", 0)), 0)
            await send_event({"type": "consumable_used", "region": p.get("region", "camp"),
                              "id": p["id"], "item": item_id, "effects": effects,
                              "x": round(p["x"], 1), "y": round(p["y"], 1)})
            await send_event({"type": "player_update", "target": pid,
                              "player": player_row(pid, p, time.monotonic())})
    elif kind == "sync":
        # The client asks for an authoritative copy of its own row.
        await send_event({"type": "player_update", "target": pid,
                          "player": player_row(pid, p, now)})
    elif kind == "upgrade":
        await apply_stat_upgrade(pid, p, str(msg.get("stat", "")), msg.get("count", 1))
    elif kind == "upgrade_skill":
        await apply_skill_upgrade(pid, p, msg)
    elif kind == "upgrade_http":
        # Резервный путь применения очков развития (если WebSocket-событие потерялось).
        stat = str(msg.get("stat", ""))
        await handle_message(pid, p, {"type": "upgrade", "stat": stat, "count": msg.get("count", 1)}, now)
    elif kind == "dodge":
        eq = equipment_bonuses(p, now)
        dodge_cost = max(10.0, round(24.0 * (1.0 - eq["stamina_cost_pct"])))
        if now >= p["dodge_at"] and p["stamina"] >= dodge_cost and p["respawn_at"] <= now and float(p.get("stun_until", 0) or 0) <= now:
            dx, dy = p["mx"], p["my"]
            if math.hypot(dx, dy) < .1: dx, dy = p["face_x"], p["face_y"]
            length = max(.01, math.hypot(dx, dy)); dx /= length; dy /= length
            sx, sy = p["x"], p["y"]
            p["x"], p["y"] = resolve_collision(p.get("region", "camp"),
                                               p["x"] + dx * 130, p["y"] + dy * 130, 15.0)
            cd = (.70 if has_class_perk(p, "ranger", 15) else .85) * (1.0 - eq["cdr_pct"] * 0.5)
            p["stamina"] -= dodge_cost; p["dodge_at"] = now + cd; p["dodge_until"] = now + .26 + eq["dodge_window_bonus"] * 0.5
            p["attack"] = None
            p["gathering"] = None
            threat_window = 0.45 + eq["dodge_window_bonus"]
            threat = any(
                m["hp"] > 0 and same_region(p, m)
                and m.get("stun_until", 0) <= now and m.get("staggered_until", 0) <= now
                and m.get("pending_attack")
                and 0 < float(m.get("telegraph_until", 0) or 0) - now <= threat_window
                and attack_contains(m["pending_attack"], {"x": sx, "y": sy})
                and (not attack_contains(m["pending_attack"], p) or m["telegraph_until"] <= p["dodge_until"])
                for m in mobs
            )
            if threat and float(p.get("counter_until", 0) or 0) <= now:
                p["counter_until"] = now + 3.2
                p["stamina"] = min(p["max_stamina"], p["stamina"] + 10)
                await send_event({"type": "combat_fx", "region": p["region"], "kind": "perfect_dodge",
                                  "id": p["id"], "x": round(p["x"], 1), "y": round(p["y"], 1),
                                  "text": "ИДЕАЛЬНЫЙ УКЛОН"})
            else:
                await send_event({"type": "combat_fx", "region": p["region"], "kind": "dodge",
                                  "id": p["id"], "from_x": round(sx, 1), "from_y": round(sy, 1),
                                  "x": round(p["x"], 1), "y": round(p["y"], 1)})
    elif kind == "chat":
        text = " ".join(str(msg.get("text", "")).split())[:180]
        if text and now - p["last_chat"] > .7:
            p["last_chat"] = now
            await send_event({"type": "chat", "name": p["name"], "text": text})


stat_names = {"might": "Сила", "vitality": "Живучесть", "agility": "Ловкость", "precision": "Точность", "fortune": "Удача"}
EXTRA_STAT_NAMES = {"insight": "Прозорливость", "tenacity": "Стойкость", "ferocity": "Свирепость"}
PERSIST_FIELDS = (
    "region", "visited_regions", "region_quests", "bosses_defeated", "bestiary_kills", "world_travel_unlocked",
    "x", "y", "hp", "stamina", "xp", "level", "skill_points",
    "talent_points", "bonus_talent_points", "gold_skill_upgrades", "ability_levels", "ability_uses", "spell_upgrades",
    "stats", "gold", "kills", "weapon", "weapons", "custom_weapons",
    "gear", "gear_inventory", "accessories", "equipped_accessories", "reforges",
    "inventory", "quest_stage", "quest_active", "quest_kills", "quest_gather", "quest_points",
    "herald_story_stage", "herald_story_active", "herald_story_kills",
    "class_bonus_points", "class_bonus_spent",
    "enchantments", "market_starter_grant", "magic_mana_spent", "upgrades",
    "mana_regen_level", "magic_damage_level", "insight_level", "tenacity_level", "ferocity_level",
    "spell_uses", "custom_spells",
    "class", "mastery", "ability_cooldowns", "tracked_quest",
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
            if not isinstance(data, dict):
                return {}
            saved = {key: data[key] for key in PERSIST_FIELDS if key in data}
            saved["bestiary_kills"] = sanitize_kills(data.get("bestiary_kills"), MONSTERS, data.get("bosses_defeated"))
            return saved
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
    data["bestiary_kills"] = sanitize_kills(p.get("bestiary_kills"), MONSTERS, p.get("bosses_defeated"))
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


RUN_SPEED_FACTOR = 1.55
SNEAK_SPEED_FACTOR = .52
WALK_SPEED_BASE = 178.0


def player_move_profile(p: dict[str, Any], now: float | None = None,
                        eq_bonuses: dict[str, float] | None = None) -> tuple[float, bool, bool]:
    """(speed, running, sneaking) for one player this tick.

    Running is a stamina-gated sprint, sneaking a slow crouch; both only apply
    while the player is actually holding a direction.
    """
    now = time.monotonic() if now is None else now
    if float(p.get("respawn_at", 0) or 0) > now or float(p.get("stun_until", 0) or 0) > now:
        return 0.0, False, False
    bonuses = eq_bonuses if eq_bonuses is not None else equipment_bonuses(p, now)
    speed = (WALK_SPEED_BASE + (p["stats"]["agility"] - 1) * 3.2) * (1.0 + bonuses["move_speed_pct"])
    moving = math.hypot(p.get("mx", 0.0), p.get("my", 0.0)) > .1
    running = bool(moving and p.get("running") and float(p.get("stamina", 0)) > 1.0 and not p.get("sneaking"))
    sneaking = bool(moving and p.get("sneaking"))
    if running:
        speed *= RUN_SPEED_FACTOR
    elif sneaking:
        speed *= SNEAK_SPEED_FACTOR
    if float(p.get("slow_until", 0) or 0) > now:
        speed *= max(.15, min(.95, float(p.get("slow_factor", .45) or .45)))
    return speed, running, sneaking


async def world_tick() -> None:
    last_saved = time.monotonic()
    last_snapshot = 0.0
    while True:
        now = time.monotonic()
        dt = TICK
        for pid, p in list(players.items()):
            if p["respawn_at"] and p["respawn_at"] <= now:
                p["respawn_at"] = 0.0
                clear_player_combat_status(p)
                p["hp"] = p["max_hp"]; p["stamina"] = p["max_stamina"]; p["mana"] = p["max_mana"]
                await enter_region(p, "camp", *SPAWN, reason="respawn")
                await tell(pid, "Ты вернулся в лагерь. Потеряно немного времени, но не добыча.")
            if p["respawn_at"] > now: continue
            for status_kind in ("burn", "poison"):
                pulse = consume_player_damage_over_time(p, status_kind, now)
                if not pulse:
                    continue
                result = apply_player_dot_pulse(p, pulse, now)
                if not result:
                    continue
                await send_event(result["event"])
                if result["killed"]:
                    await tell(pid, "Рана продолжала жечь. Ты пал в бою и скоро вернёшься в лагерь.")
                    break
            if p["respawn_at"] > now: continue
            eq_p = equipment_bonuses(p, now)
            speed, running, sneaking = player_move_profile(p, now, eq_p)
            # Solid scenery: the server slides the player around trunks, rocks
            # and pillars instead of letting them pass through.
            nx = max(25, min(WORLD_W - 25, p["x"] + p["mx"] * speed * dt))
            ny = max(25, min(WORLD_H - 25, p["y"] + p["my"] * speed * dt))
            p["x"], p["y"] = resolve_collision(p.get("region", "camp"), nx, ny, 15.0)
            regen = 15 + p["stats"]["agility"] * .35
            if running:
                p["stamina"] = max(0.0, p["stamina"] - 20.0 * (1.0 - eq_p["stamina_cost_pct"] * 0.6) * dt)
            else:
                p["stamina"] = min(p["max_stamina"], p["stamina"] + regen * (1.6 if sneaking else 1.0) * dt)
            p["mana"] = min(p["max_mana"], p.get("mana", 0) + (9.0 + 1.5 * p.get("mana_regen_level", 0) + eq_p["mana_regen"]) * dt)
            if eq_p["hp_regen"] > 0:
                p["hp"] = min(p["max_hp"], p["hp"] + eq_p["hp_regen"] * dt)
            if float(p.get("roar_until", 0) or 0) > now:
                p["hp"] = min(p["max_hp"], p["hp"] + 6.0 * dt)
            for site in POWER_SITES:
                if site["region"] != p.get("region", "camp"): continue
                if math.hypot(p["x"] - site["x"], p["y"] - site["y"]) <= site["radius"]:
                    regen = 4.0 if p["region"] == "camp" else 2.0
                    p["hp"] = min(p["max_hp"], p["hp"] + regen * dt)
                    p["mana"] = min(p["max_mana"], p["mana"] + regen * dt)
                    p["stamina"] = min(p["max_stamina"], p["stamina"] + regen * dt)
            if is_safe(p) and not p.get("attack") and now - float(p.get("last_combat", 0)) > COMBAT_LOCK:
                p["hp"] = min(p["max_hp"], p["hp"] + 3.0 * dt)
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
                        record_region_progress(p, node["kind"], amount)
                        if p["quest_active"]: p["quest_gather"][node["kind"]] = p["quest_gather"].get(node["kind"], 0) + amount
                        p["gathering"] = None
                        await tell(pid, f"Собрано: {amount} — {node['kind']}.")
        for node in nodes:
            if not node["active"] and node["respawn_at"] <= now: node["active"] = True
        for mob in mobs:
            if mob["hp"] <= 0:
                if mob["respawn_at"] <= now:
                    fresh = scaled_mob(mob["kind"], mob["level"], int(mob["id"].split("-")[-1]), mob["spawn_x"], mob["spawn_y"])
                    fresh["id"], fresh["region"] = mob["id"], mob["region"]
                    mob.update(fresh)
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
            if float(mob.get("bleed_until", 0) or 0) > now and float(mob.get("bleed_next", 0) or 0) <= now:
                owner = players.get(str(mob.get("bleed_owner", "")))
                mob["bleed_next"] = now + max(.35, float(mob.get("bleed_tick", .65) or .65))
                if owner and owner.get("respawn_at", 0) <= now:
                    spell_damage(owner, mob, float(mob.get("bleed_damage", 2) or 2), now)
                if mob["hp"] <= 0:
                    continue
            if float(mob.get("staggered_until", 0) or 0) <= now and float(mob.get("stagger", 0) or 0) > 0:
                mob["stagger"] = max(0.0, float(mob.get("stagger", 0) or 0) - 7.5 * dt)
            phase = boss_phase(mob)
            if phase > mob.get("phase", 1):
                mob["phase"] = phase
                mob["telegraph_until"] = 0.0
                mob["pending_attack"] = None
                mob["attack_at"] = max(mob["attack_at"], now + 1.2)
                await send_event({"type": "combat_fx", "region": mob["region"], "kind": "boss_phase",
                                  "x": mob["x"], "y": mob["y"], "text": "ПРОБУЖДЕНИЕ" if phase == 2 else "ЯРОСТЬ!"})
            slow_active = float(mob.get("slow_until", 0) or 0) > now
            mob_speed = float(mob["speed"]) * (float(mob.get("slow_factor", .45) or .45) if slow_active else 1.0)
            mob_speed *= 1.0 + .10 * (phase - 1)
            if float(mob.get("stun_until", 0) or 0) > now:
                mob["telegraph_until"] = 0.0
                mob["pending_attack"] = None
                continue
            target = min((p for p in players.values() if p["respawn_at"] <= now and
                          not is_safe(p) and same_region(p, mob)),
                         key=lambda p: math.hypot(p["x"] - mob["x"], p["y"] - mob["y"]), default=None)
            if target is None:
                mob["telegraph_until"] = 0.0
                mob["pending_attack"] = None
                if now > mob["wander_at"]:
                    mob["wander_x"], mob["wander_y"] = random.uniform(-1, 1), random.uniform(-1, 1)
                    mob["wander_at"] = now + random.uniform(1.2, 3.3)
                mx = max(45.0, min(WORLD_W - 45.0, mob["x"] + mob["wander_x"] * mob_speed * .16 * dt))
                my = max(45.0, min(WORLD_H - 45.0, mob["y"] + mob["wander_y"] * mob_speed * .16 * dt))
                if not is_safe({**mob, "x": mx, "y": my}):
                    mob["x"], mob["y"] = resolve_collision(mob.get("region", "camp"), mx, my,
                                                           max(10.0, mob_hit_radius(mob) * .55))
                continue
            dx, dy = target["x"] - mob["x"], target["y"] - mob["y"]
            dist = math.hypot(dx, dy)
            if dist > .01 and not mob.get("pending_attack"):
                mob["face_x"], mob["face_y"] = dx / dist, dy / dist
            if dist > 520:
                mob["alert_until"] = 0.0
                mob["telegraph_until"] = 0.0
                mob["x"] += (mob["spawn_x"] - mob["x"]) * dt * .35
                mob["y"] += (mob["spawn_y"] - mob["y"]) * dt * .35
                continue
            if dist > 300 and now > mob["wander_at"]:
                mob["wander_x"], mob["wander_y"] = random.uniform(-1, 1), random.uniform(-1, 1)
                mob["wander_at"] = now + 2
            elif (not mob.get("telegraph_until") and dist < (165 if target.get("sneaking") else 360)
                  and dist > MONSTERS[mob["kind"]]["range"] * .72):
                mob["x"], mob["y"] = resolve_collision(
                    mob.get("region", "camp"),
                    mob["x"] + dx / max(1, dist) * mob_speed * dt,
                    mob["y"] + dy / max(1, dist) * mob_speed * dt,
                    max(10.0, mob_hit_radius(mob) * .55))
            strike = advance_attack(mob, target, MONSTERS[mob["kind"]], now)
            if strike:
                await send_event({"type": "combat_fx", "region": mob["region"], "kind": "monster_strike",
                                  "x": strike["x"], "y": strike["y"], "radius": strike["radius"],
                                  "attack_hint": strike, "text": ""})
                victims = [p for p in players.values() if p["respawn_at"] <= now
                           and same_region(p, mob) and not is_safe(p) and attack_contains(strike, p)]
                for target in victims:
                    dx, dy = target["x"] - mob["x"], target["y"] - mob["y"]
                    if now < float(target.get("parry_until", 0)):
                        target["parry_until"] = 0.0
                        target["counter_until"] = now + 3.6
                        target["stamina"] = min(target["max_stamina"], target["stamina"] + 8)
                        target["last_combat"] = now
                        mob["stun_until"] = now + (.7 if mob.get("boss") else 1.5)
                        await send_event({"type": "combat_fx", "region": target["region"], "kind": "parry",
                                          "id": target["id"], "x": target["x"], "y": target["y"], "text": "ПАРИРОВАНИЕ!"})
                        continue
                    if now < target["dodge_until"]:
                        mob["telegraph_until"] = 0.0
                        stam_gain = 25.0 if has_class_perk(target, "ranger", 15) else 14.0
                        target["stamina"] = min(float(target["max_stamina"]), float(target["stamina"]) + stam_gain)
                        target["counter_until"] = now + 3.6
                        await send_event({"type": "combat_fx", "region": target["region"], "kind": "perfect_dodge",
                                          "id": target["id"], "x": round(target["x"], 1), "y": round(target["y"], 1),
                                          "text": "ИДЕАЛЬНЫЙ УКЛОН!"})
                        continue
                    defense = player_defense(target)
                    defense += 2 * enchant_level(target, "gear", target.get("gear", ""), "protection")
                    eq_def_bon = equipment_bonuses(target, now)
                    raw_damage = MONSTERS[mob["kind"]]["damage"] + max(0, mob["level"] - MONSTERS[mob["kind"]]["zone"]) * 2
                    actual = max(1, round((raw_damage - defense) * (1.0 - eq_def_bon["damage_reduction_pct"])))
                    if target.get("class") == "mage" and float(target.get("ward_until", 0) or 0) <= now and has_class_perk(target, "mage", 15):
                        if float(target.get("mana", 0)) >= 5.0:
                            absorb = min(round(actual * 0.25), int(float(target["mana"]) * 0.5))
                            if absorb > 0:
                                actual = max(1, actual - absorb)
                                target["mana"] = max(0.0, float(target["mana"]) - max(2.0, absorb * 0.45))
                    if target.get("class") == "warrior" and has_class_perk(target, "warrior", 15) and target["max_hp"] > 0 and target["hp"] / target["max_hp"] <= 0.40:
                        actual = max(1, round(actual * 0.78))
                    target["hp"] = max(0, target["hp"] - actual)
                    if target["hp"] > 0:
                        apply_monster_attack_rider(target, mob, strike, now, hit_damage=actual)
                    if eq_def_bon["thorns_pct"] > 0 and mob["hp"] > 0:
                        thorn_dmg = max(1, round(raw_damage * eq_def_bon["thorns_pct"]))
                        record_mob_contribution(target, mob, thorn_dmg, now)
                        mob["hp"] = max(0, mob["hp"] - thorn_dmg)
                        await send_event({"type": "hit", "region": mob["region"], "mob": mob["id"],
                                          "x": mob["x"], "y": mob["y"], "damage": thorn_dmg, "reaction": "ОТРАЖЕНИЕ"})
                        if mob["hp"] <= 0:
                            mob["respawn_at"] = now + random.uniform(24, 40)
                            award_drop(target, mob, now)
                    target["last_combat"] = now
                    mob["telegraph_until"] = 0.0
                    # The blow shoves the hero back into the scenery, never through it.
                    shove = 34.0 if mob.get("boss") else 20.0
                    sdist = max(.01, math.hypot(dx, dy))
                    target["x"], target["y"] = resolve_collision(
                        target.get("region", "camp"),
                        target["x"] + dx / sdist * shove, target["y"] + dy / sdist * shove, 15.0)
                    await send_event({"type": "hit_player", "region": target["region"], "id": target["id"],
                                      "damage": actual, "mob": mob["kind"], "mob_id": mob["id"],
                                      "x": round(mob["x"], 1), "y": round(mob["y"], 1),
                                      "push_x": round(dx / sdist * shove, 1), "push_y": round(dy / sdist * shove, 1)})
                    if target["hp"] <= 0:
                        target["respawn_at"] = now + 5
                        target["attack"] = None; target["gathering"] = None
                        clear_player_combat_status(target)
                        await tell(target["id"], "Ты пал в бою. Через несколько секунд вернёшься в лагерь.")
        for field in list(thorn_fields):
            if field["until"] <= now:
                thorn_fields.remove(field); continue
            if field["next_hit"] <= now:
                owner = players.get(field["owner"])
                if owner:
                    for mob in mobs:
                        if mob["hp"] > 0 and same_region(owner, mob) and math.hypot(mob["x"] - field["x"], mob["y"] - field["y"]) <= field["radius"]:
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
                if mob["hp"] > 0 and same_region(owner, mob) and math.hypot(mob["x"] - field["x"], mob["y"] - field["y"]) <= radius:
                    spell_damage(owner, mob, float(field.get("damage", 1) or 1), now)
            _damage_players_around(owner, now, float(field["x"]), float(field["y"]),
                                   radius, float(field.get("damage", 1) or 1) * .8, "arrow_rain")
            await send_event({"type": "ground_pulse", "region": field["region"], "id": field["id"], "kind": field["kind"],
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
                                  and same_region(p, arrow) and p["id"] != arrow.get("owner") and p["respawn_at"] <= now
                                  and p["id"] not in hit_ids
                                  and not is_safe(p)
                                  and math.hypot(p["x"] - arrow["x"], p["y"] - arrow["y"]) < 28), None)
            if player_target and shooter and not is_safe(shooter):
                defense = player_defense(player_target)
                actual = max(1, round(arrow["damage"] * .72) - defense)
                player_target["hp"] = max(0, player_target["hp"] - actual)
                await send_event({"type": "pvp_hit", "region": shooter["region"], "attacker": shooter["id"], "id": player_target["id"],
                                  "damage": actual, "x": player_target["x"], "y": player_target["y"],
                                  **({"element": arrow.get("element", "")} if is_ability_arrow else {})})
                if player_target["hp"] <= 0:
                    player_target["respawn_at"] = now + 5
                    player_target["attack"] = None
                    player_target["gathering"] = None
                    clear_player_combat_status(player_target)
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
                                and same_region(p, arrow) and is_safe(p)
                                and math.hypot(p["x"] - arrow["x"], p["y"] - arrow["y"]) < 28), None)
            if safe_player:
                arrows.remove(arrow)
                continue
            target = next((m for m in mobs if m["hp"] > 0 and same_region(m, arrow) and m["id"] not in hit_ids
                           and math.hypot(m["x"] - arrow["x"], m["y"] - arrow["y"]) < (52 if m["boss"] else 30)), None)
            expired = arrow["life"] <= 0 or not (0 <= arrow["x"] <= WORLD_W and 0 <= arrow["y"] <= WORLD_H)
            if is_ability_arrow and target:
                owner = players.get(arrow.get("owner"))
                if owner:
                    register_combat_hit(owner, now)
                    element = str(arrow.get("element", "") or "")
                    spell_damage(owner, target, float(arrow["damage"]), now, element=element,
                                 precomputed_critical=bool(arrow.get("critical")), stagger_amt=14.0)
                    mana_gain = int(arrow.get("mana_on_hit", 0) or 0)
                    if mana_gain > 0:
                        owner["mana"] = min(float(owner["max_mana"]), float(owner["mana"]) + mana_gain)
                    splash_r = float(arrow.get("splash_radius", 0) or 0)
                    if splash_r > 0:
                        for extra in mobs:
                            if extra is not target and extra["hp"] > 0 and same_region(owner, extra) and math.hypot(extra["x"] - target["x"], extra["y"] - target["y"]) <= splash_r:
                                spell_damage(owner, extra, float(arrow["damage"]) * 0.55, now, element=element, stagger_amt=8.0)
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
                await send_event({"type": "ability_impact", "region": target["region"], "ability": "arrow", "element": arrow.get("element", ""),
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
                    elem = str(arrow.get("spell_kind", "") or "")
                    for mob in mobs:
                        if not same_region(owner, mob): continue
                        d = math.hypot(mob["x"] - arrow["x"], mob["y"] - arrow["y"])
                        if mob["hp"] > 0 and d <= radius:
                            spell_damage(owner, mob, arrow["damage"] * max(.55, 1.0-d/max(1.0,2*radius)),
                                         now, element=elem, can_crit=True,
                                         heavy=spell_id == "meteor", stagger_amt=26.0 if spell_id == "meteor" else 14.0)
                await send_event({"type": "spell_fx", "region": arrow["region"], "spell": spell_id, "kind": arrow.get("spell_kind", spell_id),
                 "name": arrow.get("spell_name", spell_id), "rarity": arrow.get("spell_rarity", 1),
                 "mastery": arrow.get("spell_mastery", 1), "variant": arrow.get("spell_variant", 0),
                 "palette": arrow.get("spell_palette", ELEMENT_FX["Аркана"]),
                 "x": arrow["x"], "y": arrow["y"], "radius": arrow.get("radius", 100), "owner": arrow.get("owner")})
                if arrow in arrows: arrows.remove(arrow)
            elif target:
                owner = players.get(arrow["owner"])
                arr_dmg = float(arrow["damage"])
                react_tag = str(arrow.get("reaction_tag") or "")
                if owner:
                    _, streak_mult = register_combat_hit(owner, now)
                    react_mult, rtag = evaluate_combat_reaction(owner, target, str(arrow.get("element") or ""), bool(arrow.get("heavy")), now)
                    arr_dmg = max(1.0, round(arr_dmg * streak_mult * react_mult))
                    if rtag:
                        react_tag = rtag
                    build_mob_stagger(target, 18.0 if arrow.get("heavy") else 10.0, now)
                    add_damage_score(owner, arr_dmg, "mob", now)
                dealt_arr = round(arr_dmg)
                if owner:
                    record_mob_contribution(owner, target, dealt_arr, now)
                target["hp"] -= dealt_arr; target["alert_until"] = now + 4
                if target["hp"] <= 0:
                    target["hp"] = 0; target["respawn_at"] = now + random.uniform(24, 40)
                    if owner: award_drop(owner, target, now)
                hit_ev: dict[str, Any] = {"type": "hit", "region": target["region"], "mob": target["id"],
                                          "x": target["x"], "y": target["y"], "damage": dealt_arr,
                                          "critical": bool(arrow.get("critical"))}
                if react_tag:
                    hit_ev["reaction"] = react_tag
                broadcast(hit_ev)
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
        if clients and now - last_snapshot >= SNAPSHOT_INTERVAL:
            last_snapshot = now
            for pid, ws in list(clients.items()):
                compact = pid in snapshot_profiles_sent
                try:
                    await ws.send_text(json.dumps(snapshot(pid, compact=compact), ensure_ascii=False))
                    if not compact:
                        snapshot_profiles_sent.add(pid)
                except Exception:
                    # Соединение сломано — освобождаем слот сразу, не дожидаясь watchdog'а.
                    drop_client(pid)
        await asyncio.sleep(TICK)


@app.on_event("startup")
async def startup() -> None:
    init_database()
    app.state.tick_task = asyncio.create_task(world_tick())
    # Watchdog: закрывает «висячие» соединения закрытых вкладок, чтобы они
    # не удерживали персонажей в мире и не занимали слоты MAX_PLAYERS.
    app.state.cleanup_task = asyncio.create_task(close_stale_clients())


@app.on_event("shutdown")
async def shutdown() -> None:
    for attribute in ("tick_task", "cleanup_task"):
        task = getattr(app.state, attribute, None)
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


def default_player(pid: str, name: str) -> dict[str, Any]:
    """Fresh character state; also used by tests and save migration."""
    return {"id": pid, "name": name, "region": "camp", "zone": "camp", "visited_regions": ["camp"],
         "region_quests": {}, "bosses_defeated": [], "bestiary_kills": {}, "world_travel_unlocked": False,
         "x": SPAWN[0], "y": SPAWN[1], "mx": 0.0, "my": 0.0,
         "face_x": 1.0, "face_y": 0.0, "hp": 100, "max_hp": 100, "stamina": 100.0, "max_stamina": 100,
         "xp": 0, "level": 1, "skill_points": 0, "talent_points": 0, "bonus_talent_points": 0,
         "gold_skill_upgrades": 0, "ability_levels": {}, "ability_uses": {}, "spell_upgrades": {},
         "quest_points": 0, "class_bonus_points": 0, "stats": {"might": 1, "vitality": 1, "agility": 1, "precision": 1, "fortune": 1},
         "herald_story_stage": 0, "herald_story_active": False, "herald_story_kills": 0,
         "gold": 0, "kills": 0, "last_attack": 0.0, "attack": None, "respawn_at": 0.0,
         "mana": 60, "max_mana": 60, "spell_cooldowns": {}, "spell_uses": {}, "custom_spells": {},
         "enchantments": {"weapon": {}, "gear": {}}, "upgrades": {"weapon": {}, "gear": {}, "accessory": {}},
         "reforges": {"weapon": {}, "gear": {}, "accessory": {}},
         "custom_weapons": {}, "accessories": [],
         "equipped_accessories": {"ring": None, "amulet": None, "artifact_1": None, "artifact_2": None},
         "magic_mana_spent": 0, "market_starter_grant": False,
         "mana_regen_level": 0, "magic_damage_level": 0, "insight_level": 0,
         "tenacity_level": 0, "ferocity_level": 0,
         "class": None, "mastery": default_mastery(), "ability_cooldowns": {},
         "roar_until": 0.0, "guard_until": 0.0, "guard_armor": 14, "bloodhunt_until": 0.0, "eagle_marks": {},
         "ward_until": 0.0, "ward_armor": 0,
         "rage_until": 0.0, "ironskin_until": 0.0, "haste_until": 0.0, "arcane_tonic_until": 0.0,
         "combo_step": 0, "combo_until": 0.0, "combat_streak": 0, "streak_until": 0.0,
         "counter_until": 0.0, "last_element": "",
         "ability_lock_until": 0.0,
         "dodge_at": 0.0, "dodge_until": 0.0, "running": False, "sneaking": False, "weapon": "sword", "weapons": ["sword", "axe", "bow"],
         "gear": "traveler", "gear_inventory": [],
         "inventory": {"wood": 0, "herb": 0, "ore": 0, "hide": 0, "slime": 0, "crystal": 0, "shard": 0,
                       "essence": 0, "rune_dust": 0, "mithril": 0, "champion_seal": 0, "potion": 2, "arrows": 18},
         "quest_stage": 0, "quest_active": False, "quest_kills": {}, "quest_gather": {},
         "gathering": None, "last_chat": 0.0, "last_combat": 0.0, "travel_lock_until": 0.0, "recall_at": 0.0,
         "tracked_quest": ""}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    account = _account_for_token(websocket.cookies.get("echo_session"))
    if not account:
        await websocket.close(code=1008, reason="AUTH_REQUIRED")
        return
    await websocket.accept()
    if len(players) >= MAX_PLAYERS:
        await close_stale_clients_once()
    if len(players) >= MAX_PLAYERS:
        await websocket.send_text(json.dumps({"type": "error", "message": "Мир полон. Максимум 8 следопытов."}, ensure_ascii=False))
        await websocket.close(code=1008); return
    pid = uuid.uuid4().hex[:8]
    name = safe_name(account["username"])
    p = default_player(pid, name)
    saved = load_character(name)
    p.update(saved)
    # Safe migration for old saves: missing class/mastery/cooldowns become neutral,
    # while every existing level, item, spell and statistic is kept intact.
    if p.get("class") not in CLASSES:
        p["class"] = None
    p["herald_story_stage"] = max(0, min(len(HERALD_QUESTS), int(p.get("herald_story_stage", 0) or 0)))
    p["herald_story_active"] = bool(p.get("herald_story_active")) and p["herald_story_stage"] < len(HERALD_QUESTS)
    p["herald_story_kills"] = min(1, max(0, int(p.get("herald_story_kills", 0) or 0)))
    if not p["herald_story_active"]:
        p["herald_story_kills"] = 0
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
    p["ward_until"] = 0.0
    p.setdefault("ward_armor", 0)
    if not isinstance(p.get("eagle_marks"), dict):
        p["eagle_marks"] = {}
    p["ability_lock_until"] = 0.0
    p["region"], p["x"], p["y"] = migrate_position(p)
    p["zone"] = p["region"]
    if not isinstance(p.get("visited_regions"), list): p["visited_regions"] = []
    p["visited_regions"] = list(dict.fromkeys(["camp", *[r for r in p["visited_regions"] if r in REGIONS], p["region"]]))
    if not isinstance(p.get("region_quests"), dict): p["region_quests"] = {}
    for rid, state in list(p["region_quests"].items()):
        if rid not in REGIONS or not isinstance(state, dict):
            p["region_quests"].pop(rid); continue
        p["region_quests"][rid] = {"active": bool(state.get("active")), "done": bool(state.get("done")),
            "gather": {k: max(0, int(v)) for k, v in (state.get("gather") or {}).items() if k in SELL_PRICES},
            "kills": {k: max(0, int(v)) for k, v in (state.get("kills") or {}).items() if k in MONSTERS}}
    if not isinstance(p.get("bosses_defeated"), list): p["bosses_defeated"] = []
    p["bosses_defeated"] = [k for k in p["bosses_defeated"] if isinstance(k, str) and k in MONSTERS]
    p["bestiary_kills"] = sanitize_kills(p.get("bestiary_kills"), MONSTERS, p["bosses_defeated"])
    if MAIN_BOSS_KIND in p["bosses_defeated"]:
        p["world_travel_unlocked"] = True
    p["world_travel_unlocked"] = bool(p.get("world_travel_unlocked", False))
    p["level"] = max(1, min(PLAYER_MAX_LEVEL, int(p.get("level", 1))))
    p["stats"] = {key: max(1, int(p.get("stats", {}).get(key, 1)))
                  for key in stat_names}
    if not isinstance(p.get("ability_levels"), dict): p["ability_levels"] = {}
    p["ability_levels"] = {str(k): max(1, min(ABILITY_MAX_LEVEL, int(v)))
                           for k, v in p["ability_levels"].items() if str(k) in ABILITY_CATALOG}
    if not isinstance(p.get("ability_uses"), dict): p["ability_uses"] = {}
    p["ability_uses"] = {str(k): max(0, int(v)) for k, v in p["ability_uses"].items() if str(k) in ABILITY_CATALOG}
    if not isinstance(p.get("spell_upgrades"), dict): p["spell_upgrades"] = {}
    p["spell_upgrades"] = {str(k): max(0, min(SPELL_MAX_LEVEL - 1, int(v)))
                           for k, v in p["spell_upgrades"].items()}
    p["bonus_talent_points"] = max(0, int(p.get("bonus_talent_points", 0) or 0))
    p["gold_skill_upgrades"] = max(0, int(p.get("gold_skill_upgrades", 0) or 0))
    # Recover unspent level-up points in older saves where the UI/action path failed.
    reconcile_skill_points(p)
    reconcile_talent_points(p)
    if not isinstance(p.get("custom_weapons"), dict):
        p["custom_weapons"] = {}
    p["custom_weapons"] = {
        str(k): v for k, v in list(p["custom_weapons"].items())[:24]
        if isinstance(v, dict) and str(k).startswith("cw_") and v.get("kind") in ("melee", "bow", "staff")
    }
    w_all_valid = all_weapons(p)
    p["weapons"] = list(dict.fromkeys(weapon for weapon in p.get("weapons", []) if weapon in w_all_valid))
    if not p["weapons"]:
        p["weapons"] = ["sword", "axe", "bow"]
    if p["weapon"] not in p["weapons"]:
        p["weapon"] = "sword"
    p["gear_inventory"] = list(dict.fromkeys(gear for gear in p.get("gear_inventory", []) if gear in GEAR and gear != p.get("gear")))
    if p["gear"] not in GEAR:
        p["gear"] = "traveler"
    p["equipped_accessories"] = equipped_accessories_map(p)
    eq_set = {v for v in p["equipped_accessories"].values() if v}
    if not isinstance(p.get("accessories"), list):
        p["accessories"] = []
    p["accessories"] = list(dict.fromkeys(a for a in p["accessories"] if a in ACCESSORIES and a not in eq_set))
    if not isinstance(p.get("reforges"), dict):
        p["reforges"] = {"weapon": {}, "gear": {}, "accessory": {}}
    for _rt in ("weapon", "gear", "accessory"):
        raw_rt = p["reforges"].get(_rt)
        p["reforges"][_rt] = {
            str(ik): str(pv) for ik, pv in (raw_rt.items() if isinstance(raw_rt, dict) else [])
            if str(pv) in REFORGE_PREFIXES and REFORGE_PREFIXES[str(pv)].get("group") == _rt
        }
    p["inventory"] = {key: max(0, min(999999, int(p.get("inventory", {}).get(key, 0))))
                       for key in p["inventory"]}
    for resource in ("wood", "herb", "ore", "hide", "slime", "crystal", "shard", "essence", "rune_dust", "mithril", "champion_seal", "potion", "arrows"):
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
    p["tenacity_level"] = max(0, min(STAT_CAPS["tenacity"], int(p.get("tenacity_level", 0) or 0)))
    p["ferocity_level"] = max(0, min(STAT_CAPS["ferocity"], int(p.get("ferocity_level", 0) or 0)))
    for _bf in ("rage_until", "ironskin_until", "haste_until", "arcane_tonic_until"):
        p[_bf] = 0.0
    if not isinstance(p.get("upgrades"), dict): p["upgrades"] = {"weapon": {}, "gear": {}, "accessory": {}}
    p["upgrades"].setdefault("weapon", {}); p["upgrades"].setdefault("gear", {}); p["upgrades"].setdefault("accessory", {})
    reconcile_skill_points(p)
    if not p.get("market_starter_grant", False):
        p["gold"] = max(0, int(p.get("gold", 0))) + 150
        p["market_starter_grant"] = True
    p["quest_stage"] = max(0, min(len(QUESTS), int(p["quest_stage"])))
    if not isinstance(p.get("tracked_quest"), str): p["tracked_quest"] = ""
    p["tracked_quest"] = p["tracked_quest"][:48]
    update_derived(p)
    players[pid] = p; clients[pid] = websocket
    snapshot_profiles_sent.discard(pid)
    last_seen_at[pid] = time.monotonic(); last_ping_at[pid] = 0.0
    await websocket.send_text(json.dumps(snapshot(pid), ensure_ascii=False))
    snapshot_profiles_sent.add(pid)
    if p["level"] >= CLASS_MIN_LEVEL and not p["class"]:
        await send_event({"type": "class_offer", "target": pid, "level": p["level"],
                          "classes": CLASSES})
    await send_event({"type": "notice", "text": f"{name} прибыл(а) в Лес Эхо."})
    try:
        while True:
            raw = await websocket.receive_text()
            # Любая активность клиента (включая автоматический 'pong' на heartbeat)
            # подтверждает, что вкладка жива — обновляем отметку для watchdog'а.
            last_seen_at[pid] = time.monotonic()
            if len(raw) > 2048: continue
            try: message = json.loads(raw)
            except json.JSONDecodeError: continue
            if isinstance(message, dict):
                kind = message.get("type")
                if kind == "pong":
                    continue  # heartbeat answer — only refreshes last_seen_at
                await handle_message(pid, p, message, time.monotonic())
    except WebSocketDisconnect:
        pass
    finally:
        departed = drop_client(pid)
        if departed is not None:
            await send_event({"type": "notice", "text": f"{name} покинул(а) мир."})


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
