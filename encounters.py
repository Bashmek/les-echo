"""Deterministic monster windups; the serialized geometry is also the hitbox."""
import math

HERALD_SIGNATURE_EFFECTS = {
    ("bramble_warden", "line"): ("slow", "Корни цепляют"),
    ("fen_matron", "cone"): ("poison", "Яд трясины"),
    ("ashbound_herald", "circle"): ("burn", "Пепельный ожог"),
    ("blueflame_siren", "cone"): ("slow", "Колокол ледяной тишины"),
    ("glass_inquisitor", "circle"): ("poison", "Осколочный приговор"),
}


def boss_phase(mob):
    if not (mob.get("boss") or mob.get("mini_boss")):
        return 1
    ratio = mob["hp"] / max(1, mob["max_hp"])
    return 3 if ratio <= .33 else 2 if ratio <= .66 else 1


def backstab(mob, player):
    """Reward circling around a living target facing its original lane."""
    dx=player['x']-mob['x'];dy=player['y']-mob['y']
    distance=math.hypot(dx,dy)
    if distance < 1: return False
    fx=float(mob.get('face_x',1));fy=float(mob.get('face_y',0))
    facing=math.hypot(fx,fy)
    if facing < .01:return False
    return (dx*fx+dy*fy)/(distance*facing) <= -.5


def attack_contains(attack, target):
    dx, dy = target["x"] - attack["x"], target["y"] - attack["y"]
    radius = attack["radius"]
    if attack["shape"] == "circle":
        return math.hypot(dx, dy) <= radius
    angle = attack["angle"]
    along = dx * math.cos(angle) + dy * math.sin(angle)
    across = -dx * math.sin(angle) + dy * math.cos(angle)
    if attack["shape"] == "line":
        return 0 <= along <= radius and abs(across) <= attack["width"]
    return math.hypot(dx, dy) <= radius and abs(math.atan2(across, along)) <= attack["half_angle"]


def attack_view(mob, now):
    attack = mob.get("pending_attack")
    if not attack or mob.get("telegraph_until", 0) <= 0:
        return None
    return {**attack, "progress": min(1., max(0., (now - attack["started"]) / attack["duration"]))}


def advance_attack(mob, target, spec, now):
    """Start, wait or consume exactly one strike, including when it misses.

    Stuns in the existing server cancel by clearing telegraph_until. A pending
    attack never tracks its victim and never moves with its caster.
    """
    if mob.get("telegraph_until", 0) <= 0:
        mob["pending_attack"] = None
    pending = mob.get("pending_attack")
    if pending:
        if now < mob["telegraph_until"]:
            return None
        mob["telegraph_until"] = 0.
        mob["pending_attack"] = None
        mob["attack_at"] = now + spec["cooldown"] * (1 - .12 * (boss_phase(mob) - 1))
        mob["attack_step"] = mob.get("attack_step", 0) + 1
        return pending
    if now < mob.get("attack_at", 0) or target is None:
        return None
    phase = boss_phase(mob)
    kind = mob.get("kind", "")
    if mob.get("boss"):
        patterns = {
            "colossus": ("circle", "cone", "line"),
            "echo_dragon": ("cone", "line", "circle"),
            "astral_titan": ("line", "circle", "cone"),
            "ancient_warden": ("circle", "line", "cone"),
        }.get(kind, ("cone", "circle", "line"))
        shape = patterns[mob.get("attack_step", 0) % (2 if phase == 1 else 3)]
    elif mob.get("mini_boss"):
        patterns = {
            "bramble_warden": ("circle", "line", "cone"),
            "fen_matron": ("circle", "cone", "line"),
            "ashbound_herald": ("line", "circle", "cone"),
            "blueflame_siren": ("circle", "cone", "line"),
            "glass_inquisitor": ("line", "cone", "circle"),
        }.get(kind, ("circle", "line", "cone"))
        shape = patterns[mob.get("attack_step", 0) % (2 if phase == 1 else 3)]
    elif kind in ("boar", "rift_knight"):
        shape = "line"
    elif kind in ("slime", "wisp", "stone", "starseer", "void_wraith"):
        shape = "circle"
    else:
        shape = "cone"
    radius = float(spec["range"]) * (1.65 if shape == "line" else 1.2)
    if math.hypot(target["x"] - mob["x"], target["y"] - mob["y"]) > radius:
        return None
    duration = (1.05 if mob.get("boss") else .92 if mob.get("mini_boss") else .78) - .1 * (phase - 1)
    angle = math.atan2(target["y"] - mob["y"], target["x"] - mob["x"])
    mob["face_x"], mob["face_y"] = math.cos(angle), math.sin(angle)
    names = {
        "colossus": {"circle": "Пепельный раскол", "cone": "Каменный кулак", "line": "Разлом земли"},
        "echo_dragon": {"cone": "Дыхание Эха", "line": "Коготь пустоты", "circle": "Взмах крыльев"},
        "astral_titan": {"line": "Звёздное копьё", "circle": "Коллапс светила", "cone": "Серп бездны"},
        "ancient_warden": {"circle": "Гнев корней", "line": "Шип первозданного", "cone": "Жатва сада"},
        "bramble_warden": {"circle": "Круговорот корней", "line": "Шипастый прорыв", "cone": "Коса ветвей"},
        "fen_matron": {"circle": "Воронка трясины", "cone": "Ядовитый плевок", "line": "Нырок со дна"},
        "ashbound_herald": {"line": "Цепной раскол", "circle": "Пепельный звон", "cone": "Клеймо угля"},
        "blueflame_siren": {"circle": "Зов ледяной короны", "cone": "Колокол ледяной тишины", "line": "Сквозняк синего огня"},
        "glass_inquisitor": {"line": "Шрам по чёрному стеклу", "cone": "Приговор осколками", "circle": "Осколочный приговор"},
    }.get(kind, {"cone": "Рассекающий удар", "circle": "Ударная волна", "line": "Пробивающий выпад"})
    pending = dict(shape=shape, x=mob["x"], y=mob["y"],
        radius=radius, angle=angle, half_angle=.85, width=max(18., radius * .19),
        started=now, duration=duration, phase=phase,
        name=names[shape])
    rider = HERALD_SIGNATURE_EFFECTS.get((kind, shape)) if mob.get("mini_boss") else None
    if rider:
        pending["effect"], pending["effect_label"] = rider
    mob["pending_attack"] = pending
    mob["telegraph_until"] = now + duration
    return None
