import * as maplibregl from 'maplibre-gl';
import {MapboxOverlay} from '@deck.gl/mapbox';
import {ScatterplotLayer, TextLayer} from '@deck.gl/layers';
import {TripsLayer} from '@deck.gl/geo-layers';
import {buildOperationalBrief, buildSourceHealth, classifyMatch, summarizeMatches} from './intelligence.js';
import './styles.css';

const search = new URLSearchParams(window.location.search);
const API_BASE = (
  search.get('api') || import.meta.env.VITE_AGROLOG_GATEWAY_URL || (import.meta.env.DEV ? 'http://localhost:8080' : window.location.origin)
).replace(/\/$/, '');
const MAP_STYLE = search.get('style') || import.meta.env.VITE_MAP_STYLE_URL || 'https://demotiles.maplibre.org/style.json';

const els = {
  port: document.querySelector('#port-select'),
  refresh: document.querySelector('#refresh-button'),
  status: document.querySelector('#connection-status'),
  mapEmpty: document.querySelector('#map-empty'),
  lastUpdate: document.querySelector('#last-update'),
  detail: document.querySelector('#vessel-detail'),
  replayButton: document.querySelector('#replay-button'),
  replayControls: document.querySelector('#replay-controls'),
  replayToggle: document.querySelector('#replay-toggle'),
  replaySlider: document.querySelector('#replay-slider'),
  replayTime: document.querySelector('#replay-time'),
  lineupBody: document.querySelector('#lineup-body'),
  lineupCount: document.querySelector('#lineup-count'),
  sourceHealthList: document.querySelector('#source-health-list'),
  briefBody: document.querySelector('#brief-body'),
  briefGenerated: document.querySelector('#brief-generated'),
  metrics: {
    live: document.querySelector('#metric-live'),
    approach: document.querySelector('#metric-approach'),
    waiting: document.querySelector('#metric-waiting'),
    berthed: document.querySelector('#metric-berthed'),
    lineup: document.querySelector('#metric-lineup'),
    match: document.querySelector('#metric-match'),
    p50: document.querySelector('#metric-p50'),
    p90: document.querySelector('#metric-p90'),
    eta: document.querySelector('#metric-eta'),
    berth: document.querySelector('#metric-berth'),
  },
};

const state = {
  vessels: [],
  lineup: [],
  summary: {},
  sourceHealth: [],
  selected: null,
  replay: null,
  replayCurrent: 0,
  replayPlaying: false,
  replayLastFrame: null,
  replayFrame: null,
};

const map = new maplibregl.Map({
  container: 'map',
  style: MAP_STYLE,
  center: [-52, -15],
  zoom: 3.7,
  attributionControl: true,
});
map.addControl(new maplibregl.NavigationControl({showCompass: true}), 'top-right');

const overlay = new MapboxOverlay({interleaved: true, layers: []});
map.addControl(overlay);

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function fmtNumber(value, decimals = 0) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toLocaleString('pt-BR', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
}

