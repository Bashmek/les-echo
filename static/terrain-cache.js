/* Small LRU for the full-map terrain canvases. */
(function (root) {
  'use strict';

  function createTerrainCache(capacity) {
    const limit = Math.floor(Number(capacity));
    if (!Number.isFinite(limit) || limit <= 0) throw new RangeError('terrain cache capacity must be positive');
    const entries = new Map();
    return {
      getOrCreate(key, build) {
        if (entries.has(key)) {
          const value = entries.get(key);
          entries.delete(key);
          entries.set(key, value);
          return value;
        }
        const value = build();
        entries.set(key, value);
        while (entries.size > limit) entries.delete(entries.keys().next().value);
        return value;
      },
      has(key) { return entries.has(key); },
      get size() { return entries.size; },
    };
  }

  root.EchoTerrainCache = { create: createTerrainCache };
  if (typeof module === 'object' && module.exports) module.exports = createTerrainCache;
})(typeof window === 'object' ? window : globalThis);
