const test = require('node:test');
const assert = require('node:assert/strict');
const {filterStations, cheapestIds, clusterStations} = require('../app/static/overview.js');
const stations = [
  {id: 'a', name: 'Zentrum', brand: 'Alpha', street: 'Nordweg', place: 'Berlin', price: 1.7, distance_km: 2, is_open: true},
  {id: 'b', name: 'West', brand: 'Beta', street: 'Südweg', place: 'Bielefeld', price: 1.7, distance_km: 1, is_open: false},
  {id: 'c', name: 'Ost', brand: 'Alpha', street: 'Hafen', place: 'Bielefeld', price: 1.8, distance_km: .5, is_open: true},
];
const filters = {search: '', brand: '', openOnly: false, favoritesOnly: false, distance: 5, sort: 'price'};
test('search covers all four fields and filters combine', () => {
  assert.deepEqual(filterStations(stations, {...filters, search: 'BIELEFELD', brand: 'Alpha', openOnly: true}, new Set()).map(s => s.id), ['c']);
  assert.deepEqual(filterStations(stations, {...filters, search: 'nordweg'}, new Set()).map(s => s.id), ['a']);
  assert.deepEqual(filterStations(stations, {...filters, distance: .4}, new Set()), []);
});
test('sorts consistently and favorites filtering does not change prices', () => {
  const favorites = new Set(['c']);
  assert.deepEqual(filterStations(stations, filters, favorites).map(s => s.id), ['b', 'a', 'c']);
  assert.deepEqual(filterStations(stations, {...filters, sort: 'distance'}, favorites).map(s => s.id), ['c', 'b', 'a']);
  assert.deepEqual(filterStations(stations, {...filters, sort: 'favorites'}, favorites).map(s => s.id), ['c', 'b', 'a']);
  assert.deepEqual(filterStations(stations, {...filters, favoritesOnly: true}, favorites).map(s => s.id), ['c']);
});
test('every minimum price is marked, including ties and filtered subsets', () => {
  assert.deepEqual([...cheapestIds(stations)].sort(), ['a', 'b']);
  assert.deepEqual([...cheapestIds(stations.slice(2))], ['c']);
  assert.equal(cheapestIds([]).size, 0);
});
test('dense stations cluster while selection remains individual', () => {
  const project = () => ({x: 10, y: 10});
  assert.deepEqual(clusterStations(stations, project, null, 12).map(g => g.length), [3]);
  const selected = clusterStations(stations, project, 'b', 12);
  assert.equal(selected.find(g => g.some(s => s.id === 'b')).length, 1);
  assert.deepEqual(clusterStations(stations, project, null, 17).map(g => g.length), [1, 1, 1]);
  assert.deepEqual(clusterStations([], project, null, 12), []);
});
