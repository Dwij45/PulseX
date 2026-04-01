// ─────────────────────────────────────────────────
// CONFIG — change to your Render URL when deployed
// ─────────────────────────────────────────────────
// const API = "http://localhost:8000";
const API = "https://pulsex-z311.onrender.com/";

// ─────────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────────
let currentSymbol  = null;
let currentDays    = 30;
let currentChartMode = "candlestick"; // "candlestick" or "line"
let charts         = {};
let lwChart        = null;   // lightweight-charts instance
let sidebarData    = [];
let currentData    = [];     // store last fetched data for chart mode toggle

// ─────────────────────────────────────────────────
// CLOCK
// ─────────────────────────────────────────────────
setInterval(() => {
  document.getElementById("clock").textContent =
    new Date().toLocaleString("en-IN", {timeZone:"Asia/Kolkata",
      hour:"2-digit",minute:"2-digit",second:"2-digit",
      day:"2-digit",month:"short"}) + " IST";
}, 1000);

// ─────────────────────────────────────────────────
// BANNER COUNTDOWN
// ─────────────────────────────────────────────────
function updateBannerCountdown() {
  const now = new Date();
  const ist = new Date(now.toLocaleString("en-US", {timeZone:"Asia/Kolkata"}));
  const target = new Date(ist);
  target.setHours(16, 0, 0, 0);
  const day = ist.getDay();
  if (day === 0) target.setDate(target.getDate() + 1);
  else if (day === 6) target.setDate(target.getDate() + 2);
  else if (ist >= target) {
    target.setDate(target.getDate() + 1);
    const nd = target.getDay();
    if (nd === 6) target.setDate(target.getDate() + 2);
    if (nd === 0) target.setDate(target.getDate() + 1);
  }
  const diff = Math.max(0, target - ist);
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  const el = document.getElementById("bannerCountdown");
  if (el) el.textContent = `${String(h).padStart(2,"0")}h ${String(m).padStart(2,"0")}m ${String(s).padStart(2,"0")}s`;
}
updateBannerCountdown();
setInterval(updateBannerCountdown, 1000);

