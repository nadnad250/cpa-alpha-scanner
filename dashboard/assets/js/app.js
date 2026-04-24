/* ====================================================
   CPA Alpha Scanner — Dashboard App
   ==================================================== */

// ---- State ----
let allSignals = [];
let filteredSignals = [];
let activeFilter = 'all';
let activeUniverse = 'all';
let searchQuery = '';
let livePrices = {};   // { ticker: { price, changePct, time } }
let simPerPos = parseInt(localStorage.getItem('cpa_sim_per_pos') || '100', 10);
let simFeePct = parseFloat(localStorage.getItem('cpa_sim_fee_pct') || '0.1');  // 0.1% par trade (entrée + sortie)

// ---- Init ----
document.addEventListener('DOMContentLoaded', async () => {
  startClock();
  checkMarketStatus();
  await loadSignals();
  await refreshLivePrices();
  bindControls();
  setInterval(checkMarketStatus, 60000);
  // Auto-refresh signaux (fichier JSON) toutes les 5 min
  setInterval(() => loadSignals(), 5 * 60 * 1000);
  // Auto-refresh prix live toutes les 60 secondes
  setInterval(() => refreshLivePrices(), 60 * 1000);
});

// ---- Live prices depuis signals.json (écrit par le bot Python toutes les 15 min) ----
async function refreshLivePrices() {
  // Les prix sont désormais écrits directement dans signals.json par le workflow
  // live_prices.yml toutes les 15 min pendant les heures de marché.
  // On relit juste le fichier pour récupérer current_price sur chaque signal.
  try {
    const resp = await fetch('data/signals.json?t=' + Date.now(), { cache: 'no-store' });
    if (!resp.ok) throw new Error('fetch failed');
    const data = await resp.json();
    (data.signals || []).forEach(s => {
      if (s.current_price != null) {
        livePrices[s.ticker] = {
          price:     s.current_price,
          changePct: s.pnl_pct_live || 0,
          time:      s.current_price_time || new Date().toISOString(),
          progression: s.progression_pct,
        };
      }
    });
    // Dot vert dans navbar = tout est à jour
    const liveDot = document.querySelector('.live-dot');
    if (liveDot) {
      liveDot.style.background = 'var(--buy-light)';
      liveDot.style.boxShadow = '0 0 12px var(--buy-light)';
    }
    renderTable();
  } catch (e) {
    console.warn('Prix live indisponibles:', e.message);
  }
}

// ---- Progression calculée du signal (SL ← Entry ← Current → TP) ----
function computeProgression(s, current) {
  if (!current || !s.price || !s.take_profit || !s.stop_loss) return null;
  const entry = s.price, tp = s.take_profit, sl = s.stop_loss;
  const isBuy = s.score > 0;
  let pct;  // -100 = SL, 0 = entry, +100 = TP
  if (isBuy) {
    if (current >= entry) pct = ((current - entry) / (tp - entry)) * 100;
    else                  pct = -((entry - current) / (entry - sl)) * 100;
  } else {
    if (current <= entry) pct = ((entry - current) / (entry - tp)) * 100;
    else                  pct = -((current - entry) / (sl - entry)) * 100;
  }
  return Math.max(-120, Math.min(120, pct));
}

// ---- Clock ----
function startClock() {
  const updateClock = () => {
    const now = new Date();
    const timeEl = document.getElementById('clock-time');
    const dateEl = document.getElementById('clock-date');
    if (!timeEl) return;
    const pad = n => String(n).padStart(2, '0');
    timeEl.textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    const days = ['Dim','Lun','Mar','Mer','Jeu','Ven','Sam'];
    const months = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc'];
    dateEl.textContent = `${days[now.getDay()]} ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`;
    document.getElementById('eod-date').textContent = `${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`;
  };
  updateClock();
  setInterval(updateClock, 1000);
}

// ---- Market status ----
function checkMarketStatus() {
  const now = new Date();
  const nyTime = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const h = nyTime.getHours();
  const m = nyTime.getMinutes();
  const day = nyTime.getDay();
  const el = document.getElementById('market-status');
  if (!el) return;
  const dot = el.querySelector('.mkt-status-dot');
  const txt = el.querySelector('#status-text');
  el.className = 'mkt-status';
  if (day === 0 || day === 6) {
    el.classList.add('closed'); txt.textContent = 'Fermé (WE)';
  } else if (h >= 9 && (h < 16 || (h === 16 && m === 0))) {
    el.classList.add('open'); txt.textContent = 'Ouvert NYSE';
  } else if (h >= 4 && h < 9) {
    el.classList.add('pre'); txt.textContent = 'Pré-marché';
  } else if (h > 16 && h < 20) {
    el.classList.add('pre'); txt.textContent = 'After-hours';
  } else {
    el.classList.add('closed'); txt.textContent = 'Fermé';
  }
}

