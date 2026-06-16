"""
入场精度分析 — 15m 精确入场 + 高位周期趋势确认
测试指定止损宽度下的存活率和盈利表现

核心问题：2% 止损下，多少比例的交易不会被正常波动扫掉？
"""
import json
import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from data_fetcher import fetch_historical, TF_SECONDS
from indicators import calc_dmi_adx, calc_stoch_rsi, calc_atr, find_pivots


@dataclass
class EntrySignal:
    """一个入场信号"""
    ts: int           # 入场时间戳(ms)
    price: float      # 入场价
    atr: float        # 入场时的 ATR
    dmi_15m: str      # 15m DMI方向
    adx_15m: float    # 15m ADX
    srsi_k: float     # StochRSI K值
    trend_1h: str     # 1H趋势方向
    trend_4h: str     # 4H趋势方向
    trend_1d: str     # 1D趋势方向
    near_support: bool  # 是否靠近关键支撑
    trigger: str      # 触发类型: dmi_flip / srsi_bounce / support_touch


@dataclass
class ForwardResult:
    """入场后的前瞻分析结果"""
    signal: EntrySignal
    stopped: bool = False  # 是否被止损
    stop_hit_bar: int = 0  # 第几根K线被止损（从入场算）
    max_profit_pct: float = 0.0   # 最大浮盈百分比
    max_profit_bar: int = 0  # 达到最大浮盈的第几根K线
    max_loss_pct: float = 0.0    # 最大浮亏百分比
    exit_bar: int = 0    # 离场K线（止损或被追踪止盈）
    exit_price: float = 0.0


