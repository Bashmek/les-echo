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

  return { regionId, accepts };
});
