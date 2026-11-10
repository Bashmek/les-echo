/* Cosmetic queues use a real monotonic clock, independently of hit-stop. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.EchoTransientEffects = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const clock = () => typeof performance !== 'undefined' ? performance.now() : Date.now();
  const time = value => Number.isFinite(value) ? value : clock();

  function pruneExpired(array, nowMs, limit = Infinity) {
    const now = time(nowMs);
    let kept = 0;
    for (let i = 0; i < array.length; i++) {
      const item = array[i];
      if (item && item.until > now) array[kept++] = item;
    }
    array.length = kept;
    const cap = limit === Infinity ? kept : Math.max(0, Math.floor(Number(limit) || 0));
    if (kept > cap) {
      array.copyWithin(0, kept - cap, kept);
      array.length = cap;
    }
    return array;
  }

  function createParticlePool({ maxParticles = 400 } = {}) {
    const cap = Number.isFinite(maxParticles) ? Math.max(0, Math.floor(maxParticles)) : 400;
    const particles = [];

    function spawn(x, y, color, count = 12, speed = 4, size = 4, life = .55, nowMs) {
      if (!cap || !Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(count) ||
          !Number.isFinite(life) || life <= 0) return;
      const now = time(nowMs);
      const added = Math.min(cap, Math.max(0, Math.floor(count)));
      pruneExpired(particles, now, cap - added);
      const velocity = Number.isFinite(speed) ? Math.max(0, speed) : 4;
      const radius = Number.isFinite(size) ? Math.max(0, size) : 4;
      for (let i = 0; i < added; i++) {
        const angle = Math.random() * Math.PI * 2;
        const magnitude = (.3 + Math.random() * .7) * velocity;
        particles.push({
          x, y, vx: Math.cos(angle) * magnitude, vy: Math.sin(angle) * magnitude,
          color, size: radius * (.6 + Math.random() * .8), alpha: 1,
          born: now, last: now, until: now + life * 1000,
        });
      }
    }

    function draw(ctx, ox = 0, oy = 0, nowMs) {
      const now = time(nowMs);
      pruneExpired(particles, now);
      if (!particles.length) return;
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        const frames = Math.max(0, now - p.last) * .06;
        // Geometric-series displacement matches x += vx; vx *= .95 at 60 Hz,
        // including fractional steps, without replaying frames after a pause.
        const damping = Math.pow(.95, frames);
        const distance = (1 - damping) / .05;
        p.x += p.vx * distance;
        p.y += p.vy * distance;
        p.vx *= damping;
        p.vy *= damping;
        p.last = Math.max(p.last, now);
        p.alpha = Math.max(0, Math.min(1, (p.until - now) / (p.until - p.born)));
        ctx.globalAlpha = p.alpha;
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x + ox, p.y + oy, p.size * p.alpha, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }

    function clear() { particles.length = 0; }
    return { particles, spawn, draw, clear };
  }

  return { createParticlePool, pruneExpired };
});