// ─────────────────────────────────────────────────
// API HELPER
// ─────────────────────────────────────────────────
async function api(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

// ─────────────────────────────────────────────────
// SIDEBAR
// ─────────────────────────────────────────────────
async function loadSidebar() {
  try {
    sidebarData = await api("/sidebar");
    const sectors = {};
    sidebarData.forEach(c => {
      if (!sectors[c.sector]) sectors[c.sector] = [];
      sectors[c.sector].push(c);
    });
    const sb = document.getElementById("sidebar");
    sb.innerHTML = "";
    Object.entries(sectors).forEach(([sector, companies]) => {
      const sec = document.createElement("div");
      sec.className = "sidebar-section";
      sec.innerHTML = `<div class="sidebar-label">${sector}</div>`;
      companies.forEach(c => {
        const price  = c.close != null ? `₹${Number(c.close).toLocaleString("en-IN",{maximumFractionDigits:2})}` : "—";
        const ret    = c.daily_return != null ? c.daily_return : null;
        const retStr = ret != null ? (ret >= 0 ? `+${ret.toFixed(2)}%` : `${ret.toFixed(2)}%`) : "—";
        const cls    = ret == null ? "" : ret >= 0 ? "pos" : "neg";
        const name   = (c.full_name || c.symbol).split(" ").slice(0,3).join(" ");
        const btn = document.createElement("button");
        btn.className = "stock-btn";
        btn.id = `btn-${c.symbol}`;
        btn.innerHTML = `
          <div>
            <div class="sym">${c.symbol}</div>
            <div class="sname">${name}</div>
          </div>
          <div class="price-block">
            <div class="price">${price}</div>
            <div class="ret ${cls}">${retStr}</div>
          </div>`;
        btn.onclick = () => loadStock(c.symbol, c.full_name || c.symbol);
        sec.appendChild(btn);
      });
      sb.appendChild(sec);
    });
    if (sidebarData.length > 0 && !currentSymbol) {
      loadStock(sidebarData[0].symbol, sidebarData[0].full_name || sidebarData[0].symbol);
    }
  } catch(e) {
    console.error("Sidebar error:", e);
    document.getElementById("sidebar").innerHTML = `
      <div style="padding:16px;font-family:var(--font-m);font-size:10px;color:var(--red-bright);line-height:2">
        API offline<br><br>
        <span style="color:var(--muted)">Start server:<br>uvicorn main:app --reload</span>
      </div>`;
  }
}

// ─────────────────────────────────────────────────
// LOAD STOCK
// ─────────────────────────────────────────────────
async function loadStock(symbol, fullName) {
  currentSymbol = symbol;
  document.querySelectorAll(".stock-btn").forEach(b =>
    b.classList.toggle("active", b.id === `btn-${symbol}`)
  );
  document.getElementById("main").innerHTML =
    `<div class="loading"><div class="ld"></div><div class="ld"></div><div class="ld"></div>LOADING ${symbol}</div>`;
  try {
    const [data, summary] = await Promise.all([
      api(`/data/${symbol}?days=${currentDays}`),
      api(`/summary/${symbol}`)
    ]);
    currentData = data;
    renderMain(symbol, fullName, data, summary);
  } catch(e) {
    document.getElementById("main").innerHTML =
      `<div class="loading" style="color:var(--red-bright)">Error: ${e.message}</div>`;
  }
}

// ─────────────────────────────────────────────────
// RENDER MAIN
// ─────────────────────────────────────────────────
function renderMain(symbol, fullName, data, summary) {
  // Destroy all Chart.js charts
  Object.values(charts).forEach(c => { try { c.destroy(); } catch(e){} });
  charts = {};
  // Destroy lightweight-charts instance
  if (lwChart) { try { lwChart.remove(); } catch(e){} lwChart = null; }

  const ret     = summary.latest_daily_return ?? 0;
  const retStr  = ret >= 0 ? `+${ret.toFixed(2)}%` : `${ret.toFixed(2)}%`;
  const retCls  = ret >= 0 ? "pos" : "neg";
  const rsi     = summary.latest_rsi;
  const zone    = summary.rsi_zone || "neutral";
  const badgeCls= zone==="overbought"?"ob":zone==="oversold"?"os":"neu";
  const beta    = summary.beta_vs_nifty;
  const close   = summary.latest_close;

  document.getElementById("main").className = "main fade-in";
  document.getElementById("main").innerHTML = `

    <div class="page-header">
      <div>
        <div class="stock-title">${symbol}</div>
        <div class="stock-fullname">${fullName}</div>
      </div>
      <div class="time-filters">
        ${[30,90,180,365].map(d =>
          `<button class="tf-btn ${d===currentDays?'active':''}" onclick="changeDays(${d})">${d}D</button>`
        ).join("")}
      </div>
    </div>

    <div class="cards-row">
      <div class="card">
        <div class="card-label">Price</div>
        <div class="card-value">₹${close!=null?Number(close).toLocaleString("en-IN",{maximumFractionDigits:2}):"—"}</div>
        <div class="card-sub">${summary.latest_date||"—"}</div>
      </div>
      <div class="card">
        <div class="card-label">Daily Return</div>
        <div class="card-value ${retCls}">${retStr}</div>
        <div class="card-sub">vs open price</div>
      </div>
      <div class="card">
        <div class="card-label">52W High</div>
        <div class="card-value pos">₹${summary.week52_high!=null?Number(summary.week52_high).toLocaleString("en-IN",{maximumFractionDigits:2}):"—"}</div>
        <div class="card-sub">rolling max close</div>
      </div>
      <div class="card">
        <div class="card-label">52W Low</div>
        <div class="card-value neg">₹${summary.week52_low!=null?Number(summary.week52_low).toLocaleString("en-IN",{maximumFractionDigits:2}):"—"}</div>
        <div class="card-sub">rolling min close</div>
      </div>
      <div class="card">
        <div class="card-label">RSI-14 <span class="rsi-badge ${badgeCls}">${zone}</span></div>
        <div class="card-value ${badgeCls==='ob'?'neg':badgeCls==='os'?'pos':''}">${rsi!=null?rsi.toFixed(1):"—"}</div>
        <div class="card-sub">70 overbought / 30 oversold</div>
      </div>
      <div class="card">
        <div class="card-label">Beta vs Nifty</div>
        <div class="card-value ${beta!=null&&beta>1.2?'neg':beta!=null&&beta<0.8?'pos':''}">${beta!=null?beta.toFixed(3):"—"}</div>
        <div class="card-sub">${beta!=null?(beta>1?"more volatile":beta<1?"less volatile":"≈ market"):"add ^NSEI to fetch"}</div>
      </div>
    </div>

    <div class="chart-grid-top">
      <div class="chart-box">
        <div class="chart-box-title">
          <span></span>PRICE CHART
          <div class="chart-toggle">
            <button class="ct-btn ${currentChartMode==='candlestick'?'active':''}" onclick="switchChartMode('candlestick')">Candlestick</button>
            <button class="ct-btn ${currentChartMode==='line'?'active':''}" onclick="switchChartMode('line')">Line + MA</button>
          </div>
        </div>
        <div id="priceChartWrap" style="position:relative;height:260px"></div>
      </div>
      <div class="chart-box">
        <div class="chart-box-title"><span></span>TOP MOVERS TODAY</div>
        <div id="moversBox"><div class="loading" style="height:60px"><div class="ld"></div><div class="ld"></div><div class="ld"></div></div></div>
      </div>
    </div>

    <div class="chart-grid-bot">
      <div class="chart-box">
        <div class="chart-box-title"><span></span>VOLUME</div>
        <div style="position:relative;height:170px"><canvas id="cVol"></canvas></div>
      </div>
      <div class="chart-box">
        <div class="chart-box-title"><span></span>RSI — 14 DAY</div>
        <div style="position:relative;height:170px"><canvas id="cRsi"></canvas></div>
      </div>
      <div class="chart-box">
        <div class="chart-box-title"><span></span>VOLATILITY — 7 DAY</div>
        <div style="position:relative;height:170px"><canvas id="cVolty"></canvas></div>
      </div>
    </div>

    <div class="chart-box" style="margin-bottom:12px">
      <div class="chart-box-title"><span></span>CORRELATION MATRIX</div>
      <div id="heatmapBox"><div class="loading" style="height:60px"><div class="ld"></div><div class="ld"></div><div class="ld"></div></div></div>
    </div>
  `;

  // Build price chart in current mode
  buildPriceChart(data);

  // Build other Chart.js charts
  const labels = data.map(d => (d.date||"").slice(5));
  buildVolume(labels, data);
  buildRSI(labels, data);
  buildVolatility(labels, data);
  loadMovers();
  loadHeatmap();
}

// ─────────────────────────────────────────────────
// PRICE CHART — candlestick OR line with MA toggle
// ─────────────────────────────────────────────────
function buildPriceChart(data) {
  if (lwChart) { try { lwChart.remove(); } catch(e){} lwChart = null; }
  if (charts.price) { try { charts.price.destroy(); } catch(e){} delete charts.price; }

  const wrap = document.getElementById("priceChartWrap");
  if (!wrap) return;

  if (currentChartMode === "candlestick") {
    buildCandlestick(wrap, data);
  } else {
    buildLineMA(wrap, data);
  }
}

function buildCandlestick(wrap, data) {
  // Use a canvas inside the wrap for lightweight-charts
  wrap.innerHTML = "";

  lwChart = LightweightCharts.createChart(wrap, {
    width:  wrap.clientWidth || 600,
    height: 260,
    layout: {
      background: { color: "#111010" },
      textColor:  "#8a8070",
    },
    grid: {
      vertLines: { color: "rgba(255,255,255,0.03)" },
      horzLines: { color: "rgba(255,255,255,0.04)" },
    },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#1e1a17" },
    timeScale: {
      borderColor: "#1e1a17",
      timeVisible: true,
    },
  });

  const candleSeries = lwChart.addCandlestickSeries({
    upColor:       "#2ecc71",
    downColor:     "#c0392b",
    borderVisible: false,
    wickUpColor:   "#2ecc71",
    wickDownColor: "#c0392b",
  });

  const candleData = data
    .filter(d => d.open && d.high && d.low && d.close)
    .map(d => ({
      time:  d.date,
      open:  d.open,
      high:  d.high,
      low:   d.low,
      close: d.close,
    }));

  candleSeries.setData(candleData);
  lwChart.timeScale().fitContent();

  // Resize observer so chart fills container
  if (window.ResizeObserver) {
    new ResizeObserver(() => {
      if (lwChart) lwChart.applyOptions({ width: wrap.clientWidth });
    }).observe(wrap);
  }
}

function buildLineMA(wrap, data) {
  wrap.innerHTML = `<canvas id="cPrice"></canvas>`;
  const canvas = document.getElementById("cPrice");

  const labels = data.map(d => (d.date||"").slice(5));
  charts.price = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label:"Close", data:data.map(d=>d.close), borderColor:"#f0ece4", borderWidth:1.5, pointRadius:0, tension:0.3, fill:false },
        { label:"MA 7",  data:data.map(d=>d.ma_7),  borderColor:"#c0392b", borderWidth:1.2, pointRadius:0, tension:0.3, fill:false, borderDash:[4,3] },
        { label:"MA 20", data:data.map(d=>d.ma_20), borderColor:"#e67e22", borderWidth:1.2, pointRadius:0, tension:0.3, fill:false, borderDash:[6,4] },
      ]
    },
    options: { ...CD, maintainAspectRatio: false }
  });

  // Make canvas fill the wrap height
  canvas.style.height = "260px";
}