// ---- Load signals ----
async function loadSignals() {
  try {
    const resp = await fetch('data/signals.json?t=' + Date.now());
    if (!resp.ok) throw new Error('no file');
    const data = await resp.json();
    processData(data);
  } catch {
    // Use embedded demo
    processData(DEMO_DATA);
  }
}

function processData(data) {
  allSignals = data.signals || [];
  renderStats(data.stats, data.eod);
  applyFilters();
  renderBestSignal();
  renderTopList();
  renderSectors();
}

// ---- Stats bar ----
function renderStats(stats, eod) {
  if (!stats) return;
  const s = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  s('stat-total', stats.total);
  const wr = Math.round(stats.win_rate * 100);
  const wrEl = document.getElementById('stat-winrate');
  if (wrEl) { wrEl.textContent = wr + '%'; wrEl.className = 'stat-val ' + (wr >= 60 ? 'green' : wr >= 45 ? 'gold' : 'red'); }
  s('stat-confidence', Math.round(stats.avg_confidence * 100) + '%');
  s('stat-rr', stats.avg_rr.toFixed(1));
  s('stat-active', stats.active_positions);
  // ---- P&L LIVE + SIMULATION $ : agrège tous les signaux ouverts ----
  const pnlEl = document.getElementById('stat-pnl');
  const simPnlEl = document.getElementById('stat-sim-pnl');
  const simPerEl = document.getElementById('sim-per-pos');
  if (simPerEl) simPerEl.textContent = '$' + simPerPos;

  const opens = allSignals.filter(s => s.status === 'open');
  const withLive = opens.filter(s => typeof s.pnl_pct_live === 'number');

  if (pnlEl) {
    if (withLive.length) {
      const totWeight = withLive.reduce((a, s) => a + (s.kelly_position || 0.05), 0);
      const weightedPnl = withLive.reduce((a, s) => a + (s.pnl_pct_live * (s.kelly_position || 0.05)), 0);
      const avgPnl = totWeight > 0 ? weightedPnl / totWeight : 0;
      const sumPnl = withLive.reduce((a, s) => a + s.pnl_pct_live, 0);
      pnlEl.innerHTML = `${avgPnl >= 0 ? '+' : ''}${avgPnl.toFixed(2)}%<div style="font-size:10px;color:var(--text3);font-weight:400;margin-top:2px">Σ ${sumPnl >= 0 ? '+' : ''}${sumPnl.toFixed(1)}% · ${withLive.length} pos.</div>`;
      pnlEl.className = 'stat-val ' + (avgPnl >= 0 ? 'green' : 'red');
    } else {
      const pnl = stats.daily_pnl || 0;
      pnlEl.textContent = (pnl >= 0 ? '+' : '') + (pnl * 100).toFixed(1) + '%';
      pnlEl.className = 'stat-val ' + (pnl >= 0 ? 'green' : 'red');
    }
  }

  // ---- SIMULATION $ avec FRAIS : chaque position = simPerPos dollars ----
  if (simPnlEl) {
    const nPos = opens.length;
    const totalInvested = nPos * simPerPos;
    // Frais round-trip (entrée + sortie) = 2 × simFeePct % du montant
    const feesTotal = nPos * simPerPos * (simFeePct * 2 / 100);
    // Gain brut
    const gainGross = withLive.reduce((a, s) => a + (simPerPos * (s.pnl_pct_live || 0) / 100), 0);
    // Gain net (après frais)
    const gainNet = gainGross - feesTotal;

    const fmtUSD = (v) => {
      const sign = v >= 0 ? '+' : '−';
      const abs = Math.abs(v);
      if (abs >= 10000) return sign + '$' + (abs / 1000).toFixed(1) + 'k';
      return sign + '$' + abs.toFixed(2);
    };
    simPnlEl.innerHTML = `${fmtUSD(gainNet)}<div style="font-size:10px;color:var(--text3);font-weight:400;margin-top:2px">sur $${totalInvested.toLocaleString('en-US')} · frais $${feesTotal.toFixed(2)}</div>`;
    simPnlEl.className = 'stat-val ' + (gainNet >= 0 ? 'green' : 'red');
  }
  if (!eod) return;
  const total = (eod.tp_hit || 0) + (eod.sl_hit || 0);
  const rate = total > 0 ? Math.round((eod.tp_hit / total) * 100) : 0;
  const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  setEl('eod-won', eod.tp_hit || 0);
  setEl('eod-lost', eod.sl_hit || 0);
  setEl('eod-open', eod.open || 0);
  setEl('eod-rate', rate + '%');
  const barEl = document.getElementById('eod-bar');
  if (barEl) barEl.style.width = rate + '%';
  const pnlCum = eod.cumulative_pnl || 0;
  const cumEl = document.getElementById('eod-cumulative');
  if (cumEl) {
    cumEl.textContent = (pnlCum >= 0 ? '+' : '') + (pnlCum * 100).toFixed(1) + '%';
    cumEl.className = 'eod-pnl-val ' + (pnlCum >= 0 ? 'green' : 'red');
  }
}

