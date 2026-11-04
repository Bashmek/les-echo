const test = require('node:test');
const assert = require('node:assert/strict');
const MapEvents = require('../static/map-events.js');

test('snapshot region metadata is read by id, not compared as an object', () => {
  const snapshot = { type: 'state', region: { id: 'camp', name: 'Лагерь' } };
  assert.equal(MapEvents.regionId(snapshot), 'camp');
  assert.equal(MapEvents.accepts(snapshot, 'camp'), true);
});

test('a snapshot for the new map is accepted during travel', () => {
  const snapshot = { type: 'state', region: { id: 'forest' } };
  assert.equal(MapEvents.accepts(snapshot, 'camp'), true);
});

test('combat events from another map are rejected', () => {
  assert.equal(MapEvents.accepts({ type: 'hit', region: 'forest' }, 'camp'), false);
  assert.equal(MapEvents.accepts({ type: 'hit', region: 'camp' }, 'camp'), true);
});

test('global and targeted account events are not map-filtered', () => {
  for (const type of ['notice', 'chat', 'stats_updated', 'player_update', 'region_changed']) {
    assert.equal(MapEvents.accepts({ type }, 'camp'), true);
  }
});

test('events are accepted before the first snapshot arrives', () => {
  assert.equal(MapEvents.accepts({ type: 'hit', region: 'forest' }, null), true);
});