function switchChartMode(mode) {
  currentChartMode = mode;
  // Update toggle button states
  document.querySelectorAll(".ct-btn").forEach(b => {
    b.classList.toggle("active", b.textContent.toLowerCase().includes(mode === "candlestick" ? "candle" : "line"));
  });
  buildPriceChart(currentData);
}

// ─────────────────────────────────────────────────
// CHART DEFAULTS (Chart.js)
// ─────────────────────────────────────────────────
const CD = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: true, labels: { color:"#8a8070", font:{family:"JetBrains Mono",size:10}, boxWidth:10 } },
    tooltip: { backgroundColor:"#111010", borderColor:"#1e1a17", borderWidth:1,
      titleColor:"#f0ece4", bodyColor:"#8a8070",
      titleFont:{family:"Barlow Condensed",size:13,weight:"700"},
      bodyFont:{family:"JetBrains Mono",size:10} }
  },
  scales: {
    x: { grid:{color:"rgba(255,255,255,0.03)"}, ticks:{color:"#8a8070",font:{family:"JetBrains Mono",size:9},maxTicksLimit:8} },
    y: { grid:{color:"rgba(255,255,255,0.04)"}, ticks:{color:"#8a8070",font:{family:"JetBrains Mono",size:9}} }
  }
};

function buildVolume(labels, data) {
  charts.vol = new Chart(document.getElementById("cVol"), {
    type:"bar",
    data:{labels, datasets:[{
      label:"Volume", data:data.map(d=>d.volume),
      backgroundColor:data.map(d=>(d.daily_return||0)>=0?"rgba(46,204,113,0.5)":"rgba(192,57,43,0.5)"),
      borderWidth:0
    }]},
    options:{...CD, plugins:{...CD.plugins, legend:{display:false}}}
  });
}

