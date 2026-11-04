from __future__ import annotations

from typing import Any


WORLD_W, WORLD_H = 1600, 1200
TICK = 0.025
MAX_PLAYERS = 8
# Молчание клиента дольше этого времени означает, что вкладка закрыта/уснула,
# но TCP-соединение осталось «висеть» на сервере. Такой слот принудительно
# освобождается (с сохранением персонажа), чтобы не забирать место у живых игроков.
IDLE_TIMEOUT = 45.0
CLEANUP_INTERVAL = 5.0
HEARTBEAT_INTERVAL = 10.0
MAPS = {
    "camp":     {"name": "Лагерь Следопытов",       "level": "Безопасная зона", "color": "#799457",
                 "w": 1600, "h": 1200, "safe": True,  "spawn": (500, 1000)},
    "forest":   {"name": "Шепчущий лес",             "level": "Уровень 1–3",     "color": "#63834e",
                 "w": 1800, "h": 1300, "safe": False, "spawn": (250, 650)},
    "marsh":    {"name": "Затонувшие топи",          "level": "Уровень 4–6",     "color": "#4d766c",
                 "w": 1800, "h": 1300, "safe": False, "spawn": (250, 650)},
    "ruins":    {"name": "Пепельные руины",          "level": "Уровень 7–10",    "color": "#77614e",
                 "w": 1800, "h": 1300, "safe": False, "spawn": (250, 650)},
    "glacier":  {"name": "Хребет Синего Пламени",    "level": "Уровень 11–14",   "color": "#73949c",
                 "w": 1800, "h": 1300, "safe": False, "spawn": (250, 650)},
    "rift":     {"name": "Разлом Эха",               "level": "Уровень 15–19",   "color": "#584e76",
                 "w": 1900, "h": 1400, "safe": False, "spawn": (250, 700)},
    "abyss":    {"name": "Астральная Бездна",        "level": "Уровень 20–25",   "color": "#352d51",
                 "w": 1900, "h": 1400, "safe": False, "spawn": (250, 700)},
    "obsidian": {"name": "Обсидиановый край",        "level": "Уровень 26–30",   "color": "#54435f",
                 "w": 1900, "h": 1400, "safe": False, "spawn": (250, 700)},
    "garden":   {"name": "Первозданный сад",         "level": "Уровень 31–35",   "color": "#557a4a",
                 "w": 1900, "h": 1400, "safe": False, "spawn": (250, 700)},
}

# Совместимость со старым кодом (какие-то места ещё читают ZONES)
ZONES = [{"id": mid, "name": m["name"], "x0": 0, "x1": m["w"],
          "level": m["level"], "danger": 0 if m["safe"] else 1}
         for mid, m in MAPS.items()]