class EntryAnalyzer:
    """入场精度分析器"""

    def __init__(self, sl_pct: float = 0.02, forward_bars: int = 96,
                 trend_tf_map: dict = None):
        """
        sl_pct: 止损百分比（2%=0.02）
        forward_bars: 入场后向前看多少根K线（96 × 15m = 24h）
        trend_tf_map: 高位周期 → 权重 {"1H": 2, "4H": 3, "1D": 4}
        """
        self.sl_pct = sl_pct
        self.forward_bars = forward_bars
        self.trend_tf_map = trend_tf_map or {"1H": 2, "4H": 3, "1D": 4}

    def compute_trend(self, candles: List[Dict], tf_name: str) -> Dict:
        """计算某个TF的趋势状态"""
        if len(candles) < 100:
            return {"dmi_dir": "平", "adx": 0, "di_diff": 0,
                    "is_bull": False, "is_bear": False, "score": 0}

        dmi_dir, adx, di_diff = calc_dmi_adx(candles, 14)
        closes = [c["c"] for c in candles]

        # EMA 50/200 趋势
        if len(closes) >= 200:
            ema50 = sum(closes[-50:]) / 50
            ema200 = sum(closes[-200:]) / 200
            ema_bull = ema50 > ema200
            ema_bear = ema50 < ema200
        else:
            ema_bull = False
            ema_bear = False

        # 趋势得分
        score = self.trend_tf_map.get(tf_name, 0)
        bull_ok = dmi_dir == "多" or (adx < 20 and ema_bull)
        bear_ok = dmi_dir == "空" or (adx < 20 and ema_bear)

        return {
            "dmi_dir": dmi_dir,
            "adx": adx,
            "di_diff": di_diff,
            "ema_bull": ema_bull,
            "ema_bear": ema_bear,
            "is_bull": bull_ok,
            "is_bear": bear_ok,
            "score": score if bull_ok else (score if bear_ok else 0),
        }

    def compute_direction_score(self, trends: Dict[str, Dict]) -> Tuple[int, int]:
        """汇总所有高位周期的方向分"""
        bull_score = 0
        bear_score = 0
        for tf, t in trends.items():
            if t["is_bull"]:
                bull_score += t["score"]
            if t["is_bear"]:
                bear_score += t["score"]
        return bull_score, bear_score

    def find_entries_15m(self, candles_15m: List[Dict],
                         higher_trends: Dict[str, List[Dict]],
                         require_bull: bool = True) -> List[EntrySignal]:
        """
        在 15m K线上扫描入场信号
        require_bull: 是否要求高位周期整体看多
        """
        n = len(candles_15m)
        if n < 50:
            return []

        # 计算高位周期趋势
        trends = {}
        for tf, tf_candles in higher_trends.items():
            if tf_candles:
                trends[tf] = self.compute_trend(tf_candles, tf)

        bull_score, bear_score = self.compute_direction_score(trends)

        # 不满足趋势要求
        if require_bull and bull_score < 4:
            return []
        if not require_bull and bear_score < 4:
            return []

        signals = []
        closes = [c["c"] for c in candles_15m]
        highs = [c["h"] for c in candles_15m]
        lows = [c["l"] for c in candles_15m]

        # 逐K线扫描 15m
        for i in range(50, n - 1):
            # 计算当前点的 DMI
            sub = candles_15m[:i + 1]
            dmi_dir, adx, _ = calc_dmi_adx(sub, 14)
            atr = calc_atr(sub, 14)

            # 前一根的 DMI
            sub_prev = candles_15m[:i]
            dmi_dir_prev, _, _ = calc_dmi_adx(sub_prev, 14)

            # StochRSI
            k_val, d_val = calc_stoch_rsi(closes[:i + 1])
            k_prev, d_prev = calc_stoch_rsi(closes[:i])

            # Pivot支撑
            _, pivot_lows = find_pivots(sub, 5)
            near_support = False
            if pivot_lows:
                last_support = pivot_lows[-1]
                near_support = abs(closes[i] - last_support) / closes[i] < 0.01

            signal = None
            trigger = ""

            # 触发1: DMI刚翻多
            if dmi_dir == "多" and dmi_dir_prev != "多":
                signal = self._make_signal(candles_15m[i], atr, dmi_dir, adx,
                                           k_val, trends, near_support, "dmi_flip")
                trigger = "dmi_flip"

            # 触发2: StochRSI 从超卖反弹（K<20 且刚上穿D）
            elif (k_val > d_val and k_prev <= d_prev and k_val < 30 and
                  dmi_dir == "多"):
                signal = self._make_signal(candles_15m[i], atr, dmi_dir, adx,
                                           k_val, trends, near_support, "srsi_bounce")
                trigger = "srsi_bounce"

            # 触发3: 价格接近支撑位 + 趋势向上
            elif near_support and dmi_dir == "多" and k_val < 40:
                signal = self._make_signal(candles_15m[i], atr, dmi_dir, adx,
                                           k_val, trends, near_support, "support_touch")
                trigger = "support_touch"

            if signal:
                signals.append(signal)

        return signals

    def _make_signal(self, candle, atr, dmi_dir, adx, k_val,
                     trends, near_support, trigger) -> EntrySignal:
        return EntrySignal(
            ts=candle["ts"],
            price=candle["c"],
            atr=atr if atr else candle["c"] * 0.005,
            dmi_15m=dmi_dir,
            adx_15m=adx if adx else 0,
            srsi_k=k_val if k_val else 50,
            trend_1h=trends.get("1H", {}).get("dmi_dir", "平"),
            trend_4h=trends.get("4H", {}).get("dmi_dir", "平"),
            trend_1d=trends.get("1D", {}).get("dmi_dir", "平"),
            near_support=near_support,
            trigger=trigger,
        )

    def forward_analyze(self, signal: EntrySignal,
                        candles_15m: List[Dict]) -> ForwardResult:
        """
        对某个入场信号做前瞻分析
        跟踪入场后 N 根 15m K线，看是否被止损、最大盈利等
        """
        # 找到入场K线索引
        entry_idx = None
        for i, c in enumerate(candles_15m):
            if c["ts"] == signal.ts:
                entry_idx = i
                break

        if entry_idx is None or entry_idx >= len(candles_15m) - 1:
            return ForwardResult(signal=signal, stopped=True, stop_hit_bar=0)

        entry_price = signal.price
        sl_price = entry_price * (1 - self.sl_pct)

        result = ForwardResult(signal=signal)
        result.stopped = False

        end_idx = min(entry_idx + self.forward_bars + 1, len(candles_15m))

        for i in range(entry_idx + 1, end_idx):
            bar = candles_15m[i]
            bar_idx = i - entry_idx
            low = bar["l"]
            high = bar["h"]
            close = bar["c"]

            # 检查止损
            if low <= sl_price:
                result.stopped = True
                result.stop_hit_bar = bar_idx
                result.exit_price = sl_price
                result.max_loss_pct = -self.sl_pct * 100
                return result

            # 追踪最大浮盈
            profit_pct = (high - entry_price) / entry_price * 100
            if profit_pct > result.max_profit_pct:
                result.max_profit_pct = profit_pct
                result.max_profit_bar = bar_idx

            # 追踪最大浮亏（未止损之前）
            loss_pct = (low - entry_price) / entry_price * 100
            if loss_pct < result.max_loss_pct:
                result.max_loss_pct = loss_pct

        # 没有止损，记录最终状态
        final_bar = candles_15m[end_idx - 1]
        result.exit_price = final_bar["c"]
        result.exit_bar = end_idx - entry_idx - 1

        return result

    def run_analysis(self, sym: str, days: int = 90, cache_dir: str = "cache",
                     direction: bool = True):
        """跑完整分析流程
        direction: True=做多, False=做空
        """
        dir_label = "做多" if direction else "做空"
        print(f"\n{'='*60}")
        print(f"🔍 {sym} 入场精度分析 (止损={self.sl_pct*100:.1f}%, {dir_label})")
        print(f"{'='*60}")

        # 1. 拉取所有TF数据
        print("  [1/3] 拉取数据...")
        candles_15m = fetch_historical(sym, "15m", days, cache_dir)
        candles_1h = fetch_historical(sym, "1H", days, cache_dir)
        candles_4h = fetch_historical(sym, "4H", days, cache_dir)
        candles_1d = fetch_historical(sym, "1D", days, cache_dir)

        higher_trends = {"1H": candles_1h, "4H": candles_4h, "1D": candles_1d}

        # 2. 扫描入场信号
        print("  [2/3] 扫描入场信号...")
        require_bull = direction
        signals = self.find_entries_15m(candles_15m, higher_trends, require_bull=require_bull)
        print(f"    发现 {len(signals)} 个{dir_label}信号")

        if not signals:
            print("    ⚠️ 无信号，检查数据是否足够")
            return None

        # 按触发类型分组
        by_trigger = {"dmi_flip": [], "srsi_bounce": [], "support_touch": []}
        for s in signals:
            if s.trigger in by_trigger:
                by_trigger[s.trigger].append(s)

        for t, lst in by_trigger.items():
            print(f"      {t}: {len(lst)} 个")

        # 3. 前瞻分析
        print(f"  [3/3] 前瞻分析 (跟踪{self.forward_bars}根15m K线)...")
        results = [self.forward_analyze(s, candles_15m) for s in signals]

        # 4. 汇总统计
        return self._summarize(sym, results, by_trigger)

    def _summarize(self, sym: str, results: List[ForwardResult],
                   by_trigger: Dict[str, List]) -> Dict:
        """汇总分析结果"""
        total = len(results)
        if total == 0:
            return None

        stopped = [r for r in results if r.stopped]
        survived = [r for r in results if not r.stopped]

        stop_rate = len(stopped) / total * 100
        survive_rate = len(survived) / total * 100

        # 存活交易的盈利统计
        avg_profit = (sum(r.max_profit_pct for r in survived) / len(survived)
                      if survived else 0)

        # 分布: profit buckets
        buckets = {"<0%": 0, "0-2%": 0, "2-5%": 0, "5-10%": 0, ">10%": 0}
        for r in survived:
            p = r.max_profit_pct
            if p < 0:
                buckets["<0%"] += 1
            elif p < 2:
                buckets["0-2%"] += 1
            elif p < 5:
                buckets["2-5%"] += 1
            elif p < 10:
                buckets["5-10%"] += 1
            else:
                buckets[">10%"] += 1

        # 止损发生时间分布
        stop_bar_dist = {}
        for r in stopped:
            bar = r.stop_hit_bar
            slot = f"{bar}bar" if bar <= 24 else ">24bar"
            stop_bar_dist[slot] = stop_bar_dist.get(slot, 0) + 1

        # 按触发类型统计
        trigger_stats = {}
        for trig, sig_list in by_trigger.items():
            if not sig_list:
                continue
            trig_results = [r for r in results if r.signal.trigger == trig]
            trig_stopped = [r for r in trig_results if r.stopped]
            trig_survived = [r for r in trig_results if not r.stopped]

            trigger_stats[trig] = {
                "count": len(trig_results),
                "stop_rate": round(len(trig_stopped) / len(trig_results) * 100, 1),
                "avg_profit": round(
                    sum(r.max_profit_pct for r in trig_survived) / len(trig_survived), 2
                ) if trig_survived else 0,
            }

        summary = {
            "symbol": sym,
            "sl_pct": self.sl_pct * 100,
            "total_signals": total,
            "stopped": len(stopped),
            "survived": len(survived),
            "stop_rate": round(stop_rate, 1),
            "survive_rate": round(survive_rate, 1),
            "avg_max_profit": round(avg_profit, 2),
            "profit_buckets": buckets,
            "stop_bar_dist": stop_bar_dist,
            "trigger_stats": trigger_stats,
            "results": [self._result_to_dict(r) for r in results],
        }

        # 打印
        print(f"\n  📊 {sym} 分析结果 (止损{self.sl_pct*100:.1f}%)")
        print(f"  {'─' * 40}")
        print(f"  总信号: {total}  止损出局: {len(stopped)}({stop_rate:.1f}%)  "
              f"存活: {len(survived)}({survive_rate:.1f}%)")
        print(f"  存活交易平均最大浮盈: {avg_profit:.2f}%")
        print(f"\n  盈利分布:")
        for label in ["<0%", "0-2%", "2-5%", "5-10%", ">10%"]:
            cnt = buckets[label]
            bar = "█" * max(1, cnt)
            print(f"    {label:<6} {cnt:>3}  {bar}")
        print(f"\n  止损时间分布:")
        for slot in sorted(stop_bar_dist.keys(), key=lambda x: int(x.replace("bar", "").replace(">", ""))):
            print(f"    {slot:<8} {stop_bar_dist[slot]}次")

        if trigger_stats:
            print(f"\n  按触发类型:")
            for trig, stats in trigger_stats.items():
                print(f"    {trig:<15} {stats['count']:>3}次  "
                      f"止损率{stats['stop_rate']:>5.1f}%  "
                      f"均盈{stats['avg_profit']:>6.2f}%")

        return summary

    def _result_to_dict(self, r: ForwardResult) -> Dict:
        return {
            "ts": r.signal.ts,
            "price": r.signal.price,
            "trigger": r.signal.trigger,
            "trend_1h": r.signal.trend_1h,
            "trend_4h": r.signal.trend_4h,
            "trend_1d": r.signal.trend_1d,
            "srs_k": r.signal.srsi_k,
            "stopped": r.stopped,
            "stop_bar": r.stop_hit_bar,
            "max_profit": round(r.max_profit_pct, 2),
            "max_loss": round(r.max_loss_pct, 2),
        }


