import maplibregl from 'maplibre-gl';
import {MapboxOverlay} from '@deck.gl/mapbox';
import {ScatterplotLayer, TextLayer} from '@deck.gl/layers';
import {TripsLayer} from '@deck.gl/geo-layers';
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
  metrics: {
    live: document.querySelector('#metric-live'),
    approach: document.querySelector('#metric-approach'),
    waiting: document.querySelector('#metric-waiting'),
    berthed: document.querySelector('#metric-berthed'),
    lineup: document.querySelector('#metric-lineup'),
    match: document.querySelector('#metric-match'),
    p50: document.querySelector('#metric-p50'),
    p90: document.querySelector('#metric-p90'),
  },
};

const state = {
  vessels: [],
  lineup: [],
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
  return new Intl.NumberFormat('pt-BR', {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(number);
}

function fmtHours(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${fmtNumber(number, 1)} h` : '—';
}

function fmtDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(date);
}

function zoneColor(zone) {
  switch (String(zone || '').toUpperCase()) {
    case 'APPROACH': return [247, 186, 85, 235];
    case 'ANCHORAGE': return [240, 115, 101, 235];
    case 'BERTH': return [80, 201, 154, 235];
    default: return [107, 167, 219, 220];
  }
}

async function getJson(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(`${API_BASE}${path}`, {signal: controller.signal});
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`${response.status} ${detail}`);
    }
    return await response.json();
  } finally {
    clearTimeout(timeout);
  }
}

function setStatus(kind, text) {
  els.status.className = `status status-${kind}`;
  els.status.textContent = text;
}

function selectedPortQuery() {
  const value = els.port.value;
  return value ? `port_id=${encodeURIComponent(value)}&` : '';
}

function fitToVessels(vessels) {
  if (!vessels.length) return;
  const bounds = new maplibregl.LngLatBounds();
  let count = 0;
  for (const vessel of vessels) {
    const lon = Number(vessel.longitude);
    const lat = Number(vessel.latitude);
    if (Number.isFinite(lon) && Number.isFinite(lat)) {
      bounds.extend([lon, lat]);
      count += 1;
    }
  }
  if (!count || bounds.isEmpty()) return;
  if (count === 1) {
    map.easeTo({center: bounds.getCenter(), zoom: 10, duration: 650});
    return;
  }
  map.fitBounds(bounds, {padding: 70, maxZoom: 11, duration: 650});
}

function vesselLayers() {
  const selectedMmsi = state.selected?.mmsi;
  const layers = [
    new ScatterplotLayer({
      id: 'vessel-hit-area',
      data: state.vessels,
      getPosition: d => [Number(d.longitude), Number(d.latitude)],
      getRadius: 950,
      radiusMinPixels: 8,
      radiusMaxPixels: 18,
      getFillColor: d => zoneColor(d.zone).slice(0, 3).concat(45),
      getLineColor: d => zoneColor(d.zone),
      lineWidthMinPixels: 1,
      stroked: true,
      pickable: true,
      onClick: info => info.object && selectVessel(info.object),
    }),
    new TextLayer({
      id: 'vessel-symbols',
      data: state.vessels,
      getPosition: d => [Number(d.longitude), Number(d.latitude)],
      getText: () => '▲',
      getSize: d => d.mmsi === selectedMmsi ? 24 : 18,
      getColor: d => zoneColor(d.zone),
      getAngle: d => {
        const cog = Number(d.cog_deg);
        return Number.isFinite(cog) ? -cog : 0;
      },
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'center',
      billboard: false,
      pickable: true,
      onClick: info => info.object && selectVessel(info.object),
    }),
  ];

  if (state.selected) {
    layers.push(new ScatterplotLayer({
      id: 'selected-vessel',
      data: [state.selected],
      getPosition: d => [Number(d.longitude), Number(d.latitude)],
      getRadius: 1300,
      radiusMinPixels: 15,
      radiusMaxPixels: 26,
      getFillColor: [255, 255, 255, 15],
      getLineColor: [255, 255, 255, 235],
      lineWidthMinPixels: 2,
      stroked: true,
      pickable: false,
    }));
  }

  if (state.replay) {
    layers.push(new TripsLayer({
      id: 'selected-vessel-replay',
      data: [state.replay],
      getPath: d => d.path,
      getTimestamps: d => d.timestamps,
      getColor: [110, 207, 255],
      currentTime: state.replayCurrent,
      trailLength: Math.max(1800, Math.min(state.replay.maxTime, 6 * 3600)),
      widthMinPixels: 4,
      capRounded: true,
      jointRounded: true,
      fadeTrail: true,
      pickable: false,
    }));
  }
  return layers;
}

function renderMapLayers() {
  overlay.setProps({layers: vesselLayers()});
}

function renderVesselDetail() {
  const d = state.selected;
  if (!d) {
    els.detail.className = 'vessel-detail muted';
    els.detail.textContent = 'Clique em um navio no mapa.';
    els.replayButton.disabled = true;
    return;
  }
  els.detail.className = 'vessel-detail';
  const fields = [
    ['Navio', d.vessel_name || '—'],
    ['MMSI', d.mmsi || '—'],
    ['IMO', d.imo || '—'],
    ['Zona', d.zone || 'SEA'],
    ['Porto', d.port_id || '—'],
    ['Terminal', d.terminal_id || '—'],
    ['Velocidade', d.sog_kn == null ? '—' : `${fmtNumber(d.sog_kn, 1)} kn`],
    ['Rumo', d.cog_deg == null ? '—' : `${fmtNumber(d.cog_deg, 0)}°`],
    ['Destino AIS', d.destination || '—'],
    ['Observado em', fmtDate(d.observed_at)],
  ];
  els.detail.innerHTML = fields.map(([label, value]) => (
    `<div class="field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`
  )).join('');
  els.replayButton.disabled = !d.mmsi;
}