PORTALS = [
    # Из главного лагеря → регионы
    {"from": "camp",     "x": 1480, "y": 200,  "r": 62, "to": "forest",   "tx": 250, "ty": 650, "label": "В Шепчущий лес",       "kind": "door",   "color": "#83a05e"},
    {"from": "camp",     "x": 1480, "y": 350,  "r": 62, "to": "marsh",    "tx": 250, "ty": 650, "label": "В Затонувшие топи",    "kind": "puddle", "color": "#5a8a80"},
    {"from": "camp",     "x": 1480, "y": 500,  "r": 62, "to": "ruins",    "tx": 250, "ty": 650, "label": "В Пепельные руины",    "kind": "door",   "color": "#8d7358"},
    {"from": "camp",     "x": 1480, "y": 650,  "r": 62, "to": "glacier",  "tx": 250, "ty": 650, "label": "К Синему Пламени",     "kind": "portal", "color": "#8ec4cc"},
    {"from": "camp",     "x": 1480, "y": 800,  "r": 62, "to": "rift",     "tx": 250, "ty": 700, "label": "В Разлом Эха",         "kind": "portal", "color": "#8a74b0"},
    {"from": "camp",     "x": 1480, "y": 950,  "r": 62, "to": "abyss",    "tx": 250, "ty": 700, "label": "В Астральную Бездну",  "kind": "portal", "color": "#5a4f7c"},
    {"from": "camp",     "x": 1480, "y": 1100, "r": 62, "to": "obsidian", "tx": 250, "ty": 700, "label": "В Обсидиановый край",  "kind": "door",   "color": "#7a6382"},
    {"from": "camp",     "x": 1480, "y": 1180, "r": 62, "to": "garden",   "tx": 250, "ty": 700, "label": "В Первозданный сад",   "kind": "portal", "color": "#7aa86a"},
    # Из регионов → главный лагерь
    {"from": "forest",   "x": 80, "y": 650, "r": 62, "to": "camp", "tx": 1380, "ty": 200,  "label": "В лагерь", "kind": "door",   "color": "#83a05e"},
    {"from": "marsh",    "x": 80, "y": 650, "r": 62, "to": "camp", "tx": 1380, "ty": 350,  "label": "В лагерь", "kind": "puddle", "color": "#5a8a80"},
    {"from": "ruins",    "x": 80, "y": 650, "r": 62, "to": "camp", "tx": 1380, "ty": 500,  "label": "В лагерь", "kind": "door",   "color": "#8d7358"},
    {"from": "glacier",  "x": 80, "y": 650, "r": 62, "to": "camp", "tx": 1380, "ty": 650,  "label": "В лагерь", "kind": "portal", "color": "#8ec4cc"},
    {"from": "rift",     "x": 80, "y": 700, "r": 62, "to": "camp", "tx": 1380, "ty": 800,  "label": "В лагерь", "kind": "portal", "color": "#8a74b0"},
    {"from": "abyss",    "x": 80, "y": 700, "r": 62, "to": "camp", "tx": 1380, "ty": 950,  "label": "В лагерь", "kind": "portal", "color": "#5a4f7c"},
    {"from": "obsidian", "x": 80, "y": 700, "r": 62, "to": "camp", "tx": 1380, "ty": 1100, "label": "В лагерь", "kind": "door",   "color": "#7a6382"},
    {"from": "garden",   "x": 80, "y": 700, "r": 62, "to": "camp", "tx": 1380, "ty": 1180, "label": "В лагерь", "kind": "portal", "color": "#7aa86a"},
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
        # ── УНИКАЛЬНЫЕ НАГРАДЫ ЭПИЛОГА (только за квесты) ──
    "duskfang": {"name": "Клык Сумрака", "kind": "melee", "damage": 26, "bonus": 34,
                 "charge": .38, "stamina": 10, "range": 38, "arc": .44, "cooldown": .18,
                 "color": "#8a7cff", "rarity": "epic"},
    "sunburst_hammer": {"name": "Молот Солнечного Всплеска", "kind": "melee",
                        "damage": 42, "bonus": 50, "charge": .90, "stamina": 24,
                        "range": 50, "arc": .08, "cooldown": .52,
                        "color": "#ffcc52", "rarity": "epic"},
    "voidcaller": {"name": "Глас Пустоты", "kind": "staff",
                   "damage": 40, "bonus": 48, "charge": .68, "stamina": 14,
                   "range": 48, "arc": .24, "cooldown": .30,
                   "color": "#c77cff", "rarity": "legendary", "spell_power": .50},
    "eternity_edge": {"name": "Клинок Вечности", "kind": "melee",
                      "damage": 72, "bonus": 88, "charge": .66, "stamina": 22,
                      "range": 58, "arc": .32, "cooldown": .30,
                      "color": "#f0d78a", "rarity": "legendary"},
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
    "duskfang": "Сумрак сгущается на лезвии перед каждым ударом.",
    "sunburst_hammer": "В молоте бьётся осколок утреннего солнца.",
    "voidcaller": "Посох шепчет голосами тех, кто не вернулся из Разлома.",
    "eternity_edge": "Клинок, выкованный в сердце Леса Эха из памяти всех его легенд.",
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
        # ── УНИКАЛЬНЫЕ НАГРАДЫ ЭПИЛОГА (только за квесты) ──
    "serpent_scale": {"name": "Чешуя Болотного Змея", "defense": 14,
                      "color": "#5d8a72", "rarity": "epic",
                      "lore": "Каждая чешуйка помнит холод топких вод."},
    "twilight_cloak": {"name": "Плащ Сумерек", "defense": 18,
                       "color": "#7a6ba8", "rarity": "epic",
                       "lore": "Ткань впитала свет последнего заката над разломом."},
    "void_heart_plate": {"name": "Панцирь Сердца Пустоты", "defense": 29,
                         "color": "#8b5ec9", "rarity": "legendary",
                         "lore": "Броня, в которой бьётся сердце, не знающее страха."},
    "crown_of_echoes": {"name": "Венец Отголосков", "defense": 42,
                        "color": "#e6c76a", "rarity": "legendary",
                        "lore": "Венец, сплетённый из голосов всех, кто сражался за Лес Эхо."},
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
SPELLS = {
    "fireball": {"name": "Огненный шар", "kind": "Огонь", "rarity": 1, "mana": 18, "cooldown": 2.8, "damage": 48, "radius": 100, "desc": "Огненный снаряд, взрывающийся по области."},
    "lightning": {"name": "Молния", "kind": "Молния", "rarity": 2, "mana": 26, "cooldown": 4.5, "damage": 58, "radius": 125, "desc": "Поражает молнией до 4 врагов в области."},
    "thorns": {"name": "Колючие терни", "kind": "Терни", "rarity": 2, "mana": 23, "cooldown": 6.5, "damage": 17, "radius": 112, "desc": "Создает поле шипов, наносящее урон с течением времени."},
    "heal": {"name": "Исцеление", "kind": "Исцеление", "rarity": 1, "mana": 24, "cooldown": 7.0, "heal": 52, "radius": 125, "unlock_spent": 0, "unlock_level": 1, "desc": "Восстанавливает здоровье вам и союзникам в радиусе действия."},
    "ice_lance": {"name": "Ледяное копьё", "kind": "Лёд", "rarity": 2, "mana": 30, "cooldown": 4.2, "damage": 72, "radius": 76, "unlock_spent": 90, "unlock_level": 3, "desc": "Ледяной снаряд, наносящий высокий урон одной цели."},
    "arcane_burst": {"name": "Всплеск маны", "kind": "Всплеск", "rarity": 3, "mana": 38, "cooldown": 7.0, "damage": 92, "radius": 148, "unlock_spent": 240, "unlock_level": 5, "desc": "Мощный взрыв чистой магии по указанной области."},
    "meteor": {"name": "Метеоритный дождь", "kind": "Звёзды", "rarity": 4, "mana": 58, "cooldown": 12.0, "damage": 132, "radius": 172, "unlock_spent": 500, "unlock_level": 8, "desc": "Вызывает падение метеорита, наносящего колоссальный урон."},
    "frost_nova": {"name": "Кольцо инея", "kind": "Лёд", "rarity": 2, "mana": 32, "cooldown": 8.0, "damage": 65, "radius": 142, "unlock_spent": 320, "unlock_level": 6, "desc": "Взрыв льда вокруг вас, поражающий всех врагов рядом."},
    "shadow_bolt": {"name": "Сумрачный снаряд", "kind": "Тень", "rarity": 2, "mana": 28, "cooldown": 3.2, "damage": 64, "radius": 62, "unlock_spent": 160, "unlock_level": 4, "desc": "Сгусток тьмы, наносящий урон одной цели."},
    "frost_ring": {"name": "Кольцо стужи", "kind": "Лёд", "rarity": 3, "mana": 34, "cooldown": 9.5, "damage": 34, "radius": 150, "stun_duration": 2.0, "slow_duration": 3.0, "slow_factor": .45, "unlock_spent": 420, "unlock_level": 7, "desc": "Замораживает (оглушает) и замедляет всех врагов вокруг вас."},
    "root_bind": {"name": "Оковы корней", "kind": "Терни", "rarity": 3, "mana": 30, "cooldown": 10.0, "damage": 26, "radius": 138, "stun_duration": 2.6, "slow_duration": 3.5, "slow_factor": .35, "unlock_spent": 300, "unlock_level": 6, "desc": "Корни опутывают цель, обездвиживая (оглушая) её."},
    "mind_chill": {"name": "Леденящий разум", "kind": "Тень", "rarity": 4, "mana": 42, "cooldown": 11.0, "damage": 58, "radius": 78, "stun_duration": 2.2, "slow_duration": 2.5, "slow_factor": .5, "unlock_spent": 620, "unlock_level": 9, "desc": "Атака разума, наносящая урон и оглушающая цель."},
}
CLASS_MIN_LEVEL = 5
MASTERY_MAX_LEVEL = 15
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
        "abilities": ["mana_shield", "meteor_swarm", "time_rift", "arcane_nova", "oblivion"],
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
                  "cost": 26, "cooldown": 9.0, "radius": 112.0, "mult": 1.05, "key": "KeyZ",
                  "desc": "Разворачивает оружие по кругу и задевает всех врагов в радиусе 112."},
    "iron_guard": {"tree": "warrior", "name": "Железная стойка", "icon": "🛡", "mastery": 4,
                   "cost": 16, "cooldown": 16.0, "duration": 5.0, "armor": 14, "key": "KeyV",
                   "desc": "На 5 секунд добавляет 14 брони и снижает входящий урон."},
    # TUNE: parry window 0.2 s feels tight but fair; try 0.25 s for a more forgiving counter.
    "parry": {"tree": "warrior", "name": "Парирование", "icon": "⛨", "mastery": 4,
              "cost": 8, "cooldown": 3.0, "duration": 0.2, "stun_duration": 1.5, "key": "KeyX",
              "desc": "Окно 0.2 с: отбивает удар моба (урон 0), оглушает его на 1.5 с."},
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
                   "burn_duration": 5.0, "burn_tick": 0.75, "burn_mult": 0.16, "key": "KeyZ",
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
             "stun_duration": 1.6, "knockback": 70.0, "key": "KeyJ",
             "desc": "Резкий выпад: оглушает ближайших врагов на 1,6 с и отбрасывает их назад."},
    "bloodhunt": {"tree": "warrior", "name": "Жажда крови", "icon": "🩸", "mastery": 3,
                  "cost": 15, "cooldown": 16.0, "duration": 6.0, "heal_per_hit": 12, "key": "KeyN",
                  "desc": "6 секунд каждый удар по врагу восстанавливает тебе 12 здоровья."},
    "seismic_slam": {"tree": "warrior", "name": "Сейсмический удар", "icon": "☄", "mastery": 5,
                    "cost": 26, "cooldown": 12.0, "radius": 135.0, "mult": 1.15,
                    "slow_duration": 2.5, "slow_factor": 0.5, "key": "KeyK",
                    "desc": "Удар о землю: волна поражает всех вокруг и замедляет врагов на 2,5 с."},
    # Расширение следопыта: три дополнительные дальнобойные техники.
    "poison_arrow": {"tree": "ranger", "name": "Отравленная стрела", "icon": "☠", "mastery": 2,
                     "cost": 14, "arrows": 1, "cooldown": 5.5, "range": 760.0, "pierce": 0, "mult": 0.9,
                     "poison_duration": 4.0, "poison_tick": 0.8, "poison_mult": 0.14, "key": "KeyJ",
                     "desc": "Стрела впрыскивает яд: урон с течением времени в течение 4 секунд."},
    "blackout_bolt": {"tree": "ranger", "name": "Ослепляющий выстрел", "icon": "◌", "mastery": 3,
                      "cost": 17, "arrows": 1, "cooldown": 8.5, "range": 700.0, "pierce": 0, "mult": 0.85,
                      "stun_duration": 1.8, "key": "KeyN",
                      "desc": "Тёмный болт оглушает цель на 1,8 секунды и прерывает её атаки."},
    "eagle_mark": {"tree": "ranger", "name": "Метка орла", "icon": "🦅", "mastery": 5,
                   "cost": 12, "arrows": 0, "cooldown": 14.0, "range": 620.0,
                   "duration": 8.0, "bonus_mult": 0.25, "key": "KeyK",
                   "desc": "Метка на цели: 8 секунд весь твой урон по ней усилен на 25%."},
    "eagle_mark": {"tree": "ranger", "name": "Метка орла", "icon": "🦅", "mastery": 5,
                   "cost": 12, "arrows": 0, "cooldown": 14.0, "range": 620.0,
                   "duration": 8.0, "bonus_mult": 0.25, "key": "KeyK",
                   "desc": "Метка на цели: 8 секунд весь твой урон по ней усилен на 25%."},
    # ─────────── ВОИН · ур. 6–15 ───────────
    "blade_tempest": {"tree": "warrior", "name": "Вихрь клинков", "icon": "⚔", "mastery": 6,
                      "cost": 30, "cooldown": 11.0, "radius": 160.0, "mult": 1.4,
                      "stun_duration": 0.6, "key": "KeyL",
                      "desc": "Круговой удар 140% урона и оглушение 0,6 с всем в радиусе 160."},
    "blood_feast": {"tree": "warrior", "name": "Кровавый пир", "icon": "🩸", "mastery": 8,
                    "cost": 32, "cooldown": 14.0, "radius": 130.0, "mult": 1.3, "heal_mult": 0.4,
                    "key": "KeyU",
                    "desc": "AoE 130% урона в радиусе 130. Лечит на 40% нанесённого урона."},
    "iron_bastion": {"tree": "warrior", "name": "Стальная стена", "icon": "⛨", "mastery": 10,
                     "cost": 24, "cooldown": 20.0, "duration": 8.0, "armor": 40, "reflect": 0.30,
                     "key": "KeyO",
                     "desc": "+40 брони на 8 с. 30% входящего урона отражается в атакующего."},
    "titan_smash": {"tree": "warrior", "name": "Удар титана", "icon": "🔨", "mastery": 12,
                    "cost": 38, "cooldown": 16.0, "range": 110.0, "mult": 3.0,
                    "stun_duration": 3.0, "key": "KeyP",
                    "desc": "Одиночный удар 300% урона с оглушением на 3 с. Дистанция 110."},
    "berserker_rage": {"tree": "warrior", "name": "Ярость берсерка", "icon": "🔥", "mastery": 15,
                       "cost": 45, "cooldown": 40.0, "duration": 12.0, "damage_bonus": 0.5,
                       "defense_penalty": 0.30, "key": "KeyY",
                       "desc": "На 12 с: +50% урона, но −30% защиты. Только для отчаянных."},
    # ─────────── СЛЕДОПЫТ · ур. 6–15 ───────────
    "volley": {"tree": "ranger", "name": "Многозарядный выстрел", "icon": "⇶", "mastery": 6,
               "cost": 24, "arrows": 3, "cooldown": 9.0, "range": 700.0, "shots": 5,
               "spread": 0.14, "mult": 0.72, "key": "KeyL",
               "desc": "Пять стрел веером, каждая 72% урона. Стоит 3 стрелы."},
    "storm_eye": {"tree": "ranger", "name": "Глаз бури", "icon": "🌪", "mastery": 8,
                  "cost": 20, "cooldown": 22.0, "duration": 10.0, "damage_mult": 1.5,
                  "key": "KeyU",
                  "desc": "На 10 с все стрелы наносят +50% урона."},
    "hurricane_rain": {"tree": "ranger", "name": "Ураганный дождь", "icon": "☈", "mastery": 10,
                       "cost": 36, "arrows": 5, "cooldown": 20.0, "range": 600.0,
                       "radius": 200.0, "duration": 4.0, "telegraph": 0.7, "tick": 0.4,
                       "mult": 0.75, "key": "KeyO",
                       "desc": "Огромная зона дождя (радиус 200) на 4 с, удары каждые 0,4 с."},
    "deadeye_shot": {"tree": "ranger", "name": "Смертельный выстрел", "icon": "🎯", "mastery": 12,
                     "cost": 30, "arrows": 1, "cooldown": 14.0, "range": 1500.0,
                     "pierce": 1, "mult": 3.5, "guaranteed_crit": True, "key": "KeyP",
                     "desc": "Один выстрел на 350% урона, всегда крит. Дистанция 1500."},
    "apocalypse_arrow": {"tree": "ranger", "name": "Стрела Апокалипсиса", "icon": "☄",
                         "mastery": 15, "cost": 42, "arrows": 5, "cooldown": 45.0,
                         "range": 800.0, "radius": 260.0, "mult": 4.0, "key": "KeyY",
                         "desc": "Стрела взрывается: 400% урона в радиусе 260. Стоит 5 стрел."},
    # ─────────── МАГ · ур. 6–15 ───────────
    "mana_shield": {"tree": "mage", "name": "Мана-щит", "icon": "🔮", "mastery": 6,
                    "cost": 10, "mana_cost": 30, "cooldown": 15.0, "duration": 8.0,
                    "absorb_ratio": 0.6, "key": "KeyL",
                    "desc": "8 с: 60% входящего урона уходит в ману, а не в HP."},
    "meteor_swarm": {"tree": "mage", "name": "Метеоритный рой", "icon": "☄", "mastery": 8,
                     "cost": 12, "mana_cost": 45, "cooldown": 18.0, "range": 400.0,
                     "radius": 130.0, "mult": 1.6, "meteors": 3, "key": "KeyU",
                     "desc": "Три метеора падают в зону. Каждый — 160% урона в радиусе 130."},
    "time_rift": {"tree": "mage", "name": "Временной разлом", "icon": "⏳", "mastery": 10,
                  "cost": 14, "mana_cost": 40, "cooldown": 25.0, "radius": 200.0,
                  "slow_duration": 5.0, "slow_factor": 0.3, "key": "KeyO",
                  "desc": "Все враги в радиусе 200 замедлены на 70% в течение 5 с."},
    "arcane_nova": {"tree": "mage", "name": "Аркан-взрыв", "icon": "◉", "mastery": 12,
                    "cost": 16, "mana_cost": 60, "cooldown": 20.0, "radius": 200.0,
                    "mult": 3.0, "key": "KeyP",
                    "desc": "Мощный взрыв вокруг себя: 300% урона всем в радиусе 200."},
    "oblivion": {"tree": "mage", "name": "Забвение", "icon": "☠", "mastery": 15,
                 "cost": 22, "mana_cost": 100, "cooldown": 60.0, "range": 500.0,
                 "radius": 300.0, "mult": 5.0, "stun_duration": 3.0, "key": "KeyY",
                 "desc": "500% урона в радиусе 300 и оглушение 3 с. Требует 100 маны."},
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
    {"id": "spring",   "name": "Источник живой воды",          "map": "forest",   "x": 700, "y": 900, "radius": 170, "buff": "Здоровье +2/с"},
    {"id": "root",     "name": "Сердце древнего леса",         "map": "marsh",    "x": 900, "y": 750, "radius": 180, "buff": "Мана +3/с"},
    {"id": "ember",    "name": "Жар пепельной кузни",          "map": "ruins",    "x": 850, "y": 550, "radius": 170, "buff": "Выносливость +4/с"},
    {"id": "glacier",  "name": "Кристалл синего пламени",      "map": "glacier",  "x": 950, "y": 700, "radius": 170, "buff": "HP и мана +1.5/с"},
    {"id": "echo",     "name": "Алтарь эха",                   "map": "rift",     "x": 1000, "y": 800, "radius": 190, "buff": "Все ресурсы быстрее"},
    {"id": "obsidian", "name": "Осколок чёрного стекла",       "map": "obsidian", "x": 1050, "y": 700, "radius": 200, "buff": "Все ресурсы быстрее"},
    {"id": "garden",   "name": "Сердце Первозданного сада",    "map": "garden",   "x": 1100, "y": 750, "radius": 210, "buff": "HP/мана/вын. +3/с"},
]
def safe_name(value: Any) -> str:
    return " ".join(str(value).strip().split())[:18] or "Путник"


