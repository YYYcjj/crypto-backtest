"""
入场精度可视化仪表盘生成器 — 数据与HTML分离版
"""
import json
import os
from typing import List, Dict


def build_dashboard(json_path: str = "results/entry_analysis.json",
                    output_dir: str = "results"):
    """生成交互式可视化仪表盘"""

    with open(json_path, "r") as f:
        data = json.load(f)

    if not data:
        print("No data found")
        return

    # 提取摘要数据
    summaries = []
    for item in data:
        s = {k: v for k, v in item.items() if k != "results"}
        s["sample_results"] = item.get("results", [])[:20]
        summaries.append(s)

    # 保存瘦身数据
    data_json_path = os.path.join(output_dir, "dashboard_data.json")
    with open(data_json_path, "w") as f:
        json.dump(summaries, f, ensure_ascii=False, default=str)
    print(f"📦 数据已保存: {data_json_path} ({len(summaries)} 条)")

    # 收集元信息
    symbols = sorted(set(s["symbol"] for s in summaries))
    sl_pcts = sorted(set(s["sl_pct"] for s in summaries))

    # 生成纯HTML（数据从外部JSON加载）
    html = _render_html(symbols, sl_pcts)

    output_path = os.path.join(output_dir, "dashboard.html")
    with open(output_path, "w") as f:
        f.write(html)

    print(f"✅ 仪表盘已生成: {output_path}")
    return output_path