def main():
    symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
    sl_percentages = [0.005, 0.01, 0.015, 0.02]  # 0.5%, 1%, 1.5%, 2%
    directions = [("LONG", True), ("SHORT", False)]

    all_summaries = []

    for sl in sl_percentages:
        for dir_label, is_bull in directions:
            print(f"\n{'#'*60}")
            print(f"# 止损: {sl*100:.1f}% | 方向: {dir_label}")
            print(f"{'#'*60}")

            analyzer = EntryAnalyzer(sl_pct=sl, forward_bars=96)

            for sym in symbols:
                summary = analyzer.run_analysis(sym, days=90, direction=is_bull)
                if summary:
                    summary["direction"] = dir_label
                    all_summaries.append(summary)

    # 保存结果
    os.makedirs("results", exist_ok=True)
    path = "results/entry_analysis.json"
    with open(path, "w") as f:
        json.dump(all_summaries, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ 结果已保存: {path} ({len(all_summaries)} 条)")
    print(f"   档位: {[f'{p*100:.1f}%' for p in sl_percentages]}")
    print(f"   方向: LONG + SHORT")

    # 生成HTML报告
    _generate_html_report(all_summaries)


def _generate_html_report(summaries: List[Dict]):
    """生成入场精度分析 HTML 报告"""
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>入场精度分析报告</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background:#0f172a; color:#e2e8f0; padding:24px; }
h1 { font-size:24px; margin-bottom:8px; }
.card { background:#1e293b; border-radius:12px; padding:20px; margin-bottom:20px; }
.card h2 { color:#38bdf8; margin-bottom:12px; font-size:18px; }
table { width:100%; border-collapse:collapse; font-size:14px; }
th, td { padding:8px 12px; text-align:center; border-bottom:1px solid #334155; }
th { background:#0f172a; color:#94a3b8; }
tr:hover { background:#334155; }
.good { color:#22c55e; }
.bad { color:#ef4444; }
.warn { color:#f59e0b; }
.bar { display:inline-block; height:14px; margin-right:4px;
       background:#38bdf8; border-radius:2px; min-width:2px; }
</style>
</head>
<body>
<h1>📊 入场精度分析</h1>
<p style="color:#94a3b8;margin-bottom:24px;">
    15m 精确入场 | 高位周期趋势确认 | 止损测试
</p>
"""

    for s in summaries:
        sl = s["sl_pct"]
        sr = s["survive_rate"]
        sr_color = "good" if sr >= 70 else ("warn" if sr >= 50 else "bad")

        html += f"""<div class="card">
<h2>{s['symbol']} — 止损 {sl:.0f}%</h2>
<p>
  信号数: <strong>{s['total_signals']}</strong> |
  止损出局: <strong class="bad">{s['stopped']}</strong> ({s['stop_rate']:.1f}%) |
  存活率: <strong class="{sr_color}">{s['survive_rate']:.1f}%</strong> |
  存活的平均最大浮盈: <strong class="good">{s['avg_max_profit']:.2f}%</strong>
</p>

<h3>盈利分布（存活交易）</h3>
<table>
<tr><th>区间</th><th>数量</th><th>占比</th><th>分布</th></tr>"""

        total_survived = s["survived"]
        for label in ["<0%", "0-2%", "2-5%", "5-10%", ">10%"]:
            cnt = s["profit_buckets"].get(label, 0)
            pct = round(cnt / total_survived * 100, 1) if total_survived > 0 else 0
            bar_w = max(2, int(pct * 2))
            html += f"""<tr>
<td>{label}</td><td>{cnt}</td><td>{pct}%</td>
<td><span class="bar" style="width:{bar_w}px"></span></td>
</tr>"""

        html += """</table>
</div>"""

        if s.get("trigger_stats"):
            html += """<div class="card">
<h3>按触发类型</h3>
<table>
<tr><th>触发类型</th><th>信号数</th><th>止损率</th><th>均盈</th></tr>"""
            for trig, stats in s["trigger_stats"].items():
                html += f"""<tr>
<td>{trig}</td><td>{stats['count']}</td>
<td>{stats['stop_rate']}%</td>
<td class="good">{stats['avg_profit']}%</td>
</tr>"""
            html += "</table></div>"

    html += "</body></html>"

    path = "results/entry_analysis.html"
    with open(path, "w") as f:
        f.write(html)
    print(f"✅ 报告已生成: {path}")


if __name__ == "__main__":
    main()