def zone_for_x(x: float) -> dict[str, Any]:
    for zone in ZONES:
        if zone["x0"] <= x < zone["x1"]:
            return zone
    return ZONES[-1]
QUESTS = [
    ("slime", 4, "herb", 3, "Очистить опушку"), ("wolf", 3, "ore", 4, "Следы в топи"),
    ("boar", 3, "crystal", 3, "Свет под водой"), ("colossus", 1, "", 0, "Пепельный колосс"),
    ("frost_wyrm", 4, "crystal", 6, "Синий хребет"), ("echo_dragon", 1, "shard", 8, "Разлом Эха"),
    ("rift_knight", 4, "shard", 6, "Стражи разлома"), ("echo_dragon", 2, "crystal", 12, "Сердце пустоты"),
    ("void_wraith", 5, "shard", 12, "Угольный след"), ("obsidian_sentinel", 5, "ore", 18, "Ключ из чёрного стекла"),
    ("starseer", 4, "crystal", 20, "Охота на звёздочёта"), ("starseer", 5, "herb", 22, "Корни под звёздами"),
    ("ancient_warden", 1, "shard", 30, "Страж Первозданного сада"),
        # ── ЭПИЛОГ: Путь Хранителя ──
    ("wolf", 8, "crystal", 10, "Эхо в тумане"),
    ("stone", 4, "crystal", 12, "Сердце болота"),
    ("ashling", 10, "shard", 15, "Пламя и пепел"),
    ("frost_wyrm", 7, "crystal", 18, "Холод синего пламени"),
    ("rift_knight", 7, "shard", 22, "Клинки разлома"),
    ("void_wraith", 10, "shard", 25, "Тень пустоты"),
    ("astral_titan", 1, "shard", 30, "Наследие Эха"),
]
QUEST_REWARDS = [
    (45, 100, [("potion", "potion", 2)]), (90, 220, [("gear", "wolf_cloak", 1)]),
    (145, 360, [("gear", "marsh_armor", 1)]), (260, 700, [("gear", "ash_plate", 1)]),
    (420, 1000, [("gear", "ash_plate", 1)]), (700, 1600, [("gear", "ash_plate", 1)]),
    (950, 2200, [("weapon", "frostfang", 1)]), (1400, 3200, [("weapon", "void_edge", 1)]),
    (1700, 3800, [("gear", "obsidian_shell", 1)]), (2100, 4600, [("weapon", "obsidian_axe", 1)]),
    (2500, 5600, [("gear", "starseer_robe", 1)]), (3200, 7200, [("weapon", "sunfall_bow", 1)]),
    (5000, 12000, [("gear", "elder_mantle", 1), ("weapon", "elder_staff", 1)]),
        # ── ЭПИЛОГ: уникальные награды ──
    (800, 1800, [("weapon", "duskfang", 1)]),
    (900, 2000, [("gear", "serpent_scale", 1)]),
    (1200, 2600, [("weapon", "sunburst_hammer", 1)]),
    (1400, 3000, [("gear", "twilight_cloak", 1)]),
    (1800, 3600, [("weapon", "voidcaller", 1)]),
    (2200, 4200, [("gear", "void_heart_plate", 1)]),
    (5000, 10000, [("weapon", "eternity_edge", 1), ("gear", "crown_of_echoes", 1)]),
]
def quest_requirements(stage: int) -> tuple[str, int, str, int, str]:
    return QUESTS[min(max(0, int(stage)), len(QUESTS) - 1)]