def _render_html(symbols: List[str], sl_pcts: List[float]) -> str:
    sl_options = ''.join(f'<option value="{p}">{p:.1f}%</option>' for p in sl_pcts)
    sym_options = ''.join(f'<option value="{s}">{s}</option>' for s in symbols)

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>入场精度分析仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {
    --bg: #0b1120; --card: #111827; --border: #1e293b; --text: #e2e8f0;
    --muted: #64748b; --accent: #38bdf8; --green: #22c55e; --red: #ef4444;
    --yellow: #f59e0b; --purple: #a855f7;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
.header { background:linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-bottom:1px solid var(--border); padding:20px 24px; position:sticky; top:0; z-index:100; }
.header h1 { font-size:20px; display:flex; align-items:center; gap:10px; }
.header .sub { color:var(--muted); font-size:13px; margin-top:4px; }
.controls { display:flex; gap:16px; flex-wrap:wrap; padding:16px 24px; background:var(--card); border-bottom:1px solid var(--border); align-items:center; }
.control-group { display:flex; align-items:center; gap:8px; }
.control-group label { font-size:12px; color:var(--muted); white-space:nowrap; }
select { background:#1e293b; color:var(--text); border:1px solid var(--border); padding:6px 12px; border-radius:6px; font-size:13px; cursor:pointer; outline:none; }
select:focus { border-color:var(--accent); }
.metric-tabs { display:flex; gap:2px; padding:0 24px; margin:16px 0 8px; flex-wrap:wrap; }
.tab { padding:8px 16px; font-size:13px; cursor:pointer; border:1px solid var(--border); border-bottom:none; border-radius:8px 8px 0 0; background:#0f172a; color:var(--muted); transition:all 0.2s; }
.tab:hover { color:var(--text); }
.tab.active { background:var(--card); color:var(--accent); border-bottom-color:var(--card); }
.cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px; padding:0 24px; margin-bottom:16px; }
.card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px; }
.card .label { font-size:12px; color:var(--muted); margin-bottom:4px; }
.card .value { font-size:28px; font-weight:700; }
.card .sub { font-size:12px; color:var(--muted); margin-top:4px; }
.main-content { padding:0 24px 24px; }
.chart-panel { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:20px; margin-bottom:16px; }
.chart-panel h3 { font-size:15px; margin-bottom:12px; }
.chart-wrap { position:relative; height:350px; }
.chart-wrap canvas { width:100% !important; }
.data-table { width:100%; border-collapse:collapse; font-size:13px; }
.data-table th { background:#0f172a; padding:10px 12px; text-align:left; border-bottom:2px solid var(--border); color:var(--muted); font-weight:600; position:sticky; top:0; }
.data-table td { padding:8px 12px; border-bottom:1px solid var(--border); }
.data-table tr:hover { background:rgba(56,189,248,0.05); }
.pos { color:var(--green); }
.neg { color:var(--red); }
.grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
@media (max-width:768px) { .grid-2 { grid-template-columns:1fr; } }
.empty { text-align:center; padding:40px; color:var(--muted); }
.loading { text-align:center; padding:60px; color:var(--muted); font-size:16px; }
</style>
</head>
<body>

<div class="header">
    <h1>&#128202; 入场精度分析仪表盘</h1>
    <p class="sub">15m 精确入场 &middot; 高位周期趋势确认 &middot; 止损存活率 + 盈利分布</p>
</div>

<div class="controls">
    <div class="control-group">
        <label>&#9878; 止损宽度</label>
        <select id="slSelect" onchange="filterData()">""" + sl_options + """</select>
    </div>
    <div class="control-group">
        <label>&#128270; 品种</label>
        <select id="symbolSelect" onchange="filterData()">
            <option value="all">全部品种</option>""" + sym_options + """</select>
    </div>
    <div class="control-group">
        <label>&#127919; 触发类型</label>
        <select id="triggerSelect" onchange="filterData()">
            <option value="all">全部类型</option>
            <option value="dmi_flip">DMI 翻多</option>
            <option value="srsi_bounce">StochRSI 超卖反弹</option>
            <option value="support_touch">支撑位触碰</option>
        </select>
    </div>
</div>

<div class="metric-tabs">
    <div class="tab active" onclick="switchTab('survival')">存活率 &amp; 盈亏</div>
    <div class="tab" onclick="switchTab('distribution')">盈利分布</div>
    <div class="tab" onclick="switchTab('triggers')">触发类型对比</div>
    <div class="tab" onclick="switchTab('stoptime')">止损时机</div>
    <div class="tab" onclick="switchTab('data')">数据明细</div>
</div>

<div class="cards" id="cardsRow"></div>

<div class="main-content">
    <div id="tab-survival" class="chart-panel">
        <h3>&#128200; 多品种存活率 &amp; 盈亏对比</h3>
        <div class="chart-wrap"><canvas id="chartSurvival"></canvas></div>
    </div>
    <div id="tab-distribution" class="chart-panel" style="display:none">
        <h3>&#128202; 盈利区间分布</h3>
        <div class="chart-wrap"><canvas id="chartDistribution"></canvas></div>
    </div>
    <div id="tab-triggers" class="chart-panel" style="display:none">
        <h3>&#127919; 触发类型对比</h3>
        <div class="grid-2">
            <div class="chart-wrap"><canvas id="chartTriggerStop"></canvas></div>
            <div class="chart-wrap"><canvas id="chartTriggerProfit"></canvas></div>
        </div>
    </div>
    <div id="tab-stoptime" class="chart-panel" style="display:none">
        <h3>&#9201; 止损发生时间分布</h3>
        <div class="chart-wrap"><canvas id="chartStopTime"></canvas></div>
    </div>
    <div id="tab-data" class="chart-panel" style="display:none">
        <h3>&#128203; 信号明细</h3>
        <div style="max-height:400px;overflow-y:auto;">
            <table class="data-table" id="dataTable">
                <thead><tr>
                    <th>品种</th><th>入场价</th><th>触发</th><th>1H</th><th>4H</th><th>1D</th>
                    <th>SRSI K</th><th>止损?</th><th>最大浮盈</th>
                </tr></thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
</div>

<script>
// ── Load Data ──
let ALL_DATA = [];
let currentTab = 'survival';
let charts = {};

const COLORS = ['#38bdf8', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#ec4899'];

fetch('dashboard_data.json')
    .then(r => r.json())
    .then(data => {
        ALL_DATA = data;
        updateCards();
        drawSurvivalChart();
        document.querySelector('.loading')?.remove();
    })
    .catch(err => {
        document.getElementById('cardsRow').innerHTML =
            '<div class="empty" style="color:var(--red)">&#9888; 数据加载失败:<br>' + err.message + '</div>';
    });

// ── Filtering ──
function getFilteredData() {
    const slVal = parseFloat(document.getElementById('slSelect').value);
    const symVal = document.getElementById('symbolSelect').value;
    const trigVal = document.getElementById('triggerSelect').value;
    return ALL_DATA.filter(item => {
        if (slVal && item.sl_pct !== slVal) return false;
        if (symVal !== 'all' && item.symbol !== symVal) return false;
        return true;
    });
}

function filterData() { updateCards(); refreshCharts(); if (currentTab === 'data') renderTable(); }

// ── Cards ──
function updateCards() {
    const filtered = getFilteredData();
    const row = document.getElementById('cardsRow');
    if (!filtered.length) { row.innerHTML = '<div class="empty">无匹配数据</div>'; return; }
    let totalSignals = 0, totalStopped = 0, weightedProfit = 0, totalSurvived = 0, bestSymbol = '', bestSurvive = 0;
    filtered.forEach(item => {
        totalSignals += item.total_signals;
        totalStopped += item.stopped;
        totalSurvived += item.survived;
        weightedProfit += item.avg_max_profit * item.survived;
        if (item.survive_rate > bestSurvive) { bestSurvive = item.survive_rate; bestSymbol = item.symbol; }
    });
    const overallSurvive = totalSurvived / totalSignals * 100;
    const avgProfit = totalSurvived > 0 ? weightedProfit / totalSurvived : 0;
    const sc = overallSurvive >= 70 ? 'var(--green)' : (overallSurvive >= 50 ? 'var(--yellow)' : 'var(--red)');
    const pc = avgProfit >= 2 ? 'var(--green)' : (avgProfit >= 1 ? 'var(--yellow)' : 'var(--muted)');
    row.innerHTML = `
        <div class="card"><div class="label">总信号数</div><div class="value" style="color:var(--accent)">${totalSignals.toLocaleString()}</div><div class="sub">来自 ${filtered.length} 个品种/档位</div></div>
        <div class="card"><div class="label">存活率</div><div class="value" style="color:${sc}">${overallSurvive.toFixed(1)}%</div><div class="sub">${totalSurvived} / ${totalSignals} 未止损</div></div>
        <div class="card"><div class="label">存活均盈</div><div class="value" style="color:${pc}">${avgProfit.toFixed(2)}%</div><div class="sub">最佳品种: ${bestSymbol} (${bestSurvive.toFixed(0)}%)</div></div>
        <div class="card"><div class="label">止损出局</div><div class="value" style="color:var(--red)">${totalStopped.toLocaleString()}</div><div class="sub">${(totalStopped/totalSignals*100).toFixed(1)}% 被扫掉</div></div>`;
}

// ── Charts ──
function destroyCharts() { Object.values(charts).forEach(c => c.destroy()); charts = {}; }

function refreshCharts() {
    destroyCharts();
    switch(currentTab) {
        case 'survival': drawSurvivalChart(); break;
        case 'distribution': drawDistributionChart(); break;
        case 'triggers': drawTriggerStopChart(); drawTriggerProfitChart(); break;
        case 'stoptime': drawStopTimeChart(); break;
    }
}

function makeChart(canvasId, type, data, options) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    charts[canvasId] = new Chart(ctx, { type, data, options });
}

function drawSurvivalChart() {
    const d = getFilteredData(); if (!d.length) return;
    makeChart('chartSurvival', 'bar', {
        labels: d.map(x => x.symbol + ' (' + x.sl_pct.toFixed(1) + '%)'),
        datasets: [
            { label: '存活率 %', data: d.map(x => x.survive_rate), yAxisID: 'y',
              backgroundColor: d.map(x => x.survive_rate >= 70 ? 'rgba(34,197,94,0.6)' : (x.survive_rate >= 50 ? 'rgba(245,158,11,0.6)' : 'rgba(239,68,68,0.6)')),
              borderColor: d.map(x => x.survive_rate >= 70 ? '#22c55e' : (x.survive_rate >= 50 ? '#f59e0b' : '#ef4444')),
              borderWidth: 2, borderRadius: 6 },
            { label: '均盈 %', data: d.map(x => x.avg_max_profit), type: 'line', yAxisID: 'y1',
              borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.1)', borderWidth: 2,
              pointRadius: 5, pointBackgroundColor: '#38bdf8', tension: 0.3 }
        ]
    }, {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8', usePointStyle: true } },
                   tooltip: { backgroundColor: '#1e293b' } },
        scales: {
            x: { ticks: { color: '#64748b', maxRotation: 45 } },
            y: { type: 'linear', position: 'left', min: 0, max: 100,
                 ticks: { color: '#64748b', callback: v => v + '%' },
                 title: { display: true, text: '存活率', color: '#64748b' } },
            y1: { type: 'linear', position: 'right', min: 0,
                  ticks: { color: '#38bdf8', callback: v => v + '%' },
                  title: { display: true, text: '均盈', color: '#38bdf8' }, grid: { display: false } }
        }
    });
}