function selectVessel(vessel) {
  state.selected = vessel;
  stopReplay();
  renderVesselDetail();
  renderMapLayers();
}

function stateClass(value) {
  const stateValue = String(value || 'PROGRAMMED').toUpperCase();
  if (stateValue.includes('COMPLETED')) return 'completed';
  if (stateValue.includes('WAITING') || stateValue.includes('APPROACH')) return 'waiting';
  if (stateValue.includes('BERTH')) return 'berth';
  return 'programmed';
}

function renderLineup() {
  els.lineupCount.textContent = String(state.lineup.length);
  if (!state.lineup.length) {
    els.lineupBody.innerHTML = '<tr><td colspan="6" class="muted">Sem line-up no horizonte selecionado.</td></tr>';
    return;
  }
  els.lineupBody.innerHTML = state.lineup.map(row => {
    const match = row.match_confidence == null
      ? '—'
      : `${fmtNumber(Number(row.match_confidence) * 100, 0)}% ${row.match_method || ''}`.trim();
    const volume = row.planned_volume_t == null ? '—' : `${fmtNumber(row.planned_volume_t, 0)} t`;
    const reconciled = row.reconciled_state || 'PROGRAMMED';
    return `<tr>
      <td><strong>${escapeHtml(row.vessel_name || '—')}</strong><br><span class="muted">${escapeHtml(row.imo || row.mmsi || '')}</span></td>
      <td>${escapeHtml(fmtDate(row.eta))}</td>
      <td>${escapeHtml(row.product || '—')}</td>
      <td>${escapeHtml(volume)}</td>
      <td><span class="state ${stateClass(reconciled)}">${escapeHtml(reconciled)}</span><br><span class="muted">${escapeHtml(row.evidence_class || '')}</span></td>
      <td>${escapeHtml(match)}</td>
    </tr>`;
  }).join('');
}

function renderSummary(summary = {}) {
  els.metrics.live.textContent = fmtNumber(summary.vessels_live);
  els.metrics.approach.textContent = fmtNumber(summary.vessels_approaching);
  els.metrics.waiting.textContent = fmtNumber(summary.vessels_waiting);
  els.metrics.berthed.textContent = fmtNumber(summary.vessels_berthed);
  els.metrics.lineup.textContent = fmtNumber(summary.lineup_calls);
  const calls = Number(summary.lineup_calls);
  const matched = Number(summary.lineup_matched);
  els.metrics.match.textContent = Number.isFinite(calls) && calls > 0 && Number.isFinite(matched)
    ? `${fmtNumber((matched / calls) * 100, 0)}%`
    : '—';
  els.metrics.p50.textContent = fmtHours(summary.waiting_p50_hours);
  els.metrics.p90.textContent = fmtHours(summary.waiting_p90_hours);
}

async function refreshAll({fit = false} = {}) {
  setStatus('idle', 'atualizando');
  els.refresh.disabled = true;
  try {
    const port = selectedPortQuery();
    const [vesselsResponse, lineupResponse, summaryResponse] = await Promise.all([
      getJson(`/v1/maritime/vessels?${port}hours=6&limit=5000`),
      getJson(`/v1/maritime/lineup?${port}past_hours=24&future_hours=336&limit=1000`),
      getJson(`/v1/maritime/summary?${port}hours=24&future_hours=336`),
    ]);
    state.vessels = vesselsResponse.data || [];
    state.lineup = lineupResponse.data || [];

    if (state.selected?.mmsi) {
      const refreshed = state.vessels.find(v => v.mmsi === state.selected.mmsi);
      if (refreshed) state.selected = refreshed;
    }

    renderMapLayers();
    renderVesselDetail();
    renderLineup();
    renderSummary(summaryResponse.data || {});
    els.mapEmpty.classList.toggle('hidden', state.vessels.length > 0);
    if (fit) fitToVessels(state.vessels);
    els.lastUpdate.textContent = `Atualizado ${new Intl.DateTimeFormat('pt-BR', {hour: '2-digit', minute: '2-digit', second: '2-digit'}).format(new Date())}`;
    setStatus('ok', 'online');
  } catch (error) {
    console.error(error);
    setStatus('error', 'erro de dados');
  } finally {
    els.refresh.disabled = false;
  }
}