// ---- Filter & Render ----
function applyFilters() {
  filteredSignals = allSignals.filter(s => {
    // Dashboard = UNIQUEMENT positions ouvertes
    // Les TP/SL clôturés sont visibles sur /live.html et /stats.html
    if (s.status !== 'open') return false;

    const isBuy = s.score > 0;
    if (activeFilter === 'BUY'  && !isBuy)  return false;
    if (activeFilter === 'SELL' && isBuy)   return false;
    if (activeUniverse !== 'all' && s.universe !== activeUniverse) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const t = (s.ticker || '').toLowerCase();
      const sec = (s.sector || '').toLowerCase();
      if (!t.includes(q) && !sec.includes(q)) return false;
    }
    return true;
  });
  renderTable();
  const badge = document.getElementById('signal-badge');
  if (badge) badge.textContent = filteredSignals.length + ' signal' + (filteredSignals.length !== 1 ? 's' : '');
}

function renderTable() {
  const tbody = document.getElementById('signals-tbody');
  if (!tbody) return;
  if (filteredSignals.length === 0) {
    const isWaiting = allSignals.length === 0;
    tbody.innerHTML = `<tr><td colspan="12">
      <div class="empty-state" style="padding:60px 20px">
        <div class="es-icon" style="font-size:48px">${isWaiting ? '⏳' : '📭'}</div>
        <div class="es-text" style="font-size:15px;font-weight:700;margin-bottom:6px">${isWaiting ? 'En attente du prochain scan' : 'Aucun signal correspondant aux filtres'}</div>
        <div style="font-size:12px;color:var(--text3);max-width:420px;margin:0 auto;line-height:1.6">
          ${isWaiting ? 'Le bot tourne automatiquement à 09:30, 11:00, 13:30 et 15:30 NY (Lun-Ven). Les signaux apparaîtront ici dès le prochain scan.' : 'Ajustez les filtres ou ouvrez un autre marché.'}
        </div>
      </div></td></tr>`;
    return;
  }
  tbody.innerHTML = filteredSignals.map((s, i) => buildRow(s, i + 1)).join('');
  tbody.querySelectorAll('tr[data-idx]').forEach(row => {
    row.addEventListener('click', () => openModal(parseInt(row.dataset.idx)));
  });
}

