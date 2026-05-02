'use strict';

// ── Strategy metadata ────────────────────────────────────
const STRATEGIES = {
  rsi: {
    label: 'RSI (상대강도지수)',
    desc: '<strong>RSI</strong>가 30 이하 과매도 구간에서 반등할 때 <strong>매수</strong>, 70 이상 과매수 구간에서 하락할 때 <strong>매도</strong>합니다.',
  },
  ma_cross: {
    label: '이동평균 크로스오버',
    desc: '단기 이동평균이 장기 이동평균을 <strong>위로 돌파</strong>하면 매수(골든크로스), <strong>아래로 돌파</strong>하면 매도(데드크로스)합니다.',
  },
  bollinger: {
    label: '볼린저밴드',
    desc: '주가가 하단 밴드 이탈 후 <strong>회복</strong>하면 매수, 상단 밴드 이탈 후 <strong>하락</strong>하면 매도합니다.',
  },
  volatility_breakout: {
    label: '변동성 돌파 (래리 윌리엄스)',
    desc: '<strong>매수가 = 당일 시가 + (전일 고가 − 전일 저가) × k</strong> 를 돌파하면 매수, 장 마감 전 전량 매도합니다.',
  },
};

// ── State ────────────────────────────────────────────────
let isRunning = false;
let lastLogLen = 0;

// ── Formatting ───────────────────────────────────────────
function krw(n) {
  if (n == null || isNaN(n)) return '—';
  return Math.round(n).toLocaleString('ko-KR') + '원';
}

function usd(n) {
  if (n == null || isNaN(n)) return '—';
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct(r) {
  if (r == null || isNaN(r)) return '—';
  const sign = r > 0 ? '+' : '';
  return `${sign}${Number(r).toFixed(2)}%`;
}

function rateClass(r) {
  if (r > 0.005) return 'profit-pos';
  if (r < -0.005) return 'profit-neg';
  return 'profit-nil';
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// ── Status ───────────────────────────────────────────────
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const d = await res.json();

    isRunning = d.running;

    // Status dot & label
    const dot   = document.getElementById('statusDot');
    const label = document.getElementById('statusLabel');
    const btn   = document.getElementById('toggleBtn');

    if (d.running) {
      dot.className   = 'status-dot active';
      label.textContent = '실행 중';
      btn.textContent = '중지하기';
      btn.classList.add('running');
    } else {
      dot.className   = 'status-dot';
      label.textContent = '대기 중';
      btn.textContent = '시작하기';
      btn.classList.remove('running');
    }

    // Mode tag
    document.getElementById('modeTag').textContent = d.virtual ? '모의투자' : '실전투자';

    // Config row
    document.getElementById('cfgInterval').textContent = `${d.interval}분마다`;
    document.getElementById('cfgMode').textContent     = d.virtual ? '모의투자' : '실전투자';

    // Strategy pills
    document.querySelectorAll('.strategy-pill').forEach(pill => {
      pill.classList.toggle('active', pill.dataset.strategy === d.strategy);
    });

    // Strategy info
    const info = STRATEGIES[d.strategy];
    if (info) {
      document.getElementById('strategyInfo').innerHTML =
        `<strong>${info.label}</strong> &mdash; ${info.desc}`;
    }

  } catch {/* silently retry */ }
}

// ── Balance ──────────────────────────────────────────────
async function fetchBalance() {
  try {
    const res = await fetch('/api/balance');
    const d   = await res.json();
    renderBalance(d);
  } catch {/* silently retry */ }
}

async function refreshBalance() {
  const btn = document.getElementById('refreshBtn');
  btn.classList.add('spinning');
  try {
    const res = await fetch('/api/balance/refresh');
    const d   = await res.json();
    renderBalance(d);
  } catch {/* silently retry */ }
  setTimeout(() => btn.classList.remove('spinning'), 600);
}

function renderBalance(d) {
  const cash  = d.balance?.cash         ?? 0;
  const total = d.balance?.total_assets ?? 0;
  const stock = total - cash;

  document.getElementById('cashValue').textContent  = krw(cash);
  document.getElementById('stockValue').textContent = krw(stock);
  document.getElementById('totalValue').textContent = krw(total);

  renderHoldings(d.holdings ?? []);
}