async function loadConfig() {
  const response = await getJson('/v1/maritime/config');
  for (const port of response.pilot_ports || []) {
    const option = document.createElement('option');
    option.value = port.port_id;
    option.textContent = port.name;
    els.port.appendChild(option);
  }
}

function updateReplayTime() {
  if (!state.replay) {
    els.replayTime.textContent = '—';
    return;
  }
  const timestamp = new Date(state.replay.startMs + state.replayCurrent * 1000);
  els.replayTime.textContent = fmtDate(timestamp.toISOString());
  els.replaySlider.value = String(Math.round(state.replayCurrent));
}

function replayFrame(now) {
  if (!state.replay || !state.replayPlaying) return;
  if (state.replayLastFrame == null) state.replayLastFrame = now;
  const elapsed = Math.max(0, (now - state.replayLastFrame) / 1000);
  state.replayLastFrame = now;
  const speed = Math.max(60, state.replay.maxTime / 120);
  state.replayCurrent += elapsed * speed;
  if (state.replayCurrent >= state.replay.maxTime) state.replayCurrent = 0;
  updateReplayTime();
  renderMapLayers();
  state.replayFrame = requestAnimationFrame(replayFrame);
}

function startReplayAnimation() {
  state.replayPlaying = true;
  state.replayLastFrame = null;
  els.replayToggle.textContent = 'Pausar';
  if (state.replayFrame) cancelAnimationFrame(state.replayFrame);
  state.replayFrame = requestAnimationFrame(replayFrame);
}

function pauseReplay() {
  state.replayPlaying = false;
  els.replayToggle.textContent = 'Continuar';
  if (state.replayFrame) cancelAnimationFrame(state.replayFrame);
  state.replayFrame = null;
  state.replayLastFrame = null;
}

function stopReplay() {
  pauseReplay();
  state.replay = null;
  state.replayCurrent = 0;
  els.replayControls.classList.add('hidden');
}

async function loadReplay() {
  const vessel = state.selected;
  if (!vessel?.mmsi) return;
  els.replayButton.disabled = true;
  try {
    const response = await getJson(`/v1/maritime/vessels/${encodeURIComponent(vessel.mmsi)}/replay?hours=24&limit=20000`);
    const rows = (response.data || []).filter(row => Number.isFinite(Number(row.longitude)) && Number.isFinite(Number(row.latitude)));
    if (rows.length < 2) throw new Error('Histórico AIS insuficiente para replay');
    const startMs = new Date(rows[0].observed_at).getTime();
    const timestamps = rows.map(row => Math.max(0, (new Date(row.observed_at).getTime() - startMs) / 1000));
    state.replay = {
      path: rows.map(row => [Number(row.longitude), Number(row.latitude)]),
      timestamps,
      startMs,
      maxTime: Math.max(...timestamps),
    };
    state.replayCurrent = 0;
    els.replaySlider.max = String(Math.max(1, Math.round(state.replay.maxTime)));
    els.replaySlider.value = '0';
    els.replayControls.classList.remove('hidden');
    updateReplayTime();
    renderMapLayers();
    startReplayAnimation();
    fitToVessels(rows);
  } catch (error) {
    console.error(error);
    setStatus('error', 'replay indisponível');
  } finally {
    els.replayButton.disabled = !state.selected?.mmsi;
  }
}

els.refresh.addEventListener('click', () => refreshAll({fit: false}));
els.port.addEventListener('change', () => {
  stopReplay();
  state.selected = null;
  renderVesselDetail();
  refreshAll({fit: true});
});
els.replayButton.addEventListener('click', loadReplay);
els.replayToggle.addEventListener('click', () => {
  if (!state.replay) return;
  if (state.replayPlaying) pauseReplay();
  else startReplayAnimation();
});
els.replaySlider.addEventListener('input', event => {
  if (!state.replay) return;
  state.replayCurrent = Number(event.target.value) || 0;
  updateReplayTime();
  renderMapLayers();
});

map.on('load', async () => {
  try {
    await loadConfig();
    await refreshAll({fit: true});
  } catch (error) {
    console.error(error);
    setStatus('error', 'gateway indisponível');
  }
});

setInterval(() => {
  if (!document.hidden) refreshAll({fit: false});
}, 30000);