function buildRow(s, num) {
  const isBuy = s.score > 0;
  const badgeCls = s.action === 'STRONG_BUY' ? 'badge-sb' : s.action === 'BUY' ? 'badge-b' : s.action === 'STRONG_SELL' ? 'badge-ss' : 'badge-s';
  const actionLabel = s.action === 'STRONG_BUY' ? '⬆⬆ STRONG BUY' : s.action === 'BUY' ? '⬆ BUY' : s.action === 'STRONG_SELL' ? '⬇⬇ STRONG SELL' : '⬇ SELL';
  const confPct = Math.round(s.confidence * 100);
  const confColor = confPct >= 80 ? 'var(--buy-light)' : confPct >= 70 ? 'var(--gold)' : 'var(--sell-light)';
  const rrCls = s.risk_reward >= 2.5 ? 'rr-good' : s.risk_reward >= 2.0 ? 'rr-ok' : 'rr-bad';
  const rowCls = s.status === 'tp_hit' ? 'tp-row' : s.status === 'sl_hit' ? 'sl-row' : '';
  const time = s.issued_at ? s.issued_at.split('T')[1].substring(0,5) : '--:--';
  const idx = allSignals.indexOf(s);

  // ---- Prix live + variation % depuis l'entrée ----
  const live = livePrices[s.ticker];
  let livePriceCell = `<span style="color:var(--text3);font-size:10px">—</span>`;
  let progBar = '';
  if (live && live.price) {
    const pctFromEntry = isBuy
      ? ((live.price - s.price) / s.price) * 100
      : ((s.price - live.price) / s.price) * 100;
    const goingWell = pctFromEntry >= 0;
    const color = goingWell ? 'var(--buy-light)' : 'var(--sell-light)';
    const arrow = goingWell ? '▲' : '▼';
    livePriceCell = `
      <div class="live-price-wrap">
        <span class="live-price" style="color:${color}">$${fmt(live.price)}</span>
        <span class="live-chg" style="color:${color}">${arrow} ${Math.abs(pctFromEntry).toFixed(2)}%</span>
      </div>`;

    // Progression : -100% = SL touché, 0% = au prix d'entrée, +100% = TP atteint
    const prog = computeProgression(s, live.price);
    if (prog !== null) {
      const posOnBar = Math.max(0, Math.min(100, 50 + prog / 2)); // 0..100 sur la barre
      const progColor = prog > 0 ? 'var(--buy-light)' : 'var(--sell-light)';
      // Gain/perte en $ pour ce signal (basé sur simPerPos, net de frais)
      const dollarGross = simPerPos * (live.price && s.price
        ? (isBuy ? (live.price - s.price) / s.price : (s.price - live.price) / s.price)
        : 0);
      const dollarFees = simPerPos * (simFeePct * 2 / 100);
      const dollarPnl = dollarGross - dollarFees;
      const dollarStr = `${dollarPnl >= 0 ? '+' : '−'}$${Math.abs(dollarPnl).toFixed(2)}`;
      progBar = `
        <div class="prog-signal" title="SL ← Entry → TP — progression: ${prog.toFixed(0)}%">
          <div class="prog-signal-bar">
            <div class="prog-signal-sl">SL</div>
            <div class="prog-signal-entry"></div>
            <div class="prog-signal-tp">TP</div>
            <div class="prog-signal-marker" style="left:${posOnBar}%;background:${progColor};box-shadow:0 0 8px ${progColor}"></div>
            ${prog > 0 ? `<div class="prog-signal-fill-up" style="width:${posOnBar - 50}%"></div>` : ''}
            ${prog < 0 ? `<div class="prog-signal-fill-down" style="width:${50 - posOnBar}%"></div>` : ''}
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:2px">
            <span class="prog-signal-pct" style="color:${progColor}">${prog > 0 ? '+' : ''}${prog.toFixed(0)}%</span>
            <span style="font-family:var(--mono);font-size:10px;color:${progColor};font-weight:600">${dollarStr}</span>
          </div>
        </div>`;
    }
  }

  const tvHref = tradingViewUrl(s.ticker, s.universe);
  return `<tr class="${rowCls}" data-idx="${idx}">
    <td class="td-num">${num}</td>
    <td class="td-ticker" onclick="event.stopPropagation()">
      <a href="${tvHref}" target="_blank" rel="noopener noreferrer" class="ticker-link" title="Ouvrir ${s.ticker} dans TradingView">
        ${s.ticker}<span class="ext-icon">↗</span>
      </a>
      <span class="ticker-sub">${s.universe}</span>
    </td>
    <td><span class="action-badge ${badgeCls}">${actionLabel}</span></td>
    <td class="td-price">
      <div style="font-size:10px;color:var(--text3);margin-bottom:2px">ENTRÉE</div>
      $${fmt(s.price)}
      ${(() => {
        const mkt = getMarketStatus(s.universe, s.ticker);
        if (live && live.price) {
          return `<div style="font-size:9px;color:var(--text3);margin-top:3px">LIVE · <span style="color:${mkt.open ? 'var(--buy-light)' : 'var(--sell-light)'};font-weight:600">${mkt.open ? '🟢' : '🔴 '+mkt.short}</span></div>${livePriceCell}`;
        }
        return `<div style="font-size:9px;color:var(--text3);margin-top:3px">${mkt.label}</div>`;
      })()}
    </td>
    <td class="td-tp">$${fmt(s.take_profit)}</td>
    <td class="td-sl">$${fmt(s.stop_loss)}</td>
    <td class="td-progression">${progBar || `<span style="color:var(--text3);font-size:10px">⏳ En attente prix live</span>`}</td>
    <td>
      <div class="conf-wrap">
        <div class="conf-bar"><div class="conf-fill" style="width:${confPct}%;background:${confColor}"></div></div>
        <span class="conf-pct" style="color:${confColor}">${confPct}%</span>
      </div>
    </td>
    <td class="td-rr ${rrCls}">${s.risk_reward.toFixed(1)}x</td>
    <td class="td-alloc">${Math.round((s.kelly_position || computeKellyFallback(s)) * 100)}%</td>
    <td class="td-time">${time}</td>
    <td class="td-info"><button class="info-btn" title="Détails">🔍</button></td>
  </tr>`;
}

// ---- Best Signal ----
function renderBestSignal() {
  // Uniquement signaux ouverts (pas les tp_hit/sl_hit)
  const opens = allSignals.filter(s => s.status === 'open');
  const best = [...opens].sort((a, b) => Math.abs(b.score) - Math.abs(a.score))[0];
  if (!best) return;
  const el = document.getElementById('best-signal-body');
  if (!el) return;
  const isBuy = best.score > 0;
  const up = isBuy ? '+' : '-';
  el.innerHTML = `
    <div class="best-inner">
      <div class="best-top">
        <span class="best-ticker">${best.ticker}</span>
        <span class="best-up" style="color:${isBuy ? 'var(--strong-buy)' : 'var(--strong-sell)'}">${up}${Math.abs(best.upside_pct).toFixed(1)}%</span>
      </div>
      <div class="best-row"><span>Prix</span><span>$${fmt(best.price)}</span></div>
      <div class="best-row"><span>TP</span><span style="color:var(--buy-light)">$${fmt(best.take_profit)}</span></div>
      <div class="best-row"><span>SL</span><span style="color:var(--sell-light)">$${fmt(best.stop_loss)}</span></div>
      <div class="best-row"><span>Confiance</span><span>${Math.round(best.confidence * 100)}%</span></div>
      <div class="best-row"><span>R/R</span><span>${best.risk_reward.toFixed(1)}x</span></div>
      <div class="best-reason">${best.primary_reason}</div>
    </div>`;
}

