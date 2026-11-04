from __future__ import annotations

import random
import time
from typing import Any

from data import GEAR, MAX_ITEM_UPGRADE, MONSTERS, WEAPONS, zone_for_x


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
def apply_player_control(target: dict[str, Any], now: float, *, slow_duration: float = 0.0,
                         slow_factor: float = .45, stun_duration: float = 0.0, source: str = "") -> str | None:
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
            return f"Ты оглушён{' ' + source if source else ''}: {duration:.1f} с."
    return None
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
        "pvp": bucket("pvp", "pvp_spell"),
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
def spell_control(spec: dict[str, Any], target: dict[str, Any], now: float, source: str) -> str | None:
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
    if "mx" in target:  # players carry movement input, mobs do not
        return apply_player_control(target, now,
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
    return None
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
            "face_x": 0.0, "face_y": 0.0,
            # Marsh (топи) mobs start "wet" so fire/ice/lightning trigger reactions there.
            "wet_until": float("inf") if zone_for_x(x)["id"] == "marsh" else 0.0,
            "boss": bool(spec.get("boss") or kind == "colossus")}
def weapon_power(p: dict[str, Any]) -> float:
    spec = WEAPONS.get(p.get("weapon", ""), WEAPONS["sword"])
    upgrade = 0 if spec.get("kind") == "staff" else 6 * item_upgrade_level(p, "weapon", p.get("weapon", ""))
    return (float(spec.get("damage", 0)) + float(spec.get("bonus", 0)) * .55
            + (int(p.get("stats", {}).get("might", 1)) - 1) * 2.2
            + 8 * enchant_level(p, "weapon", p.get("weapon", ""), "sharpness") + upgrade)
def enchant_level(p: dict[str, Any], target: str, item_id: str, enchant_id: str) -> int:
    return int(p.get("enchantments", {}).get(target, {}).get(item_id, {}).get(enchant_id, 0))
def item_upgrade_level(p: dict[str, Any], target: str, item_id: str) -> int:
    return max(0, min(MAX_ITEM_UPGRADE,
                      int(p.get("upgrades", {}).get(target, {}).get(item_id, 0))))
def player_defense(p: dict[str, Any]) -> int:
    gear_id = p.get("gear", "traveler")
    base = GEAR.get(gear_id, GEAR["traveler"])["defense"]
    guard = 14 if float(p.get("guard_until", 0) or 0) > time.monotonic() else 0
    return (base + 3 * item_upgrade_level(p, "gear", gear_id)
            + 2 * enchant_level(p, "gear", gear_id, "protection") + guard)


def compute_melee_damage(p: dict[str, Any], weapon_id: str, charge: float) -> dict[str, Any]:
    """Authoritative melee/arrow damage roll (crit chance included)."""
    spec = WEAPONS.get(weapon_id, WEAPONS["sword"])
    power_bonus = (int(p.get("stats", {}).get("might", 1)) - 1) * 2.2
    weapon_upgrade = item_upgrade_level(p, "weapon", weapon_id)
    physical_upgrade = 0 if spec["kind"] == "staff" else 6 * weapon_upgrade
    base_damage = (spec["damage"] + spec["bonus"] * charge + power_bonus
                   + 8 * enchant_level(p, "weapon", weapon_id, "sharpness")
                   + physical_upgrade)
    crit_chance = min(.30, max(0, (int(p.get("stats", {}).get("precision", 1)) - 1) * .025))
    critical = random.random() < crit_chance
    return {"damage": round(base_damage * (1.75 if critical else 1.0)),
            "critical": critical, "crit_chance": crit_chance, "spec": spec}


def apply_hit_to_mob(mob: dict[str, Any], damage: float) -> bool:
    """Subtract damage from a monster; returns True when it died."""
    mob["hp"] = max(0, mob["hp"] - damage)
    return mob["hp"] <= 0


def apply_hit_to_player(target: dict[str, Any], damage: float,
                        pvp_factor: float = PVP_DAMAGE_FACTOR) -> int:
    """Apply softened PvP damage after armor; returns the final damage dealt."""
    actual = max(1, round(damage * pvp_factor) - player_defense(target))
    target["hp"] = max(0, target["hp"] - actual)
    return actual


def apply_control(spec: dict[str, Any], target: dict[str, Any], now: float,
                  source: str = "") -> str | None:
    """Apply a stun/slow control effect to a monster or player (alias)."""
    return spell_control(spec, target, now, source)


# --- Elemental reactions (Phase 3: боевая глубина) --------------------------
# Canonical element ids; spell specs use Russian kind names, arrows use English.
ELEMENT_ALIASES = {
    "Огонь": "fire", "Лёд": "ice", "Молния": "lightning", "Яд": "poison",
    "Терни": "poison", "Тень": "shadow", "fire": "fire", "ice": "ice",
    "lightning": "lightning", "poison": "poison", "shadow": "shadow",
}


def canonical_element(element: str) -> str:
    return ELEMENT_ALIASES.get(str(element or ""), "")


def apply_elemental_reaction(mob: dict[str, Any], element: str, now: float) -> tuple[float, str]:
    """Elemental reactions between statuses (server-authoritative).

    Returns ``(damage_multiplier, reaction_name)``. Mutates the mob's status
    fields (consumes ``wet``, applies ``stun`` for freeze). The caller is
    responsible for any chain/AoE that needs the live mob list.

    Reactions:
      fire + wet        -> Пар (steam)        x1.5, consumes wet
      ice  + wet        -> Лёд (frozen)       stun 2.0 s, consumes wet
      lightning + wet   -> Разряд (shock)     x1.3, consumes wet (chain in caller)
      fire + frozen     -> Таяние (melt)      x2.0
      fire + poison     -> Воспламенение      x1.5
    """
    if mob.get("hp", 0) <= 0:
        return 1.0, ""
    canonical = canonical_element(element)
    wet = float(mob.get("wet_until", 0) or 0) > now
    frozen = float(mob.get("stun_until", 0) or 0) > now
    poisoned = float(mob.get("poison_until", 0) or 0) > now
    if canonical == "fire" and frozen:
        return 2.0, "Таяние"
    if canonical == "fire" and wet:
        mob["wet_until"] = 0.0
        return 1.5, "Пар"
    if canonical == "ice" and wet:
        mob["wet_until"] = 0.0
        mob["stun_until"] = max(float(mob.get("stun_until", 0) or 0), now + 2.0)
        return 1.0, "Лёд"
    if canonical == "lightning" and wet:
        mob["wet_until"] = 0.0
        return 1.3, "Разряд"
    if canonical == "fire" and poisoned:
        return 1.5, "Воспламенение"
    return 1.0, ""


def backstab_multiplier(mob: dict[str, Any], ax: float, ay: float) -> float:
    """+30% damage when the attack lands from behind the mob's facing."""
    fx = float(mob.get("face_x", 0) or 0)
    fy = float(mob.get("face_y", 0) or 0)
    if fx == 0.0 and fy == 0.0:
        return 1.0
    # Attacker direction (ax, ay) is roughly opposite the mob facing.
    if ax * fx + ay * fy < -0.3:
        return 1.3
    return 1.0
