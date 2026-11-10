/* Frame-rate independent presentation; authoritative entity coordinates stay untouched. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.EchoMotion = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const FRAME_MS = 1000 / 60;

  function frameBlend(alpha, elapsedMs) {
    const a = Math.max(0, Math.min(1, Number(alpha) || 0));
    const dt = Math.max(0, Number(elapsedMs) || 0);
    return dt > 0 ? 1 - Math.pow(1 - a, dt / FRAME_MS) : 0;
  }

  function createTracker({ halfLifeMs = 32, snapDistance = 260, resetAfterMs = 250 } = {}) {
    const views = new Map();
    function sample(entity, nowMs, halfLife = halfLifeMs) {
      if (!entity || entity.id == null || !Number.isFinite(entity.x) || !Number.isFinite(entity.y)
          || !Number.isFinite(nowMs)) return entity;
      let view = views.get(entity.id);
      const respawning = !!entity.respawning;
      if (!view || view.region !== entity.region || view.respawning !== respawning
          || nowMs - view.at > resetAfterMs
          || Math.hypot(entity.x - view.x, entity.y - view.y) > snapDistance) {
        view = { x: entity.x, y: entity.y, at: nowMs, region: entity.region, respawning };
        views.set(entity.id, view);
        return view;
      }
      // Camera, culling and sprite rendering can all ask in one frame.
      // Read the same view without taking a second smoothing step.
      if (nowMs <= view.at) return view;
      const alpha = 1 - Math.pow(.5, (nowMs - view.at) / Math.max(1, halfLife));
      view.x += (entity.x - view.x) * alpha;
      view.y += (entity.y - view.y) * alpha;
      view.at = nowMs;
      if (Math.hypot(entity.x - view.x, entity.y - view.y) < .05) {
        view.x = entity.x; view.y = entity.y;
      }
      return view;
    }
    function retain(...groups) {
      const live = new Set();
      for (const group of groups) for (const entity of group || []) live.add(entity.id);
      for (const id of views.keys()) if (!live.has(id)) views.delete(id);
    }
    return { sample, retain, clear: () => views.clear(), get size() { return views.size; } };
  }

  function advanceClock(state, nowMs) {
    state.frameMs = 0; state.activeMs = 0; state.resumed = false;
    if (!Number.isFinite(nowMs)) return state;
    const previous = state.lastFrame;
    const first = previous == null || !Number.isFinite(previous);
    const gap = first ? 0 : nowMs - previous;
    if (first || gap > 250) {
      state.lastFrame = nowMs; state.motionNow = nowMs;
      state.frameMs = FRAME_MS; state.freeze = 0; state.resumed = !first;
      return state;
    }
    if (gap <= 0) return state;
    const frozenMs = Math.min(gap, Math.max(0, Number(state.freeze) || 0));
    state.freeze = Math.max(0, (Number(state.freeze) || 0) - frozenMs);
    state.lastFrame = nowMs;
    state.frameMs = Math.min(64, gap);
    state.activeMs = gap - frozenMs;
    state.motionNow = (Number.isFinite(state.motionNow) ? state.motionNow : previous) + state.activeMs;
    return state;
  }

  function requestFreeze(state, durationMs, nowMs) {
    const duration = Math.min(190, Math.max(0, Number(durationMs) || 0));
    if (!duration || !Number.isFinite(nowMs) || state.freeze > 0
        || nowMs < (state.freezeReadyAt ?? -Infinity)) return false;
    state.freeze = duration;
    state.freezeReadyAt = nowMs + 250;
    return true;
  }

  return { createTracker, frameBlend, advanceClock, requestFreeze };
});
