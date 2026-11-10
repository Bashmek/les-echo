/* Server combat rules shared by browser controls and Node tests. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.EchoCombatRules = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function attackChargeSeconds(player) {
    const spec = player?.weapon_catalog?.[player.weapon];
    const charge = Number(spec?.charge);
    const speed = Number(player?.equipment_bonuses?.attack_speed_pct);
    const baseCharge = Number.isFinite(charge) && charge > 0 ? charge : .65;
    const attackSpeed = Number.isFinite(speed) ? speed : 0;
    return Math.max(.16, baseCharge / Math.max(.45, 1 + attackSpeed));
  }

  function spellGate(player) {
    if (player?.class !== 'mage') {
      return { allowed: false,
        reason: 'Сначала выбери квалификацию «Маг» — заклинания доступны только магам.' };
    }
    if (player.weapon_kind !== 'staff') {
      return { allowed: false,
        reason: 'Для заклинаний нужен посох. Сейчас в руках другое оружие.' };
    }
    return { allowed: true, reason: '' };
  }

  function temperBenefitLabel(player, target, itemId) {
    if (target === 'gear') return '+3 защиты';
    if (target === 'accessory') return '+8% к характеристикам реликвии';
    const kind = player?.weapon_catalog?.[itemId]?.kind;
    if (kind === 'staff') return '+6 к урону заклинаний';
    if (kind === 'bow') return '+6 к урону стрел';
    return '+6 к урону ближней атаки';
  }

  return { attackChargeSeconds, spellGate, temperBenefitLabel };
});