function fmtTs(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('pt-BR', {
    timeZone: 'America/Cuiaba',
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
}

function freshnessClass(value) {
  const minutes = Number(value);
  if (!Number.isFinite(minutes)) return 'freshness-unknown';
  if (minutes <= 15) return 'freshness-good';
  if (minutes <= 60) return 'freshness-warn';
  return 'freshness-bad';
}

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

async function requestJson(path) {
  const response = await fetch(apiUrl(path), {headers: {'Accept': 'application/json'}});
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${body || response.statusText}`);
  }
  return response.json();
}

function setStatus(kind, text) {
  els.status.dataset.state = kind;
  els.status.textContent = text;
}

function vesselLabel(vessel) {
  return vessel.name || vessel.vessel_name || vessel.mmsi || 'Sem identificação';
}

function vesselPoint(vessel) {
  const lon = Number(vessel.lon ?? vessel.longitude);
  const lat = Number(vessel.lat ?? vessel.latitude);
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
  return [lon, lat];
}

function renderMetrics(summary = {}) {
  const metrics = els.metrics;
  metrics.live.textContent = fmtNumber(summary.vessels_live ?? state.vessels.length);
  metrics.approach.textContent = fmtNumber(summary.approaching ?? 0);
  metrics.waiting.textContent = fmtNumber(summary.waiting ?? 0);
  metrics.berthed.textContent = fmtNumber(summary.berthed ?? 0);
  metrics.lineup.textContent = fmtNumber(summary.lineup_total ?? state.lineup.length);
  metrics.match.textContent = `${fmtNumber((summary.match_rate ?? 0) * 100, 0)}%`;
  metrics.p50.textContent = summary.wait_p50_hours == null ? '—' : `${fmtNumber(summary.wait_p50_hours, 1)} h`;
  metrics.p90.textContent = summary.wait_p90_hours == null ? '—' : `${fmtNumber(summary.wait_p90_hours, 1)} h`;
  metrics.eta.textContent = summary.eta_next ? fmtTs(summary.eta_next) : '—';
  metrics.berth.textContent = summary.berth_next ? fmtTs(summary.berth_next) : '—';
}

function renderVessels() {
  const positions = [];
  const labels = [];
  for (const vessel of state.vessels) {
    const point = vesselPoint(vessel);
    if (!point) continue;
    const selected = state.selected && (state.selected.mmsi === vessel.mmsi || state.selected.imo === vessel.imo);
    positions.push({position: point, vessel, selected});
    labels.push({position: point, label: vesselLabel(vessel), vessel});
  }

  const layers = [
    new ScatterplotLayer({
      id: 'vessels',
      data: positions,
      getPosition: (d) => d.position,
      getRadius: (d) => d.selected ? 1100 : 700,
      radiusMinPixels: (d) => d.selected ? 8 : 5,
      radiusMaxPixels: 18,
      getFillColor: [70, 160, 255, 220],
      pickable: true,
      autoHighlight: true,
      onClick: ({object}) => {
        if (!object) return;
        state.selected = object.vessel;
        renderDetail(object.vessel);
        renderVessels();
      },
    }),
    new TextLayer({
      id: 'vessel-labels',
      data: labels,
      getPosition: (d) => d.position,
      getText: (d) => d.label,
      getSize: 12,
      getPixelOffset: [0, 14],
      getColor: [230, 238, 247, 220],
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'top',
      billboard: true,
    }),
  ];

  if (state.replay && Array.isArray(state.replay.trips)) {
    layers.push(new TripsLayer({
      id: 'replay-trips',
      data: state.replay.trips,
      getPath: (d) => d.path,
      getTimestamps: (d) => d.timestamps,
      getColor: [255, 176, 64],
      opacity: 0.7,
      widthMinPixels: 2,
      trailLength: 3600,
      currentTime: state.replayCurrent,
    }));
  }

  overlay.setProps({layers});
  els.mapEmpty.hidden = positions.length > 0;
}

function renderDetail(vessel) {
  if (!vessel) {
    els.detail.innerHTML = '<p>Selecione um navio no mapa.</p>';
    return;
  }
  const match = classifyMatch(vessel);
  els.detail.innerHTML = `
    <div class="detail-head">
      <strong>${escapeHtml(vesselLabel(vessel))}</strong>
      <span class="badge ${escapeHtml(match.className)}">${escapeHtml(match.label)}</span>
    </div>
    <dl>
      <div><dt>MMSI</dt><dd>${escapeHtml(vessel.mmsi || '—')}</dd></div>
      <div><dt>IMO</dt><dd>${escapeHtml(vessel.imo || '—')}</dd></div>
      <div><dt>Status</dt><dd>${escapeHtml(vessel.status || vessel.lifecycle || '—')}</dd></div>
      <div><dt>Destino AIS</dt><dd>${escapeHtml(vessel.destination || '—')}</dd></div>
      <div><dt>ETA</dt><dd>${escapeHtml(fmtTs(vessel.eta))}</dd></div>
      <div><dt>Última posição</dt><dd>${escapeHtml(fmtTs(vessel.timestamp || vessel.position_timestamp))}</dd></div>
    </dl>
  `;
}

function renderLineup() {
  els.lineupCount.textContent = fmtNumber(state.lineup.length);
  els.lineupBody.innerHTML = state.lineup.map((item) => {
    const programmed = item.programmed_tonnes ?? item.tonnes ?? item.quantity;
    const realized = item.realized_tonnes;
    return `
      <tr>
        <td>${escapeHtml(item.vessel_name || item.name || item.imo || '—')}</td>
        <td>${escapeHtml(item.product || item.cargo || '—')}</td>
        <td>${escapeHtml(item.terminal || item.berth || '—')}</td>
        <td>${escapeHtml(item.status || 'programado')}</td>
        <td class="num">${programmed == null ? '—' : escapeHtml(fmtNumber(programmed))}</td>
        <td class="num">${realized == null ? '—' : escapeHtml(fmtNumber(realized))}</td>
        <td>${escapeHtml(fmtTs(item.eta || item.arrival || item.expected_at))}</td>
      </tr>`;
  }).join('') || '<tr><td colspan="7" class="empty-cell">Sem line-up disponível.</td></tr>';
}

function renderSourceHealth() {
  const rows = buildSourceHealth(state.sourceHealth);
  els.sourceHealthList.innerHTML = rows.map((item) => `
    <li>
      <span class="source-name">${escapeHtml(item.name)}</span>
      <span class="source-age ${freshnessClass(item.ageMinutes)}">${escapeHtml(item.ageLabel)}</span>
      <span class="source-state">${escapeHtml(item.stateLabel)}</span>
    </li>
  `).join('') || '<li class="empty-cell">Sem telemetria de fontes.</li>';
}

function renderBrief() {
  const matchSummary = summarizeMatches(state.vessels, state.lineup);
  const brief = buildOperationalBrief({
    port: els.port.value,
    vessels: state.vessels,
    lineup: state.lineup,
    summary: state.summary,
    sourceHealth: state.sourceHealth,
    matchSummary,
  });
  els.briefGenerated.textContent = fmtTs(brief.generatedAt);
  els.briefBody.innerHTML = brief.sections.map((section) => `
    <section>
      <h3>${escapeHtml(section.title)}</h3>
      <p>${escapeHtml(section.body)}</p>
    </section>
  `).join('');
}

function normalizeReplay(payload) {
  if (!payload) return null;
  if (Array.isArray(payload.trips)) return payload;
  if (!Array.isArray(payload.points)) return null;
  const byVessel = new Map();
  for (const row of payload.points) {
    const key = row.mmsi || row.imo || row.vessel_name;
    const point = vesselPoint(row);
    const timestamp = new Date(row.timestamp || row.position_timestamp).getTime() / 1000;
    if (!key || !point || !Number.isFinite(timestamp)) continue;
    if (!byVessel.has(key)) byVessel.set(key, []);
    byVessel.get(key).push({point, timestamp});
  }
  const trips = [...byVessel.entries()].map(([id, rows]) => {
    rows.sort((a, b) => a.timestamp - b.timestamp);
    return {id, path: rows.map((row) => row.point), timestamps: rows.map((row) => row.timestamp)};
  });
  return {trips};
}

async function loadReplay() {
  const port = encodeURIComponent(els.port.value);
  try {
    const payload = await requestJson(`/v1/maritime/replay?port=${port}&hours=24`);
    state.replay = normalizeReplay(payload);
    const timestamps = state.replay?.trips?.flatMap((trip) => trip.timestamps) || [];
    if (!timestamps.length) throw new Error('Sem posições de replay');
    const min = Math.min(...timestamps);
    const max = Math.max(...timestamps);
    els.replaySlider.min = String(min);
    els.replaySlider.max = String(max);
    els.replaySlider.value = String(min);
    els.replayControls.hidden = false;
    updateReplay(min);
  } catch (error) {
    state.replay = null;
    els.replayControls.hidden = true;
    setStatus('warn', `Replay indisponível: ${error.message}`);
  }
}

function updateReplay(value) {
  state.replayCurrent = Number(value);
  els.replaySlider.value = String(state.replayCurrent);
  els.replayTime.textContent = fmtTs(new Date(state.replayCurrent * 1000).toISOString());
  renderVessels();
}

function tickReplay(timestamp) {
  if (!state.replayPlaying) return;
  if (state.replayLastFrame == null) state.replayLastFrame = timestamp;
  const delta = (timestamp - state.replayLastFrame) / 1000;
  state.replayLastFrame = timestamp;
  const speed = 120;
  const max = Number(els.replaySlider.max);
  const next = state.replayCurrent + delta * speed;
  if (next >= max) {
    updateReplay(max);
    state.replayPlaying = false;
    els.replayToggle.textContent = '▶';
    return;
  }
  updateReplay(next);
  state.replayFrame = requestAnimationFrame(tickReplay);
}

function toggleReplay() {
  state.replayPlaying = !state.replayPlaying;
  els.replayToggle.textContent = state.replayPlaying ? '❚❚' : '▶';
  state.replayLastFrame = null;
  if (state.replayPlaying) state.replayFrame = requestAnimationFrame(tickReplay);
  else if (state.replayFrame) cancelAnimationFrame(state.replayFrame);
}

async function refresh() {
  const port = encodeURIComponent(els.port.value);
  setStatus('loading', 'Atualizando');
  els.refresh.disabled = true;
  try {
    const [live, lineup, summary, health] = await Promise.all([
      requestJson(`/v1/maritime/live?port=${port}&limit=500`),
      requestJson(`/v1/maritime/lineup?port=${port}&limit=500`),
      requestJson(`/v1/maritime/summary?port=${port}`),
      requestJson(`/v1/maritime/source-health?port=${port}`),
    ]);
    state.vessels = live.items || live.vessels || [];
    state.lineup = lineup.items || lineup.lineup || [];
    state.summary = summary || {};
    state.sourceHealth = health.items || health.sources || [];
    renderMetrics(state.summary);
    renderVessels();
    renderLineup();
    renderSourceHealth();
    renderBrief();
    els.lastUpdate.textContent = fmtTs(new Date().toISOString());
    setStatus('ok', 'Conectado');
  } catch (error) {
    setStatus('error', `Gateway indisponível: ${error.message}`);
  } finally {
    els.refresh.disabled = false;
  }
}

els.port.addEventListener('change', async () => {
  state.selected = null;
  state.replay = null;
  els.replayControls.hidden = true;
  await refresh();
});
els.refresh.addEventListener('click', refresh);
els.replayButton.addEventListener('click', loadReplay);
els.replayToggle.addEventListener('click', toggleReplay);
els.replaySlider.addEventListener('input', (event) => updateReplay(event.target.value));

map.on('load', refresh);