function drawDistributionChart() {
    const d = getFilteredData(); if (!d.length) return;
    const buckets = ['<0%', '0-2%', '2-5%', '5-10%', '>10%'];
    makeChart('chartDistribution', 'bar', {
        labels: buckets,
        datasets: d.map((x, i) => ({
            label: x.symbol + ' (' + x.sl_pct.toFixed(1) + '%)',
            data: buckets.map(b => x.profit_buckets[b] || 0),
            backgroundColor: COLORS[i % COLORS.length] + '99',
            borderColor: COLORS[i % COLORS.length], borderWidth: 1, borderRadius: 4
        }))
    }, {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8', usePointStyle: true } }, tooltip: { backgroundColor: '#1e293b' } },
        scales: { x: { ticks: { color: '#64748b' } }, y: { ticks: { color: '#64748b' }, title: { display: true, text: '交易数', color: '#64748b' } } }
    });
}

function drawTriggerStopChart() {
    const d = getFilteredData(); if (!d.length) return;
    const names = { 'dmi_flip': 'DMI翻多', 'srsi_bounce': '超卖反弹', 'support_touch': '支撑触碰' };
    const triggers = d.length ? Object.keys(d[0].trigger_stats || {}) : [];
    makeChart('chartTriggerStop', 'bar', {
        labels: triggers.map(t => names[t] || t),
        datasets: d.map((x, i) => ({
            label: x.symbol, data: triggers.map(t => x.trigger_stats?.[t]?.stop_rate || 0),
            backgroundColor: COLORS[i % COLORS.length] + '99', borderColor: COLORS[i % COLORS.length], borderWidth: 1, borderRadius: 4
        }))
    }, {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8', usePointStyle: true } }, title: { display: true, text: '止损率 (%)', color: '#e2e8f0', font: { size: 14 } } },
        scales: { x: { ticks: { color: '#64748b' } }, y: { ticks: { color: '#64748b', callback: v => v + '%' }, min: 0, max: 100 } }
    });
}