MAX_ITEM_UPGRADE = 5
SPELL_ICONS = {"fireball": "✦", "lightning": "ϟ", "heal": "✚", "thorns": "❖", "ice_lance": "❄",
               "arcane_burst": "◉", "meteor": "☄", "frost_nova": "✧", "shadow_bolt": "◈"}

# ─────────────────────────────────────────────────────────────────────────────
# СКРЫТЫЕ NPC И ИХ PvP-ДАРЫ
# ─────────────────────────────────────────────────────────────────────────────
PVP_TALENTS = {
    "hunter_instinct": {
        "name": "Чутьё охотника", "icon": "🎯",
        "description": "+8% урона по игрокам, +15% шанс крита в PvP",
        "pvp_damage_mult": 1.08,
        "pvp_crit_bonus": 0.15,
    },
    "bog_endurance": {
        "name": "Стойкость топей", "icon": "🌿",
        "description": "+15 плоской брони против атак других игроков",
        "pvp_armor_bonus": 15,
    },
    "ash_veil": {
        "name": "Пепельная завеса", "icon": "🔥",
        "description": "−15% входящего урона от игроков",
        "pvp_damage_reduction": 0.15,
    },
    "glacial_step": {
        "name": "Ледяной шаг", "icon": "❄",
        "description": "+20% скорости, когда в радиусе 400 ед. есть враг-игрок",
        "pvp_haste_when_hunted": 1.20,
    },
    "riftwalker": {
        "name": "Идущий сквозь разлом", "icon": "◈",
        "description": "10% похищения жизни в PvP; первый удар в дуэли — гарантированный крит ×2",
        "pvp_lifesteal": 0.10,
        "pvp_first_hit_crit": True,
    },
}