// ---- Top Signals List ----
function renderTopList() {
  const opens = allSignals.filter(s => s.status === 'open');
  const top = [...opens].sort((a, b) => b.confidence - a.confidence).slice(0, 6);
  const ul = document.getElementById('top-list');
  if (!ul) return;
  ul.innerHTML = top.map((s, i) => {
    const isBuy = s.score > 0;
    const idx = allSignals.indexOf(s);
    return `<li class="top-item" data-idx="${idx}">
      <span class="top-rank">#${i + 1}</span>
      <div class="top-action-dot ${isBuy ? 'dot-buy' : 'dot-sell'}"></div>
      <span class="top-ticker">${s.ticker}</span>
      <span class="top-conf">${Math.round(s.confidence * 100)}%</span>
    </li>`;
  }).join('');
  ul.querySelectorAll('.top-item').forEach(li => {
    li.addEventListener('click', () => openModal(parseInt(li.dataset.idx)));
  });
}

// ---- Sector Breakdown ----
function renderSectors() {
  const counts = {};
  const opens = allSignals.filter(s => s.status === 'open');
  opens.forEach(s => {
    const sec = s.sector || '—';
    counts[sec] = (counts[sec] || 0) + 1;
  });
  const max = Math.max(...Object.values(counts));
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const el = document.getElementById('sector-bars');
  if (!el) return;
  el.innerHTML = sorted.map(([name, count]) => `
    <div class="sect-row">
      <div class="sect-label">
        <span class="sect-name">${name}</span>
        <span class="sect-count">${count}</span>
      </div>
      <div class="sect-track">
        <div class="sect-fill" style="width:${Math.round((count / max) * 100)}%"></div>
      </div>
    </div>`).join('');
}