function drawTriggerProfitChart() {
    const d = getFilteredData(); if (!d.length) return;
    const names = { 'dmi_flip': 'DMI翻多', 'srsi_bounce': '超卖反弹', 'support_touch': '支撑触碰' };
    const triggers = d.length ? Object.keys(d[0].trigger_stats || {}) : [];
    makeChart('chartTriggerProfit', 'bar', {
        labels: triggers.map(t => names[t] || t),
        datasets: d.map((x, i) => ({
            label: x.symbol, data: triggers.map(t => x.trigger_stats?.[t]?.avg_profit || 0),
            backgroundColor: COLORS[(i + 3) % COLORS.length] + '99', borderColor: COLORS[(i + 3) % COLORS.length], borderWidth: 1, borderRadius: 4
        }))
    }, {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8', usePointStyle: true } }, title: { display: true, text: '均盈 (%)', color: '#e2e8f0', font: { size: 14 } } },
        scales: { x: { ticks: { color: '#64748b' } }, y: { ticks: { color: '#64748b', callback: v => v + '%' } } }
    });
}

function drawStopTimeChart() {
    const d = getFilteredData(); if (!d.length) return;
    const merged = {};
    d.forEach(item => Object.entries(item.stop_bar_dist || {}).forEach(([k, v]) => { merged[k] = (merged[k] || 0) + v; }));
    const sorted = Object.entries(merged).sort((a, b) => { const na = parseInt(a[0].replace(/[^0-9]/g, '')) || 999; const nb = parseInt(b[0].replace(/[^0-9]/g, '')) || 999; return na - nb; });
    makeChart('chartStopTime', 'bar', {
        labels: sorted.map(s => s[0]),
        datasets: [{ label: '止损次数', data: sorted.map(s => s[1]),
            backgroundColor: sorted.map((_, i) => i < sorted.length - 1 ? 'rgba(239,68,68,0.5)' : 'rgba(245,158,11,0.7)'),
            borderColor: sorted.map((_, i) => i < sorted.length - 1 ? '#ef4444' : '#f59e0b'),
            borderWidth: 1, borderRadius: 4 }]
    }, {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1e293b' } },
        scales: { x: { ticks: { color: '#64748b' }, title: { display: true, text: '入场后第N根K线', color: '#64748b' } },
                  y: { ticks: { color: '#64748b' }, title: { display: true, text: '止损次数', color: '#64748b' } } }
    });
}