function buildRSI(labels, data) {
  charts.rsi = new Chart(document.getElementById("cRsi"), {
    type:"line",
    data:{labels, datasets:[{
      label:"RSI-14", data:data.map(d=>d.rsi_14),
      borderColor:"#c0392b", borderWidth:1.5, pointRadius:0, tension:0.3, fill:false
    }]},
    options:{...CD,
      plugins:{...CD.plugins, legend:{display:false},
        annotation:{annotations:{
          ob:{type:"line",yMin:70,yMax:70,borderColor:"rgba(192,57,43,0.5)",borderWidth:1,borderDash:[4,3]},
          os:{type:"line",yMin:30,yMax:30,borderColor:"rgba(46,204,113,0.4)",borderWidth:1,borderDash:[4,3]}
        }}
      },
      scales:{...CD.scales, y:{...CD.scales.y, min:0, max:100}}
    }
  });
}

function buildVolatility(labels, data) {
  charts.volty = new Chart(document.getElementById("cVolty"), {
    type:"line",
    data:{labels, datasets:[{
      label:"Volatility-7", data:data.map(d=>d.volatility_7),
      borderColor:"#e67e22", borderWidth:1.5,
      backgroundColor:"rgba(230,126,34,0.08)",
      pointRadius:0, tension:0.3, fill:true
    }]},
    options:{...CD, plugins:{...CD.plugins, legend:{display:false}}}
  });
}

// ─────────────────────────────────────────────────
// TOP MOVERS
// ─────────────────────────────────────────────────
async function loadMovers() {
  try {
    const d = await api("/top-movers?n=4");
    const box = document.getElementById("moversBox");
    if (!box) return;
    box.innerHTML = `
      <div class="movers-grid">
        <div class="movers-col">
          <div class="movers-head">▲ GAINERS</div>
          ${(d.gainers||[]).map(m=>`
            <div class="mover-row">
              <span class="mover-sym">${m.symbol}</span>
              <span class="mover-ret pos">+${(m.daily_return||0).toFixed(2)}%</span>
            </div>`).join("")}
        </div>
        <div class="movers-col" style="border-left:1px solid var(--border);padding-left:10px">
          <div class="movers-head">▼ LOSERS</div>
          ${(d.losers||[]).map(m=>`
            <div class="mover-row">
              <span class="mover-sym">${m.symbol}</span>
              <span class="mover-ret neg">${(m.daily_return||0).toFixed(2)}%</span>
            </div>`).join("")}
        </div>
      </div>
      <div style="font-family:var(--font-m);font-size:9px;color:var(--muted);margin-top:10px">${d.date||""}</div>`;
  } catch(e) {
    const box = document.getElementById("moversBox");
    if (box) box.innerHTML = `<div style="font-size:11px;color:var(--muted);font-family:var(--font-m);padding:10px 0">No movers data yet</div>`;
  }
}