// ---- Modal ----
function openModal(idx) {
  const s = allSignals[idx];
  if (!s) return;
  const isBuy = s.score > 0;
  const tvHref = tradingViewUrl(s.ticker, s.universe);
  const modalTicker = document.getElementById('modal-ticker');
  modalTicker.innerHTML = `<a href="${tvHref}" target="_blank" rel="noopener" class="modal-ticker-link" title="Voir sur TradingView">${s.ticker}<span class="ext-icon-big">↗</span></a>`;
  document.getElementById('modal-universe').textContent = s.universe + ' · ' + s.sector;
  const ab = document.getElementById('modal-action-big');
  const badgeCls = s.action === 'STRONG_BUY' ? 'badge-sb' : s.action === 'BUY' ? 'badge-b' : s.action === 'STRONG_SELL' ? 'badge-ss' : 'badge-s';
  ab.innerHTML = `<span class="action-badge ${badgeCls}">${s.action.replace('_', ' ')}</span>`;

  // Price block
  document.getElementById('md-price').textContent = '$' + fmt(s.price);
  document.getElementById('md-tp').textContent = '$' + fmt(s.take_profit);
  document.getElementById('md-sl').textContent = '$' + fmt(s.stop_loss);
  document.getElementById('md-intrinsic').textContent = s.intrinsic_value ? '$' + fmt(s.intrinsic_value) : '—';
  const up = s.upside_pct;
  document.getElementById('md-upside').textContent = (up >= 0 ? '+' : '') + up.toFixed(1) + '%';
  document.getElementById('md-upside').style.color = up >= 0 ? 'var(--buy-light)' : 'var(--sell-light)';

  // Signal block
  document.getElementById('md-cpa').textContent = s.cpa_alpha ? s.cpa_alpha.toFixed(3) : '—';
  document.getElementById('md-confidence').textContent = Math.round(s.confidence * 100) + '%';
  document.getElementById('md-rr').textContent = s.risk_reward.toFixed(2) + 'x';
  document.getElementById('md-ml').textContent = s.ml_proba_up ? Math.round(s.ml_proba_up * 100) + '%' : '—';
  document.getElementById('md-kelly').textContent = s.kelly_position ? Math.round(s.kelly_position * 100) + '%' : '—';
  document.getElementById('md-score').textContent = s.score.toFixed(3);

  // CPA Components
  const comps = [
    { name: 'Value Gap', key: 'value_gap', weight: '35%' },
    { name: 'Factor Premia', key: 'factor_premia', weight: '25%' },
    { name: 'Mean Reversion', key: 'mean_reversion', weight: '20%' },
    { name: 'Info Flow', key: 'info_flow', weight: '20%' },
  ];
  const cpaEl = document.getElementById('md-cpa-components');
  if (cpaEl) {
    cpaEl.innerHTML = comps.map(c => {
      const raw = s[c.key];
      // Non calculé → "—" discret
      if (raw === null || raw === undefined) {
        return `<div class="cpa-comp-row">
          <div class="cpa-comp-label">
            <span class="cpa-comp-name">${c.name} <span style="color:var(--text3);font-size:10px">(${c.weight})</span></span>
            <span class="cpa-comp-score" style="color:var(--text3)">— non calculé</span>
          </div>
          <div class="cpa-comp-track"><div style="height:100%;opacity:.3;background:var(--border);width:100%"></div></div>
        </div>`;
      }
      // Valeur à 0 exact → stratégiquement affichée mais discrète (vieux signal sans data)
      if (raw === 0) {
        return `<div class="cpa-comp-row">
          <div class="cpa-comp-label">
            <span class="cpa-comp-name">${c.name} <span style="color:var(--text3);font-size:10px">(${c.weight})</span></span>
            <span class="cpa-comp-score" style="color:var(--text3)">0.000 · neutre</span>
          </div>
          <div class="cpa-comp-track"><div style="height:100%;opacity:.2;background:var(--border);width:100%"></div></div>
        </div>`;
      }
      // Normalise avec tanh pour garder visuellement [-1, +1]
      const normalized = Math.tanh(raw);
      const pct = Math.min(Math.abs(normalized) * 100, 100);
      const pos = raw >= 0;
      const displayVal = Math.abs(raw) > 2 ? raw.toFixed(2) : raw.toFixed(3);
      return `<div class="cpa-comp-row">
        <div class="cpa-comp-label">
          <span class="cpa-comp-name">${c.name} <span style="color:var(--text3);font-size:10px">(${c.weight})</span></span>
          <span class="cpa-comp-score" style="color:${pos ? 'var(--buy-light)' : 'var(--sell-light)'}">${pos ? '+' : ''}${displayVal}</span>
        </div>
        <div class="cpa-comp-track">
          <div class="cpa-comp-fill ${pos ? 'cpa-pos' : 'cpa-neg'}" style="width:${pct}%"></div>
        </div>
      </div>`;
    }).join('');
  }

  // Reason
  const reasonEl = document.getElementById('md-reason');
  if (reasonEl) {
    const subs = (s.secondary_reasons || []).map(r => `<span>• ${r}</span>`).join('');
    reasonEl.innerHTML = `<div class="reason-main">${s.primary_reason}</div>${subs ? `<div class="reason-sub">${subs}</div>` : ''}`;
  }

  // News
  const newsBlock = document.getElementById('md-news-block');
  const newsEl = document.getElementById('md-news');
  if (newsBlock && newsEl && s.top_news_title) {
    newsBlock.style.display = '';
    const link = s.top_news_url ? `<a href="${s.top_news_url}" target="_blank">${s.top_news_title}</a>` : s.top_news_title;
    newsEl.innerHTML = link + (s.news_score != null ? ` <span style="color:${s.news_score >= 0 ? 'var(--buy-light)' : 'var(--sell-light)'}">(sentiment: ${s.news_score >= 0 ? '+' : ''}${s.news_score.toFixed(1)})</span>` : '');
  } else if (newsBlock) {
    newsBlock.style.display = 'none';
  }

  // Risk flags
  const riskBlock = document.getElementById('md-risk-block');
  const riskEl = document.getElementById('md-risks');
  if (riskBlock && riskEl) {
    if (s.risk_flags && s.risk_flags.length > 0) {
      riskBlock.style.display = '';
      riskEl.innerHTML = `<div class="risk-tags">${s.risk_flags.map(r => `<span class="risk-tag">⚠ ${r}</span>`).join('')}</div>`;
    } else {
      riskBlock.style.display = 'none';
    }
  }

  // Status
  const statusMap = { open: '🟢 Signal actif', tp_hit: '✅ Take Profit atteint', sl_hit: '🔴 Stop Loss touché', expired: '⏱ Expiré' };
  document.getElementById('md-status').textContent = statusMap[s.status] || s.status;

  document.getElementById('modal-overlay').classList.add('open');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
}