HIDDEN_NPCS = [
    {
        "id": "hermit_mist", "name": "Отшельник Мглы", "icon": "🧙",
        "x": 400, "y": 750, "zone": "forest",
        "greeting": "Ты пахнешь кровью и удачей, странник. Слушай: волки в тумане — лучшие учителя. Принеси мне 15 их шкур, не умерев ни разу, — и я научу тебя бить других путников так, как бьёт туман: внезапно и точно.",
        "quest": {
            "goal": {"type": "kill_without_death", "mob": "wolf", "count": 15},
            "reward_talent": "hunter_instinct",
        },
    },
    {
        "id": "bog_shaman", "name": "Болотный шаман", "icon": "🧙‍♂️",
        "x": 400, "y": 750, "zone": "marsh",
        "greeting": "Топи шепчут о тебе. Хочешь выживать в них — покажи, что умеешь стоять в грязи. Принеси мне кости вепрей и руду из глубины, и я дам тебе стойкость, которой не сломать и в поединке.",
        "quest": {
            "goal": {"type": "kill_and_collect", "mob": "boar", "kill_count": 10,
                     "collect": "ore", "collect_count": 20},
            "reward_talent": "bog_endurance",
        },
    },
    {
        "id": "ash_priestess", "name": "Пепельная жрица", "icon": "🔥",
        "x": 400, "y": 750, "zone": "ruins",
        "greeting": "Пепел шепчет: ты уже горел. Принеси мне пепел стражей и осколков — и я научу тебя гореть так, чтобы даже в дуэли ты не сгорал, а вспыхивал.",
        "quest": {
            "goal": {"type": "kill_and_collect", "mob": "ashguard", "kill_count": 8,
                     "collect": "shard", "collect_count": 10},
            "reward_talent": "ash_veil",
        },
    },
    {
        "id": "ice_wanderer", "name": "Странник льда", "icon": "❄",
        "x": 400, "y": 750, "zone": "glacier",
        "greeting": "Холод — лучший учитель скорости. Убей ледяных змеев и принеси мне кристаллов их дыхания. Тогда я научу тебя двигаться так быстро, как бежит зима, когда за тобой идёт смерть.",
        "quest": {
            "goal": {"type": "kill_and_collect", "mob": "frost_wyrm", "kill_count": 5,
                     "collect": "crystal", "collect_count": 15},
            "reward_talent": "glacial_step",
        },
    },
    {
        "id": "rift_shadow", "name": "Тень разлома", "icon": "◈",
        "x": 400, "y": 780, "zone": "rift",
        "greeting": "Я — то, что осталось от того, кто убил дракона и не вернулся. Сразись с теми, кто стерегёт разлом, — и я отдам тебе свою последнюю тень. Она пьёт жизнь других, как я пил вино в последний вечер.",
        "quest": {
            "goal": {"type": "kill_multiple", "mobs": {"rift_knight": 3, "echo_dragon": 1}},
            "reward_talent": "riftwalker",
        },
    },
]