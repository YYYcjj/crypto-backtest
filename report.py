"""
报告生成器 — HTML可视化报告
"""
import json
import os
from datetime import datetime, timezone
from typing import List, Dict


def generate_html_report(all_results: List[Dict], config, output_dir: str = "results"):
    """生成HTML回测报告"""
    os.makedirs(output_dir, exist_ok=True)

    # 汇总统计
    total_trades = sum(r["total_trades"] for r in all_results)
    total_pnl = sum(r["total_pnl"] for r in all_results)
    total_win = sum(r["win_trades"] for r in all_results)
    overall_win_rate = round(total_win / total_trades * 100, 1) if total_trades > 0 else 0
    overall_return = round(total_pnl / config.initial_capital * 100, 2)

    # 构造Chart.js数据
    equity_labels = []
    equity_data = []
    if all_results and all_results[0].get("equity_curve"):
        for pt in all_results[0]["equity_curve"][::max(1, len(all_results[0]["equity_curve"]) // 200)]:
            equity_labels.append(datetime.fromtimestamp(pt["ts"] / 1000, tz=timezone.utc).strftime("%m-%d %H:%M"))
            equity_data.append(round(pt["equity"], 2))

    # 交易明细
    all_trades = []
    for r in all_results:
        for t in r.get("trades", []):
            t["symbol"] = r["symbol"]
            all_trades.append(t)
    all_trades.sort(key=lambda x: x["entry_time"])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>策略回测报告 — OKX Strategy Engine v4</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1419; color: #e7e9ea; padding: 20px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1 {{ font-size: 24px; margin-bottom: 5px; color: #1d9bf0; }}
.subtitle {{ color: #71767b; margin-bottom: 30px; font-size: 14px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 30px; }}
.card {{ background: #1a1f26; border: 1px solid #2f3336; border-radius: 12px; padding: 20px; }}
.card .label {{ font-size: 12px; color: #71767b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
.card .value {{ font-size: 28px; font-weight: 700; }}
.card .value.positive {{ color: #00ba7c; }}
.card .value.negative {{ color: #f4212e; }}
.card .value.neutral {{ color: #e7e9ea; }}
.chart-container {{ background: #1a1f26; border: 1px solid #2f3336; border-radius: 12px; padding: 20px; margin-bottom: 30px; }}
.chart-container h2 {{ font-size: 16px; margin-bottom: 15px; color: #e7e9ea; }}
table {{ width: 100%; border-collapse: collapse; background: #1a1f26; border-radius: 12px; overflow: hidden; margin-bottom: 30px; }}
th {{ background: #2f3336; padding: 12px 16px; text-align: left; font-size: 13px; color: #71767b; font-weight: 600; }}
td {{ padding: 10px 16px; font-size: 13px; border-bottom: 1px solid #2f3336; }}
tr:hover td {{ background: #1d2330; }}
.positive {{ color: #00ba7c; }}
.negative {{ color: #f4212e; }}
.summary-table {{ margin-bottom: 20px; }}
.summary-table td:first-child {{ color: #71767b; width: 140px; }}
</style>
</head>
<body>
<div class="container">
<h1>📊 策略回测报告</h1>
<div class="subtitle">
    策略引擎 v4 · 多时间框架: {', '.join(config.timeframes)} · 主周期: {config.primary_tf} ·
    回测{config.backtest_days}天 · {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>

<div class="cards">
    <div class="card">
        <div class="label">总收益率</div>
        <div class="value {'positive' if overall_return > 0 else 'negative' if overall_return < 0 else 'neutral'}">{overall_return:+.2f}%</div>
    </div>
    <div class="card">
        <div class="label">总盈亏</div>
        <div class="value {'positive' if total_pnl > 0 else 'negative' if total_pnl < 0 else 'neutral'}">¥{total_pnl:,.2f}</div>
    </div>
    <div class="card">
        <div class="label">总交易次数</div>
        <div class="value neutral">{total_trades}</div>
    </div>
    <div class="card">
        <div class="label">胜率</div>
        <div class="value {'positive' if overall_win_rate >= 50 else 'negative'}">{overall_win_rate}%</div>
    </div>
    <div class="card">
        <div class="label">初始资金</div>
        <div class="value neutral">¥{config.initial_capital:,.0f}</div>
    </div>
    <div class="card">
        <div class="label">最终资金</div>
        <div class="value {'positive' if total_pnl > 0 else 'negative'}">¥{config.initial_capital + total_pnl:,.2f}</div>
    </div>
</div>

<div class="chart-container">
    <h2>权益曲线</h2>
    <canvas id="equityChart" height="80"></canvas>
</div>

<h2 style="margin-bottom:15px;">按品种汇总</h2>
<table>
<thead>
<tr>
    <th>品种</th><th>交易数</th><th>胜率</th><th>总盈亏</th><th>收益率</th>
    <th>最大回撤</th><th>夏普比</th><th>盈亏比</th><th>多/空</th>
</tr>
</thead>
<tbody>
"""
    for r in all_results:
        if r["total_trades"] == 0:
            continue
        pnl_class = "positive" if r["total_pnl"] > 0 else "negative"
        wr_class = "positive" if r["win_rate"] >= 50 else "negative"
        html += f"""<tr>
    <td><strong>{r['symbol']}</strong></td>
    <td>{r['total_trades']}</td>
    <td class="{wr_class}">{r['win_rate']}%</td>
    <td class="{pnl_class}">¥{r['total_pnl']:,.2f}</td>
    <td class="{pnl_class}">{r['total_return']:+.2f}%</td>
    <td>{r['max_drawdown']}%</td>
    <td>{r['sharpe']:.2f}</td>
    <td>{r['profit_factor']}</td>
    <td>{r['long_count']}/{r['short_count']}</td>
</tr>"""

    html += """
</tbody>
</table>

<h2 style="margin-bottom:15px;">交易明细 (最近100笔)</h2>
<table>
<thead>
<tr>
    <th>品种</th><th>方向</th><th>入场时间</th><th>出场时间</th>
    <th>入场价</th><th>出场价</th><th>盈亏</th><th>盈亏%</th><th>阶梯</th><th>原因</th>
</tr>
</thead>
<tbody>
"""
    for t in all_trades[-100:]:
        pnl_class = "positive" if t["pnl"] > 0 else "negative"
        dir_class = "positive" if t["direction"] == "LONG" else "negative"
        html += f"""<tr>
    <td>{t['symbol']}</td>
    <td class="{dir_class}">{t['direction']}</td>
    <td>{t['entry_time']}</td>
    <td>{t['exit_time']}</td>
    <td>{t['entry']:.4f}</td>
    <td>{t['exit']:.4f}</td>
    <td class="{pnl_class}">¥{t['pnl']:,.2f}</td>
    <td class="{pnl_class}">{t['pnl_pct']:+.2f}%</td>
    <td>{t['steps']}</td>
    <td>{t['reason']}</td>
</tr>"""

    html += f"""
</tbody>
</table>
</div>
<script>
new Chart(document.getElementById('equityChart'), {{
    type: 'line',
    data: {{
        labels: {json.dumps(equity_labels)},
        datasets: [{{
            label: '权益',
            data: {json.dumps(equity_data)},
            borderColor: '#1d9bf0',
            backgroundColor: 'rgba(29, 155, 240, 0.1)',
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            borderWidth: 1.5
        }}, {{
            label: '初始资金',
            data: {json.dumps([config.initial_capital] * len(equity_labels))},
            borderColor: '#71767b',
            borderDash: [5, 5],
            borderWidth: 1,
            pointRadius: 0,
            fill: false
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ labels: {{ color: '#71767b' }} }} }},
        scales: {{
            x: {{ ticks: {{ color: '#71767b', maxTicksLimit: 20 }} }},
            y: {{ ticks: {{ color: '#71767b', callback: v => '¥' + v.toLocaleString() }} }}
        }},
        interaction: {{ intersect: false, mode: 'index' }}
    }}
}});
</script>
</body>
</html>"""

    report_path = os.path.join(output_dir, "backtest_report.html")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    # 同时保存JSON
    json_path = os.path.join(output_dir, "backtest_results.json")
    json_data = []
    for r in all_results:
        jr = {k: v for k, v in r.items() if k not in ("trades", "equity_curve")}
        json_data.append(jr)
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"\n📄 HTML报告: {report_path}")
    print(f"📄 JSON数据: {json_path}")
    return report_path