// ---- Controls ----
function bindControls() {
  // Filter buttons
  document.querySelectorAll('.fbtn').forEach(btn => {
    btn.addEventListener('click', () => {
      activeFilter = btn.dataset.filter;
      document.querySelectorAll('.fbtn').forEach(b => b.classList.remove('active','buy-active','sell-active'));
      if (activeFilter === 'BUY')  btn.classList.add('buy-active');
      else if (activeFilter === 'SELL') btn.classList.add('sell-active');
      else btn.classList.add('active');
      applyFilters();
    });
  });

  // Universe select
  const univSel = document.getElementById('univ-filter');
  if (univSel) univSel.addEventListener('change', () => { activeUniverse = univSel.value; applyFilters(); });

  // Search
  const searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.addEventListener('input', () => { searchQuery = searchInput.value.trim(); applyFilters(); });

  // Modal close
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-overlay').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

  // ---- Simulation modal ----
  const simCard   = document.getElementById('sim-card');
  const simModal  = document.getElementById('sim-modal');
  const simInput  = document.getElementById('sim-input');
  const simSave   = document.getElementById('sim-save');
  const simClose  = document.getElementById('sim-close');
  const simPreview = document.getElementById('sim-preview');

  const simFeeInput = document.getElementById('sim-fee');

  function updateSimPreview() {
    if (!simPreview) return;
    const val = parseInt(simInput.value, 10) || 0;
    const fee = parseFloat(simFeeInput.value) || 0;
    const opens = allSignals.filter(s => s.status === 'open');
    const withLive = opens.filter(s => typeof s.pnl_pct_live === 'number');
    const total = opens.length * val;
    const gainGross = withLive.reduce((a, s) => a + (val * (s.pnl_pct_live || 0) / 100), 0);
    const fees = opens.length * val * (fee * 2 / 100);
    const gainNet = gainGross - fees;
    simPreview.innerHTML = `
      <div style="display:flex;justify-content:space-between;margin-bottom:4px"><span>Positions ouvertes :</span><strong style="color:var(--text)">${opens.length}</strong></div>
      <div style="display:flex;justify-content:space-between;margin-bottom:4px"><span>Investissement total :</span><strong style="color:var(--text);font-family:var(--mono)">$${total.toLocaleString('en-US')}</strong></div>
      <div style="display:flex;justify-content:space-between;margin-bottom:4px"><span>Gain brut live :</span><span style="color:${gainGross >= 0 ? 'var(--buy-light)' : 'var(--sell-light)'};font-family:var(--mono)">${gainGross >= 0 ? '+' : '−'}$${Math.abs(gainGross).toFixed(2)}</span></div>
      <div style="display:flex;justify-content:space-between;margin-bottom:4px"><span>Frais total (${fee}% × 2) :</span><span style="color:var(--sell-light);font-family:var(--mono)">−$${fees.toFixed(2)}</span></div>
      <div style="display:flex;justify-content:space-between;padding-top:8px;margin-top:4px;border-top:2px solid var(--border)"><span style="font-weight:700;color:var(--text)">GAIN NET :</span><strong style="color:${gainNet >= 0 ? 'var(--buy-light)' : 'var(--sell-light)'};font-family:var(--mono);font-size:15px">${gainNet >= 0 ? '+' : '−'}$${Math.abs(gainNet).toFixed(2)}</strong></div>
    `;
  }

  if (simCard && simModal) {
    simCard.addEventListener('click', () => {
      simInput.value = simPerPos;
      simFeeInput.value = simFeePct;
      updateSimPreview();
      simModal.style.display = 'flex';
    });
    simClose.addEventListener('click', () => { simModal.style.display = 'none'; });
    simModal.addEventListener('click', (e) => { if (e.target === simModal) simModal.style.display = 'none'; });
    simInput.addEventListener('input', updateSimPreview);
    simFeeInput.addEventListener('input', updateSimPreview);
    document.querySelectorAll('.sim-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        simInput.value = btn.dataset.v;
        updateSimPreview();
      });
    });
    document.querySelectorAll('.fee-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        simFeeInput.value = btn.dataset.v;
        updateSimPreview();
      });
    });
    simSave.addEventListener('click', () => {
      const v = Math.max(10, Math.min(100000, parseInt(simInput.value, 10) || 100));
      const f = Math.max(0, Math.min(2, parseFloat(simFeeInput.value) || 0));
      simPerPos = v;
      simFeePct = f;
      localStorage.setItem('cpa_sim_per_pos', String(v));
      localStorage.setItem('cpa_sim_fee_pct', String(f));
      simModal.style.display = 'none';
      loadSignals();
      showToast(`💰 Simulation : $${v}/pos · ${f}% frais`);
    });
  }

  // Refresh button
  const refBtn = document.getElementById('refresh-btn');
  if (refBtn) {
    refBtn.addEventListener('click', () => {
      refBtn.textContent = '⟳';
      refBtn.style.animation = 'spin .5s linear';
      loadSignals().then(() => {
        refBtn.style.animation = '';
        showToast('✅ Données actualisées');
      });
    });
  }
}

// ---- Toast ----
function showToast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.remove('hidden');
  setTimeout(() => t.classList.add('hidden'), 2500);
}

// ---- Util ----
function fmt(n) {
  if (n == null) return '—';
  if (n >= 1000) return n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return n.toFixed(2);
}