// ─────────────────────────────────────────────────
// CORRELATION HEATMAP
// ─────────────────────────────────────────────────
async function loadHeatmap() {
  try {
    const data   = await api("/correlation");
    const matrix = data.correlation_matrix;
    const syms   = Object.keys(matrix);
    const box    = document.getElementById("heatmapBox");
    if (!box || !syms.length) return;
    function heatColor(v) {
      if (v == null) return "#1a1a1a";
      v = Math.max(-1, Math.min(1, v));
      if (v >= 0) return `rgba(${Math.round(122+70*v)},${Math.round(26+31*v)},${Math.round(15+28*v)},${0.3+0.7*v})`;
      const a = Math.abs(v);
      return `rgba(20,${Math.round(80+80*a)},${Math.round(40+80*a)},${0.3+0.7*a})`;
    }
    let html = `<div class="heatmap-wrap"><table class="heatmap-table">
      <thead><tr><th></th>${syms.map(s=>`<th>${s}</th>`).join("")}</tr></thead><tbody>`;
    syms.forEach(s1 => {
      html += `<tr><th style="text-align:right;padding-right:10px;color:var(--muted)">${s1}</th>`;
      syms.forEach(s2 => {
        const val = matrix[s1]?.[s2];
        html += `<td style="background:${heatColor(val)};color:var(--white)" title="${s1}↔${s2}: ${val!=null?val.toFixed(3):'—'}">${val!=null?val.toFixed(2):"—"}</td>`;
      });
      html += `</tr>`;
    });
    html += `</tbody></table></div>
      <div style="font-family:var(--font-m);font-size:9px;color:var(--muted);margin-top:8px">
        Computed: ${data.computed_date} &nbsp;|&nbsp; Red = positive correlation &nbsp;|&nbsp; Green = negative
      </div>`;
    box.innerHTML = html;
  } catch(e) {
    const box = document.getElementById("heatmapBox");
    if (box) box.innerHTML = `<div style="font-size:11px;color:var(--muted);font-family:var(--font-m);padding:10px 0">Run pipeline once to generate correlation data</div>`;
  }
}

// ─────────────────────────────────────────────────
// TIME FILTER
// ─────────────────────────────────────────────────
function changeDays(days) {
  currentDays = days;
  if (currentSymbol) {
    const c = sidebarData.find(x => x.symbol === currentSymbol);
    loadStock(currentSymbol, c?.full_name || currentSymbol);
  }
}

// ─────────────────────────────────────────────────
// REFRESH BUTTON — fixed with proper timeout handling
// pipeline can take 3-5 min on first run
// ─────────────────────────────────────────────────
async function triggerPipeline() {
  const btn    = document.getElementById("refreshBtn");
  const status = document.getElementById("refreshStatus");

  btn.disabled = true;
  btn.classList.add("loading");
  btn.innerHTML = `<span class="spin">↻</span> Running...`;
  status.textContent = "Pipeline running (may take 2-5 min)...";
  status.style.color = "var(--orange)";

  try {
    // Use AbortController with 10 minute timeout
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 600000); // 10 min

    const result = await fetch(`${API}/pipeline/run`, {
      method: "POST",
      signal: controller.signal,
      headers: { "Content-Type": "application/json" }
    });
    clearTimeout(timeout);

    if (result.ok) {
      status.textContent = "✓ Pipeline complete — data updated";
      status.style.color = "var(--green)";
      // Reload sidebar with fresh prices
      await loadSidebar();
      // Reload current chart
      if (currentSymbol) {
        const c = sidebarData.find(x => x.symbol === currentSymbol);
        loadStock(currentSymbol, c?.full_name || currentSymbol);
      }
    } else {
      const err = await result.json().catch(() => ({}));
      status.textContent = `✗ Failed: ${err.detail || result.status}`;
      status.style.color = "var(--red-bright)";
    }
  } catch(e) {
    if (e.name === "AbortError") {
      status.textContent = "✗ Timed out — check server logs";
    } else {
      status.textContent = `✗ Error: ${e.message}`;
    }
    status.style.color = "var(--red-bright)";
  }

  btn.disabled = false;
  btn.classList.remove("loading");
  btn.innerHTML = `<span class="spin">↻</span> Refresh Data`;
  setTimeout(() => { status.textContent = ""; }, 8000);
}

// ─────────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────────
loadSidebar();