// ── Tab ──
function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    currentTab = tab;
    ['survival', 'distribution', 'triggers', 'stoptime', 'data'].forEach(t => {
        const el = document.getElementById('tab-' + t); if (el) el.style.display = t === tab ? '' : 'none';
    });
    destroyCharts();
    if (tab === 'survival') drawSurvivalChart();
    else if (tab === 'distribution') drawDistributionChart();
    else if (tab === 'triggers') { drawTriggerStopChart(); drawTriggerProfitChart(); }
    else if (tab === 'stoptime') drawStopTimeChart();
    else if (tab === 'data') renderTable();
}

// ── Table ──
function renderTable() {
    const filtered = getFilteredData();
    const tbody = document.querySelector('#dataTable tbody');
    tbody.innerHTML = '';
    const names = { 'dmi_flip': 'DMI翻多', 'srsi_bounce': '超卖反弹', 'support_touch': '支撑触碰' };
    filtered.forEach(item => (item.sample_results || []).forEach(r => {
        const sc = r.stopped ? 'neg' : 'pos';
        const pc = r.max_profit >= 2 ? 'pos' : (r.max_profit >= 0 ? '' : 'neg');
        tbody.innerHTML += `<tr><td>${item.symbol}</td><td>${(r.price||0).toFixed(2)}</td><td>${names[r.trigger]||r.trigger}</td><td>${r.trend_1h||'-'}</td><td>${r.trend_4h||'-'}</td><td>${r.trend_1d||'-'}</td><td>${(r.srs_k||0).toFixed(1)}</td><td class="${sc}">${r.stopped?'&#10007; 止损':'&#10003; 存活'}</td><td class="${pc}">${(r.max_profit||0).toFixed(2)}%</td></tr>`;
    }));
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    build_dashboard()
