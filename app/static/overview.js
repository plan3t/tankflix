/* One station identity and one filtered data set drive the list, map and comparison. */
(() => {
  'use strict';
  const priceOrder = (a, b) => a.price - b.price || a.distance_km - b.distance_km || a.id.localeCompare(b.id);
  function filterStations(stations, filters, favorites) {
    const query = filters.search.trim().toLocaleLowerCase('de-DE');
    return stations.filter(s => (!filters.openOnly || s.is_open)
      && (!filters.brand || s.brand === filters.brand)
      && s.distance_km <= filters.distance
      && (!filters.favoritesOnly || favorites.has(s.id))
      && (!query || [s.name, s.brand, s.street, s.place].join(' ').toLocaleLowerCase('de-DE').includes(query)))
      .sort((a, b) => (filters.sort === 'distance' ? a.distance_km - b.distance_km
        : filters.sort === 'favorites' ? Number(favorites.has(b.id)) - Number(favorites.has(a.id)) : 0) || priceOrder(a, b));
  }
  function cheapestIds(stations) {
    const min = Math.min(...stations.map(s => Math.round(s.price * 1000)));
    return new Set(stations.filter(s => Math.round(s.price * 1000) === min).map(s => s.id));
  }
  function clusterStations(stations, project, selectedId, zoom, expandedIds = new Set()) {
    const groups = new Map();
    stations.forEach(s => {
      const point = project(s);
      const key = zoom >= 17 || s.id === selectedId || expandedIds.has(s.id) ? `station:${s.id}` : `${Math.floor(point.x / 88)}:${Math.floor(point.y / 72)}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(s);
    });
    return Array.from(groups.values());
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {filterStations, cheapestIds, clusterStations};
    return;
  }

  const data = JSON.parse(document.getElementById('overview-data').textContent);
  const stationsById = new Map(data.stations.map(s => [s.id, s]));
  const rows = new Map(Array.from(document.querySelectorAll('[data-station-row]')).map(row => [row.dataset.id, row]));
  const $ = id => document.getElementById(id);
  const price = value => Number(value).toLocaleString('de-DE', {minimumFractionDigits: 3, maximumFractionDigits: 3}) + ' €/L';
  const distance = value => Number(value).toLocaleString('de-DE', {maximumFractionDigits: 2}) + ' km Luftlinie';
  const date = value => value ? new Intl.DateTimeFormat('de-DE', {dateStyle: 'short', timeStyle: 'short'}).format(new Date(value)) : 'Noch keiner';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const scrollTo = element => element.scrollIntoView({behavior: reducedMotion ? 'instant' : 'smooth', block: 'center'});
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  function readStorage(key, fallback, session = false) {
    try { return JSON.parse((session ? sessionStorage : localStorage).getItem(key)) ?? fallback; }
    catch { return fallback; }
  }
  function writeStorage(key, value, session = false) {
    try { (session ? sessionStorage : localStorage).setItem(key, JSON.stringify(value)); }
    catch { /* Private browsing may disable persistence; the current view still works. */ }
  }
  const storedFavorites = readStorage('tankflix-favorites', []);
  const favorites = new Set(Array.isArray(storedFavorites) ? storedFavorites.filter(id => typeof id === 'string') : []);
  const savedView = readStorage('tankflix-view', {}, true);
  const view = savedView && typeof savedView === 'object' ? savedView : {};
  let selectedId = typeof view.selectedId === 'string' ? view.selectedId : null;
  let filtered = [];
  let best = new Set();
  let map = null;
  let markerGroup = null;
  let markers = new Map();
  let popupWanted = null;
  let renderingMap = false;
  const expandedIds = new Set();
  let expandedAtZoom = 0;
  const validLocation = s => Number.isFinite(s.lat) && Number.isFinite(s.lng) && Math.abs(s.lat) <= 90 && Math.abs(s.lng) <= 180 && !(s.lat === 0 && s.lng === 0);
  function routeLink(s) {
    const link = element('a', 'Route starten', 'btn-link secondary');
    if (validLocation(s)) {
      const url = new URL('https://www.google.com/maps/dir/');
      url.search = new URLSearchParams({api: '1', destination: `${s.lat},${s.lng}`, travelmode: 'driving'});
      link.href = url.toString();
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.setAttribute('aria-label', `Route zu ${s.name} starten (neuer Tab)`);
    } else {
      link.textContent = 'Kein Standort verfügbar';
      link.setAttribute('aria-disabled', 'true');
    }
    return link;
  }
  function actionButton(text, action, s, secondary = false) {
    const button = element('button', text, secondary ? 'secondary' : '');
    button.type = 'button';
    button.dataset.action = action;
    button.dataset.id = s.id;
    if (action === 'map') button.disabled = !map || !validLocation(s);
    return button;
  }
  function saveView() {
    writeStorage('tankflix-view', {...getFilters(), selectedId, mapOpen: $('map-panel').open}, true);
  }
  function getFilters() {
    return {search: $('station-search').value, brand: $('brand-filter').value,
      openOnly: $('open-only').checked, favoritesOnly: $('favorites-only').checked,
      distance: Number($('distance-filter').value), sort: $('sort-order').value};
  }
  function selectionStatus() {
    const station = stationsById.get(selectedId);
    $('selection-status').textContent = station
      ? `${filtered.some(s => s.id === selectedId) ? 'Ausgewählt' : 'Auswahl durch Filter ausgeblendet'}: ${station.name} · ${price(station.price)}`
      : selectedId ? 'Die ausgewählte Tankstelle ist für diesen Kraftstoff nicht verfügbar.' : 'Keine Tankstelle ausgewählt.';
    rows.forEach((row, id) => {
      const selected = id === selectedId;
      row.classList.toggle('selected-station', selected);
      row.querySelector('.selection-badge').hidden = !selected;
    });
  }
  function selectStation(id, target) {
    const station = stationsById.get(id);
    if (!station) return;
    selectedId = id;
    popupWanted = target === 'map' || target === 'marker' ? id : null;
    selectionStatus();
    renderComparison();
    saveView();
    if (target === 'map' && map && validLocation(station)) {
      $('map-panel').open = true;
      saveView();
      map.invalidateSize();
      map.setView([station.lat, station.lng], Math.max(map.getZoom(), 16), {animate: false});
      scrollTo($('map-panel'));
    }
    renderMarkers();
    if (target === 'list') {
      const row = rows.get(id);
      scrollTo(row);
      row.focus({preventScroll: true});
    } else if (target === 'map' || target === 'marker') {
      const button = document.querySelector('.leaflet-popup [data-action="list"]');
      button?.focus({preventScroll: true});
    }
  }
  function popup(station) {
    const body = element('div', null, 'station-popup');
    body.append(element('strong', station.name), element('p', price(station.price)),
      element('p', `${station.street} ${station.place}`), element('p', distance(station.distance_km)));
    if (best.has(station.id)) body.append(element('span', '★ Günstigste', 'badge best'));
    if (station.id === selectedId) body.append(element('span', '● Ausgewählt', 'badge selected-label'));
    body.append(actionButton('Zur Liste', 'list', station), routeLink(station), actionButton('Details & Verlauf', 'details', station, true));
    return body;
  }
  function markerKeyboard(marker, activate) {
    marker.getElement()?.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      event.stopPropagation();
      activate();
    });
  }
  function renderMarkers() {
    if (!map || renderingMap) return;
    renderingMap = true;
    try {
      markerGroup.clearLayers();
      markers = new Map();
      const groups = clusterStations(filtered.filter(validLocation), s => map.project([s.lat, s.lng]), selectedId, map.getZoom(), expandedIds);
      groups.forEach(group => {
        if (group.length > 1) {
          const center = [group.reduce((sum, s) => sum + s.lat, 0) / group.length, group.reduce((sum, s) => sum + s.lng, 0) / group.length];
          const minimum = group.reduce((a, b) => priceOrder(a, b) <= 0 ? a : b);
          const label = `${group.length} Tankstellen, ab ${price(minimum.price)}. Zum Vergrößern aktivieren.`;
          const node = element('div', null, 'cluster-label');
          node.append(element('strong', `${group.length} Tankstellen`), element('span', `ab ${price(minimum.price)}`));
          if (group.some(s => best.has(s.id))) node.append(element('span', '★ Bestpreis'));
          const marker = L.marker(center, {icon: L.divIcon({html: node, className: 'cluster-icon', iconSize: [118, 64], iconAnchor: [59, 32]}), title: label, alt: label}).addTo(markerGroup);
          const expandGroup = () => {
            group.forEach(s => expandedIds.add(s.id));
            map.fitBounds(L.latLngBounds(group.map(s => [s.lat, s.lng])), {padding: [60, 60], maxZoom: 17, animate: false});
            expandedAtZoom = map.getZoom();
            renderMarkers();
            map.getContainer().focus({preventScroll: true});
          };
          marker.on('click', expandGroup);
          markerKeyboard(marker, expandGroup);
          marker.getElement()?.setAttribute('aria-label', label);
          return;
        }
        const station = group[0];
        const selected = station.id === selectedId;
        const node = element('div', null, `price-marker${best.has(station.id) ? ' is-best' : ''}${selected ? ' is-selected' : ''}`);
        node.append(element('strong', price(station.price)));
        if (best.has(station.id)) node.append(element('span', '★ Günstigste'));
        if (selected) node.append(element('span', '● Ausgewählt'));
        const label = `${station.name}, ${price(station.price)}${best.has(station.id) ? ', Günstigste' : ''}${selected ? ', ausgewählt' : ''}`;
        const marker = L.marker([station.lat, station.lng], {icon: L.divIcon({html: node, className: 'price-icon', iconSize: [112, 60], iconAnchor: [56, 30]}), title: label, alt: label, zIndexOffset: selected ? 1000 : best.has(station.id) ? 500 : 0}).addTo(markerGroup);
        marker.bindPopup(popup(station), {autoPan: true, autoPanPadding: [14, 14], maxWidth: 280, maxHeight: 220});
        marker.bindTooltip(element('span', station.name));
        marker.on('click', () => selectStation(station.id, 'marker'));
        markerKeyboard(marker, () => selectStation(station.id, 'marker'));
        marker.on('popupclose', () => { if (!renderingMap) popupWanted = null; });
        marker.getElement()?.setAttribute('aria-label', label);
        marker.getElement()?.setAttribute('aria-pressed', String(selected));
        markers.set(station.id, marker);
      });
      if (popupWanted) markers.get(popupWanted)?.openPopup();
    } finally { renderingMap = false; }
  }
  function renderComparison() {
    const visible = filtered.filter(s => favorites.has(s.id)).sort(priceOrder);
    const favoriteBest = cheapestIds(visible);
    const container = $('favorite-comparison');
    container.replaceChildren();
    $('favorite-summary').textContent = favorites.size
      ? `${visible.length} sichtbare von ${favorites.size} gespeicherten Favoriten. Aktueller Kraftstoff und alle Filter gelten auch hier.`
      : 'Markiere Tankstellen mit dem Stern, um sie hier zu vergleichen.';
    visible.forEach(station => {
      const card = element('article', null, 'favorite-card');
      card.classList.toggle('selected-station', station.id === selectedId);
      card.append(element('h4', station.name), element('strong', price(station.price)), element('p', distance(station.distance_km)));
      if (favoriteBest.has(station.id)) card.append(element('span', '★ Günstigster Favorit', 'badge best'));
      const actions = element('div', null, 'station-actions');
      actions.append(actionButton('Auf Karte zeigen', 'map', station), actionButton('Details & Verlauf', 'details', station, true), routeLink(station));
      card.append(actions);
      container.append(card);
    });
    $('show-favorite').disabled = !map || !visible.some(validLocation);
  }
  function applyFilters() {
    filtered = filterStations(data.stations, getFilters(), favorites);
    best = cheapestIds(filtered);
    const visibleIds = new Set(filtered.map(s => s.id));
    const body = document.querySelector('#stations-table tbody');
    rows.forEach((row, id) => {
      row.hidden = !visibleIds.has(id);
      row.querySelector('.best-badge').hidden = !best.has(id);
      const button = row.querySelector('.fav-btn');
      button.textContent = favorites.has(id) ? '★' : '☆';
      button.classList.toggle('active', favorites.has(id));
      button.setAttribute('aria-pressed', String(favorites.has(id)));
      button.setAttribute('aria-label', `${stationsById.get(id).name} ${favorites.has(id) ? 'aus Favoriten entfernen' : 'als Favorit markieren'}`);
    });
    filtered.forEach(s => body.append(rows.get(s.id)));
    $('distance-value').textContent = Number($('distance-filter').value).toLocaleString('de-DE', {minimumFractionDigits: 1});
    $('result-count').textContent = `${filtered.length} von ${data.stations.length} Tankstellen · ${$('sort-order').selectedOptions[0].textContent}${filtered.length ? ` · Bestpreis ${price(Math.min(...filtered.map(s => s.price)))}` : ''}`;
    $('show-cheapest').disabled = !map || !filtered.some(s => best.has(s.id) && validLocation(s));
    $('filter-empty').hidden = filtered.length > 0;
    if (data.stations.length) $('empty-reason').textContent = 'Keine Treffer für diese Filter. Suche oder Filter zurücksetzen, um weitere Tankstellen zu sehen.';
    selectionStatus();
    renderComparison();
    renderMarkers();
    saveView();
    updateFreshness();
  }
  function updateFreshness() {
    const lastSuccess = data.health.last_success_at;
    $('stale-warning').hidden = !lastSuccess || Date.now() - Date.parse(lastSuccess) <= data.staleSeconds * 1000;
    rows.forEach((row, id) => {
      const stale = Date.now() - Date.parse(stationsById.get(id).fetched_at) > data.staleSeconds * 1000;
      row.querySelector('.stale-badge').hidden = !stale;
    });
  }

  let detailStation = null;
  let historyRequest = null;
  let historyGeneration = 0;
  function showDetails(station) {
    selectStation(station.id, 'details');
    detailStation = station;
    $('detail-title').textContent = `${station.name} · ${data.fuel.toUpperCase()}`;
    $('detail-address').textContent = `${station.brand} · ${station.street} ${station.place}`;
    $('detail-price').textContent = `${price(station.price)} · ${distance(station.distance_km)} · ${station.is_open ? 'Offen' : 'Geschlossen'}`;
    $('detail-freshness').textContent = `Preisstand: ${date(station.fetched_at)}${Date.now() - Date.parse(station.fetched_at) > data.staleSeconds * 1000 ? ' · Preis veraltet' : ''}`;
    const meta = station.meta;
    const alerts = $('detail-alerts');
    alerts.replaceChildren();
    alerts.append(element('li', `Preisgrenze: ${price(meta.threshold)}. Aktuell ${meta.below_threshold ? 'erreicht oder unterschritten' : 'überschritten'}.`));
    alerts.append(element('li', meta.delta_cents == null ? 'Für einen Preisvergleich fehlt ein früherer Messwert.'
      : `Änderung zum vorherigen Messwert (${date(meta.previous_at)}, ${price(meta.previous_price)}): ${meta.delta_cents > 0 ? '+' : ''}${meta.delta_cents.toLocaleString('de-DE')} Cent. Schwelle für starke Änderungen: ${meta.strong_change_cents.toLocaleString('de-DE')} Cent.${meta.strong_drop ? ' Starker Preisrückgang.' : meta.strong_rise ? ' Starker Preisanstieg.' : ''}`));
    alerts.append(element('li', data.teamsEnabled ? 'Teams-Benachrichtigungen sind aktiviert. Ein Preishinweis allein bestätigt keinen Versand.' : 'Teams-Benachrichtigungen sind deaktiviert. Preishinweise werden trotzdem angezeigt.'));
    if (meta.last_alert_at) alerts.append(element('li', `Letzter bestätigter Teams-Versand für einen Preisgrenzen- oder Änderungsalarm: ${date(meta.last_alert_at)}.`));
    $('detail-actions').replaceChildren(actionButton('Auf Karte zeigen', 'map', station), routeLink(station));
    $('history-period').value = '7';
    if (!$('station-details').open) $('station-details').showModal();
    loadHistory();
  }
  const svgElement = (tag, attributes, text) => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attributes || {}).forEach(([key, value]) => node.setAttribute(key, value));
    if (text != null) node.textContent = text;
    return node;
  };
  function drawHistory(points) {
    const chart = $('history-chart');
    chart.replaceChildren();
    if (!points.length) {
      $('history-status').textContent = 'Für diesen Zeitraum sind noch keine Messwerte vorhanden.';
      return;
    }
    const prices = points.map(p => p.price);
    const min = Math.min(...prices), max = Math.max(...prices);
    const times = points.map(p => Date.parse(p.at));
    const first = times[0], last = times[times.length - 1];
    const margin = Math.max(0.002, (max - min) * 0.15);
    const x = time => last === first ? 345 : 85 + (time - first) / (last - first) * 535;
    const y = value => 180 - (value - min + margin) / (max - min + 2 * margin) * 155;
    $('history-status').textContent = `${points.length} Messwerte · Minimum ${price(min)} · Maximum ${price(max)}. ${points.length === 1 ? 'Ein einzelner Messwert erlaubt noch keinen Trend.' : ''}`;
    chart.append(svgElement('title', {id: 'history-chart-title'}, `Preisverlauf ${detailStation.name}`),
      svgElement('desc', {id: 'history-chart-desc'}, `${points.length} Messwerte, von ${date(points[0].at)} bis ${date(points[points.length - 1].at)}. Preise zwischen ${price(min)} und ${price(max)}. Genaue Werte in der Tabelle darunter.`),
      svgElement('line', {x1: 85, x2: 620, y1: 180, y2: 180, class: 'chart-axis'}),
      svgElement('text', {x: 3, y: y(max), class: 'chart-label'}, price(max)),
      svgElement('text', {x: 3, y: y(min) + 12, class: 'chart-label'}, price(min)),
      svgElement('text', {x: 85, y: 210, class: 'chart-label'}, date(points[0].at)),
      svgElement('text', {x: 620, y: 210, 'text-anchor': 'end', class: 'chart-label'}, date(points[points.length - 1].at)),
      svgElement('polyline', {points: points.map(p => `${x(Date.parse(p.at))},${y(p.price)}`).join(' '), class: 'chart-line'}));
    if (points.length === 1) chart.append(svgElement('circle', {cx: x(first), cy: y(min), r: 4, class: 'chart-point'}));
    chart.removeAttribute('hidden');
    $('history-values').hidden = false;
    $('history-values-note').textContent = `Die letzten ${Math.min(100, points.length)} von ${points.length} Messwerten. Das Diagramm zeigt den gesamten gewählten Zeitraum.`;
    points.slice(-100).reverse().forEach(point => {
      const row = element('tr');
      row.append(element('td', date(point.at)), element('td', price(point.price)));
      $('history-table').append(row);
    });
  }
  async function loadHistory() {
    historyRequest?.abort();
    historyRequest = new AbortController();
    const generation = ++historyGeneration;
    $('history-status').textContent = 'Preisverlauf wird geladen …';
    $('history-chart').setAttribute('hidden', '');
    $('history-values').hidden = true;
    $('history-table').replaceChildren();
    try {
      const response = await fetch(`/api/stations/${encodeURIComponent(detailStation.id)}/history?fuel=${encodeURIComponent(data.fuel)}&days=${$('history-period').value}`, {signal: historyRequest.signal});
      if (!response.ok) throw new Error('History unavailable');
      const history = await response.json();
      if (generation !== historyGeneration || !$('station-details').open) return;
      drawHistory(history.points.filter(p => Number.isFinite(p.price) && Number.isFinite(Date.parse(p.at))));
    } catch (error) {
      if (error.name === 'AbortError' || generation !== historyGeneration || !$('station-details').open) return;
      $('history-status').textContent = 'Der Preisverlauf konnte nicht geladen werden. Die aktuellen Tankstellendaten bleiben verfügbar. ';
      const retry = element('button', 'Erneut laden', 'secondary');
      retry.type = 'button';
      retry.addEventListener('click', loadHistory);
      $('history-status').append(retry);
    }
  }
  function drawSparklines() {
    document.querySelectorAll('.sparkline').forEach(canvas => {
      const points = JSON.parse(canvas.dataset.points || '[]');
      if (points.length < 2) { canvas.hidden = true; return; }
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const min = Math.min(...points), max = Math.max(...points);
      ctx.strokeStyle = '#3b82f6';
      ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach((p, i) => {
        const x = i / (points.length - 1) * canvas.width;
        const y = max === min ? canvas.height / 2 : (max - p) / (max - min) * (canvas.height - 4) + 2;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });
  }

  $('station-search').value = typeof view.search === 'string' ? view.search : '';
  if (Array.from($('brand-filter').options).some(option => option.value === view.brand)) $('brand-filter').value = view.brand;
  $('open-only').checked = view.openOnly === true;
  $('favorites-only').checked = view.favoritesOnly === true;
  if (typeof view.distance === 'number' && Number.isFinite(view.distance)) $('distance-filter').value = String(Math.min(data.radius, Math.max(0, view.distance)));
  if (['price', 'distance', 'favorites'].includes(view.sort)) $('sort-order').value = view.sort;
  $('map-panel').open = view.mapOpen !== false;
  if (typeof L !== 'undefined') {
    try {
      // Immediate popup removal avoids ghost popups during marker reconciliation.
      map = L.map('station-map', {fadeAnimation: false}).setView(data.origin, 12);
      const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; OpenStreetMap'}).addTo(map);
      tiles.on('tileerror', () => { $('map-error').hidden = false; $('map-error').textContent = 'Der Kartenhintergrund ist nicht verfügbar. Tankstellenmarker, Liste und Routenlinks bleiben nutzbar.'; });
      L.marker(data.origin, {title: 'Ausgangspunkt', alt: 'Ausgangspunkt'}).addTo(map).bindPopup(element('span', 'Ausgangspunkt'));
      markerGroup = L.layerGroup().addTo(map);
      // Grouping uses world pixels, so panning does not require rebuilding markers.
      // Keeping them mounted also preserves popup/keyboard focus during auto-pan.
      map.on('zoomend', () => {
        if (map.getZoom() < expandedAtZoom) expandedIds.clear();
        renderMarkers();
      });
    } catch { map = null; $('map-error').hidden = false; }
  } else { $('map-error').hidden = false; $('station-map').hidden = true; }
  rows.forEach((row, id) => {
    const station = stationsById.get(id);
    row.querySelector('[data-action="map"]').disabled = !map || !validLocation(station);
    if (!validLocation(station)) row.querySelector('[data-action="route"]').replaceWith(routeLink(station));
  });
  document.querySelectorAll('time[datetime]').forEach(time => { time.textContent = date(time.dateTime); });
  ['station-search', 'brand-filter', 'distance-filter', 'sort-order', 'open-only', 'favorites-only'].forEach(id => $(id).addEventListener('input', applyFilters));
  $('reset-filters').addEventListener('click', () => {
    $('station-search').value = ''; $('brand-filter').value = '';
    $('open-only').checked = false; $('favorites-only').checked = false;
    $('distance-filter').value = String(data.radius); $('sort-order').value = 'price';
    applyFilters();
  });
  $('show-cheapest').addEventListener('click', () => {
    const station = filtered.filter(s => best.has(s.id) && validLocation(s)).sort(priceOrder)[0];
    if (station) selectStation(station.id, 'map');
  });
  $('show-favorite').addEventListener('click', () => {
    const station = filtered.filter(s => favorites.has(s.id) && validLocation(s)).sort(priceOrder)[0];
    if (station) selectStation(station.id, 'map');
  });
  $('map-panel').addEventListener('toggle', () => { saveView(); if ($('map-panel').open) map?.invalidateSize(); });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-action][data-id]');
    if (!button) return;
    const station = stationsById.get(button.dataset.id);
    if (!station) return;
    switch (button.dataset.action) {
      case 'favorite':
        if (favorites.has(station.id)) favorites.delete(station.id); else favorites.add(station.id);
        writeStorage('tankflix-favorites', Array.from(favorites)); applyFilters(); break;
      case 'map':
        if ($('station-details').open) $('station-details').close();
        selectStation(station.id, 'map'); break;
      case 'list': selectStation(station.id, 'list'); break;
      case 'details': showDetails(station); break;
    }
  });
  $('close-details').addEventListener('click', () => $('station-details').close());
  $('station-details').addEventListener('close', () => { historyRequest?.abort(); ++historyGeneration; });
  $('history-period').addEventListener('change', loadHistory);
  window.addEventListener('storage', event => {
    if (event.key !== 'tankflix-favorites') return;
    const saved = readStorage('tankflix-favorites', []);
    favorites.clear();
    if (Array.isArray(saved)) saved.filter(id => typeof id === 'string').forEach(id => favorites.add(id));
    applyFilters();
  });
  drawSparklines();
  applyFilters();
  setInterval(updateFreshness, 60000);
})();