function renderHoldings(list) {
  const container = document.getElementById('holdingsContainer');
  const badge     = document.getElementById('holdingsCount');
  badge.textContent = list.length;

  if (!list.length) {
    container.innerHTML = `<div class="empty-holdings">보유 종목이 없습니다</div>`;
    return;
  }

  const kr   = list.filter(h => (h.market ?? (/^\d+$/.test(h.symbol) ? 'KR' : 'US')) === 'KR');
  const us   = list.filter(h => (h.market ?? (/^\d+$/.test(h.symbol) ? 'KR' : 'US')) === 'US');
  const both = kr.length > 0 && us.length > 0;

  function tableSection(items, title, fmt) {
    const header = both ? `<div class="market-subtitle">${title}</div>` : '';
    const rows = items.map(h => {
      const profit = (h.current_price - h.avg_price) * h.qty;
      const rc     = rateClass(h.profit_rate);
      return `
        <tr>
          <td><span class="cell-symbol">${esc(h.symbol)}</span></td>
          <td>${h.qty.toLocaleString()}주</td>
          <td>${fmt(h.avg_price)}</td>
          <td>${fmt(h.current_price)}</td>
          <td class="${rc}">${pct(h.profit_rate)}</td>
          <td class="${rc}">${fmt(profit)}</td>
        </tr>`;
    }).join('');
    return `
      ${header}
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>종목코드</th><th>수량</th><th>평균단가</th>
              <th>현재가</th><th>수익률</th><th>평가손익</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  let html = '';
  if (kr.length) html += tableSection(kr, '한국 주식', krw);
  if (us.length) html += tableSection(us, '미국 주식', usd);
  container.innerHTML = html;
}

// ── Watchlist ────────────────────────────────────────────
async function fetchWatchlist() {
  try {
    const res = await fetch('/api/watchlist');
    const d = await res.json();
    renderWatchlist(d);
  } catch {/* silently retry */ }
}

async function refreshWatchlist() {
  const btn = document.getElementById('watchlistRefreshBtn');
  btn.classList.add('spinning');
  try {
    const res = await fetch('/api/watchlist/refresh');
    const d = await res.json();
    renderWatchlist(d);
  } catch {/* silently retry */ }
  setTimeout(() => btn.classList.remove('spinning'), 600);
}

function renderWatchlist(d) {
  const container  = document.getElementById('watchlistContainer');
  const badge      = document.getElementById('watchlistCount');
  const updatedEl  = document.getElementById('watchlistUpdated');
  const items      = d.items ?? [];

  badge.textContent = items.length;
  if (d.updated_at) updatedEl.textContent = `마지막 업데이트: ${d.updated_at}`;

  if (!items.length) {
    container.innerHTML = `<div class="empty-holdings">감시 종목이 없습니다</div>`;
    return;
  }

  const rows = items.map(item => {
    const nameCell = `<span class="cell-symbol">${esc(item.symbol)}</span><span class="cell-name">${esc(item.name ?? '')}</span>`;
    if (item.error) {
      return `<tr>
        <td>${nameCell}</td>
        <td class="profit-nil">—</td>
        <td class="profit-nil">—</td>
        <td class="profit-nil">—</td>
        <td><span class="screener-badge screener-fail">미조회</span></td>
      </tr>`;
    }
    const rc   = item.change_rate > 0.05 ? 'profit-pos' : item.change_rate < -0.05 ? 'profit-neg' : 'profit-nil';
    const sign = item.change_rate > 0 ? '+' : '';
    const passedBadge = item.passed
      ? `<span class="screener-badge screener-pass">통과</span>`
      : `<span class="screener-badge screener-fail" title="${esc(item.fail_reason ?? '')}">${esc(item.fail_reason ?? '제외')}</span>`;
    return `<tr>
      <td>${nameCell}</td>
      <td>${krw(item.price)}</td>
      <td class="${rc}">${sign}${Number(item.change_rate).toFixed(2)}%</td>
      <td>${Number(item.volume).toLocaleString('ko-KR')}</td>
      <td>${passedBadge}</td>
    </tr>`;
  }).join('');

  container.innerHTML = `
    <div class="table-wrap">
      <table class="data-table watchlist-table">
        <thead>
          <tr>
            <th>종목코드</th><th>현재가</th><th>등락률</th><th>거래량</th><th>스크리너</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ── Logs ─────────────────────────────────────────────────
async function fetchLogs() {
  try {
    const res  = await fetch('/api/logs');
    const logs = await res.json();

    if (logs.length === lastLogLen) return;
    lastLogLen = logs.length;

    const wrap = document.getElementById('logWrap');

    if (!logs.length) {
      wrap.innerHTML = `<div class="log-empty">아직 로그가 없습니다</div>`;
      return;
    }

    wrap.innerHTML = logs.map(e => `
      <div class="log-entry">
        <span class="log-time">${esc(e.time)}</span>
        <span class="log-badge ${esc(e.level)}">${esc(e.level)}</span>
        <span class="log-msg">${esc(e.message)}</span>
      </div>`).join('');

  } catch {/* silently retry */ }
}

function clearLogs() {
  lastLogLen = 0;
  document.getElementById('logWrap').innerHTML =
    `<div class="log-empty">아직 로그가 없습니다</div>`;
}

// ── Bot control ──────────────────────────────────────────
async function toggleBot() {
  const btn = document.getElementById('toggleBtn');
  btn.disabled = true;
  try {
    const ep  = isRunning ? '/api/stop' : '/api/start';
    await fetch(ep, { method: 'POST' });
    await fetchStatus();
  } finally {
    btn.disabled = false;
  }
}

// ── Strategy change ──────────────────────────────────────
async function changeStrategy(strategy) {
  if (isRunning) {
    alert('봇이 실행 중에는 전략을 변경할 수 없습니다.\n먼저 봇을 중지하세요.');
    return;
  }
  try {
    const res = await fetch('/api/strategy', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ strategy }),
    });
    const d = await res.json();
    if (d.status === 'ok') await fetchStatus();
    else alert(d.error ?? '전략 변경 실패');
  } catch (e) {
    console.error(e);
  }
}

// ── Footer clock ─────────────────────────────────────────
function updateClock() {
  const now = new Date();
  document.getElementById('footerTime').textContent =
    now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// ── Init ─────────────────────────────────────────────────
fetchStatus();
fetchBalance();
fetchWatchlist();
fetchLogs();
updateClock();

setInterval(fetchStatus,    3_000);
setInterval(fetchLogs,      5_000);
setInterval(fetchBalance,  60_000);
setInterval(fetchWatchlist, 60_000);
setInterval(updateClock,    1_000);