// ---- Convertir ticker yfinance → symbole TradingView ----
const UNIVERSE_EXCHANGE = {
  SP500: 'NYSE', NASDAQ100: 'NASDAQ', DOW30: 'NYSE',
  DAX40: 'XETR', CAC40: 'EURONEXT', FTSE100: 'LSE', EUROSTOXX50: 'EURONEXT',
};
const SUFFIX_EXCHANGE = {
  DE: 'XETR', PA: 'EURONEXT', L: 'LSE', MI: 'MIL',
  AS: 'AMS',  MC: 'BME',      HK: 'HKEX', T: 'TSE',
  TO: 'TSX',  SW: 'SIX',      BR: 'EURONEXT', VI: 'VIE',
};
// Tickers NASDAQ courants (quand pas de suffixe)
const NASDAQ_TICKERS = new Set('AAPL MSFT GOOGL GOOG AMZN META NVDA TSLA AMD INTC NFLX ADBE CSCO AVGO COST PEP CMCSA TMUS QCOM INTU TXN AMGN SBUX CHTR BKNG PYPL FTNT ODFL ADP ISRG MDLZ GILD MU REGN ADI VRTX LRCX PANW KLAC ASML MELI ORLY SNPS CDNS MNST CRWD ABNB MRNA CTAS NXPI PCAR FAST EA PAYX ROST IDXX CPRT CTSH DXCM DLTR XEL BIIB ANSS FANG KHC GEHC ON SIRI WDAY WBD LULU TTD TEAM ZS DASH MAR'.split(' '));

function tradingViewUrl(ticker, universe) {
  const parts = (ticker || '').split('.');
  let tvSymbol;
  if (parts.length === 2 && SUFFIX_EXCHANGE[parts[1]]) {
    tvSymbol = `${SUFFIX_EXCHANGE[parts[1]]}:${parts[0]}`;
  } else if (NASDAQ_TICKERS.has(ticker)) {
    tvSymbol = `NASDAQ:${ticker}`;
  } else {
    const exch = UNIVERSE_EXCHANGE[universe] || 'NASDAQ';
    tvSymbol = `${exch}:${ticker}`;
  }
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}`;
}

// ---- Détection du statut du marché pour un ticker donné ----
function getMarketStatus(universe, ticker) {
  const now = new Date();
  const day = now.getUTCDay();      // 0 = Dim, 6 = Sam
  const hoursUTC = now.getUTCHours() + now.getUTCMinutes() / 60;
  const isWeekend = (day === 0 || day === 6);

  // Crypto = 24/7
  if (universe === 'CRYPTO' || (ticker || '').endsWith('-USD')) {
    return { open: true, label: '🟢 24/7', short: '24/7' };
  }
  // Week-end : tout fermé
  if (isWeekend) return { open: false, label: '🔴 Week-end', short: 'WE' };

  // Futures : quasi 24h (NQ/ES/GC/CL) - ouvert sauf maintenance
  if ((ticker || '').endsWith('=F')) {
    return { open: true, label: '🟢 Futures', short: 'Fut' };
  }
  // Europe : 08:00-16:30 UTC (09:00-17:30 Paris)
  if (['DAX40', 'CAC40', 'EUROSTOXX50', 'FTSE100'].includes(universe) ||
      /\.(DE|PA|L|AS|MI|MC|BR)$/.test(ticker || '')) {
    const open = hoursUTC >= 8 && hoursUTC < 16.5;
    return open
      ? { open: true,  label: '🟢 Ouvert',  short: 'EU' }
      : { open: false, label: '🔴 Fermé EU', short: 'EU' };
  }
  // US : 13:30-20:00 UTC (09:30-16:00 NY)
  if (['SP500', 'NASDAQ100', 'DOW30'].includes(universe)) {
    const open = hoursUTC >= 13.5 && hoursUTC < 20;
    return open
      ? { open: true,  label: '🟢 Ouvert',  short: 'NYSE' }
      : { open: false, label: '🔴 Fermé NYSE', short: 'NYSE' };
  }
  return { open: true, label: '🟢', short: '?' };
}

// Fallback Kelly fractionné + score factor → varie de 3% à 10% selon conviction
function computeKellyFallback(s) {
  const p = s.confidence || 0.5;
  const b = s.risk_reward || 2.0;
  const raw = b > 0 ? (p * b - (1 - p)) / b : 0;
  const scoreFactor = 0.7 + 0.6 * Math.min(Math.abs(s.score || 0), 1.0);  // 0.7-1.3
  return Math.max(0.025, Math.min(0.10, raw * 0.15 * scoreFactor));
}

// ---- Embedded Demo (fallback) ----
const DEMO_DATA = {
  "generated_at": new Date().toISOString(),
  "date": new Date().toISOString().split('T')[0],
  "stats": { "total": 15, "buy_signals": 11, "sell_signals": 4, "avg_confidence": 0.81, "avg_rr": 2.74, "win_rate": 0.78, "active_positions": 7, "daily_pnl": 0.042 },
  "eod": { "tp_hit": 9, "sl_hit": 2, "open": 7, "cumulative_pnl": 0.042 },
  "signals": []
};
