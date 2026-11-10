/* Map-scoped WebSocket event filtering. Shared by the browser and Node tests. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.MapEvents = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function regionId(event) {
    if (!event) return null;
    if (typeof event.region === 'string') return event.region;
    return event.region?.id || null;
  }

  function accepts(event, currentRegion) {
    const rid = regionId(event);
    // Full snapshots carry public region metadata and must replace the old map.
    return !(rid && currentRegion && rid !== currentRegion && event.type !== 'state');
  }

  function mergeSnapshot(previous, incoming) {
    if (!incoming?.compact || !previous || previous.you !== incoming.you) return incoming;
    const previousRegion = regionId(previous), incomingRegion = regionId(incoming);
    // A map change needs a full payload with its terrain, portal, and atlas data.
    if (previousRegion && incomingRegion && previousRegion !== incomingRegion) return previous;

    const merged = { ...previous, ...incoming };
    if (previousRegion && previousRegion === incomingRegion) merged.region = previous.region;
    const previousPlayer = (previous.players || []).find(player => player.id === incoming.you);
    if (previousPlayer) {
      merged.players = (incoming.players || []).map(player => player.id === incoming.you
        ? { ...previousPlayer, ...player }
        : player);
    }
    return merged;
  }

  function createMinimapRefreshGate(intervalMs = 100) {
    const interval = Math.max(0, Number(intervalMs) || 0);
    let lastAt = -Infinity;
    let lastRegion = null;
    return function shouldRefresh(nowMs, regionId) {
      if (!regionId) {
        lastAt = -Infinity;
        lastRegion = null;
        return false;
      }
      if (regionId !== lastRegion || nowMs - lastAt >= interval) {
        lastAt = nowMs;
        lastRegion = regionId;
        return true;
      }
      return false;
    };
  }

  return { regionId, accepts, mergeSnapshot, createMinimapRefreshGate };
});
