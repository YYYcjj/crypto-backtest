"""
交易细节分析模块 — 深入每笔交易的微观行为
核心问题：2% 止损在实际交易中提供了多少缓冲？
"""
import json
import os
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone
from collections import defaultdict

from data_fetcher import fetch_historical
from indicators import calc_dmi_adx, calc_stoch_rsi, calc_atr, find_pivots
from entry_analysis import EntryAnalyzer, EntrySignal, ForwardResult


class DetailAnalyzer:
    """交易细节深度分析器"""

    def __init__(self, sl_pct: float = 0.02):
        self.sl_pct = sl_pct
        self.analyzer = EntryAnalyzer(sl_pct=sl_pct, forward_bars=96)

    def run_symbol(self, sym: str, days: int = 90) -> Dict:
        """对单个品种做深度分析"""
        print(f"\n{'='*50}")
        print(f"🔬 {sym} 细节分析 (止损={self.sl_pct*100:.0f}%)")

        # 1. 获取数据
        print("  [1/4] 获取数据...")
        c15 = fetch_historical(sym, "15m", days)
        c1h = fetch_historical(sym, "1H", days)
        c4h = fetch_historical(sym, "4H", days)
        c1d = fetch_historical(sym, "1D", days)

        if len(c15) < 50:
            return {"symbol": sym, "error": "数据不足"}

        # 2. 找到所有入场信号（做多）
        print("  [2/4] 扫描入场信号...")
        higher = {"1H": c1h, "4H": c4h, "1D": c1d}
        signals = self.analyzer.find_entries_15m(c15, higher, require_bull=True)

        if len(signals) < 10:
            return {"symbol": sym, "error": f"信号不足 ({len(signals)}个)"}

        print(f"    发现 {len(signals)} 个信号")

        # 3. 逐笔前瞻分析
        print("  [3/4] 逐笔前瞻分析...")
        results = []
        for i, sig in enumerate(signals):
            fr = self.analyzer.forward_analyze(sig, c15)
            results.append(self._enrich_result(fr, c15))
            if (i + 1) % 200 == 0:
                print(f"    {i+1}/{len(signals)}...")

        # 4. 聚合分析
        print("  [4/4] 聚合分析...")
        return self._aggregate(sym, results, c15)

    def _enrich_result(self, fr: ForwardResult, candles: List[Dict]) -> Dict:
        """丰富单笔交易数据"""
        sig = fr.signal

        # 入场时间特征
        dt = datetime.fromtimestamp(sig.ts / 1000, tz=timezone.utc)
        hour = dt.hour
        dow = dt.weekday()  # 0=Mon, 6=Sun

        # ATR 环境
        atr_pct = sig.atr / sig.price * 100 if sig.atr and sig.price else 0

        # 信号组合
        combo_parts = [sig.trigger]
        if sig.near_support:
            combo_parts.append("near_support")
        combo = "_".join(sorted(combo_parts))

        # 高维趋势
        trends = {"1H": sig.trend_1h, "4H": sig.trend_4h, "1D": sig.trend_1d}
        trend_aligned = sum(1 for v in trends.values() if v == "多")

        # MAE (最大不利偏移，即入场后最低点)
        mae_pct = abs(fr.max_loss_pct)  # 正值

        # 盈利速度：啥时候到达 +1%、+2%、+3%
        profit_speed = self._calc_profit_speed(fr, candles)

        return {
            "ts": sig.ts,
            "price": sig.price,
            "trigger": sig.trigger,
            "combo": combo,
            "hour": hour,
            "dow": dow,
            "atr_pct": round(atr_pct, 2),
            "adx": sig.adx_15m,
            "srsi_k": sig.srsi_k,
            "trend_aligned": trend_aligned,
            "near_support": sig.near_support,
            "stopped": fr.stopped,
            "stop_bar": fr.stop_hit_bar,
            "exit_bar": fr.exit_bar,
            "exit_price": fr.exit_price,
            "mae_pct": round(mae_pct, 2),
            "mfe_pct": round(fr.max_profit_pct, 2),  # Maximum Favorable Excursion
            "profit_speed": profit_speed,
        }

    def _calc_profit_speed(self, fr: ForwardResult, candles: List[Dict]) -> Dict:
        """计算达到各盈利目标的K线数"""
        sig = fr.signal
        entry_idx = None
        for i, c in enumerate(candles):
            if c["ts"] == sig.ts:
                entry_idx = i
                break
        if entry_idx is None:
            return {}

        targets = [1.0, 2.0, 3.0, 5.0]
        speed = {}
        end = min(entry_idx + fr.exit_bar + 1, len(candles))

        for tgt in targets:
            tgt_price = sig.price * (1 + tgt / 100)
            for i in range(entry_idx + 1, end):
                if candles[i]["h"] >= tgt_price:
                    speed[f"to_{tgt}%"] = i - entry_idx
                    break
            if f"to_{tgt}%" not in speed:
                speed[f"to_{tgt}%"] = None  # 未达到

        return speed

    def _aggregate(self, sym: str, results: List[Dict], candles: List[Dict]) -> Dict:
        """聚合所有交易数据"""
        total = len(results)
        stopped = [r for r in results if r["stopped"]]
        survived = [r for r in results if not r["stopped"]]

        if total == 0:
            return {"symbol": sym, "error": "无交易数据"}

        # ── 1. MAE 分布 ──
        mae_buckets = {"<0.5%": 0, "0.5-1%": 0, "1-1.5%": 0, "1.5-2%": 0, "stopped": 0}
        for r in results:
            if r["stopped"]:
                mae_buckets["stopped"] += 1
            else:
                m = r["mae_pct"]
                if m < 0.5:
                    mae_buckets["<0.5%"] += 1
                elif m < 1.0:
                    mae_buckets["0.5-1%"] += 1
                elif m < 1.5:
                    mae_buckets["1-1.5%"] += 1
                else:
                    mae_buckets["1.5-2%"] += 1

        # ── 2. 时段分析 ──
        hour_stats = defaultdict(lambda: {"signals": 0, "stopped": 0})
        for r in results:
            h = r["hour"]
            hour_stats[h]["signals"] += 1
            if r["stopped"]:
                hour_stats[h]["stopped"] += 1

        hour_data = {}
        for h in range(24):
            s = hour_stats.get(h, {"signals": 0, "stopped": 0})
            surv = round((1 - s["stopped"] / s["signals"]) * 100, 1) if s["signals"] > 0 else 0
            hour_data[h] = {
                "signals": s["signals"],
                "survive_rate": surv,
            }

        # ── 3. 信号叠加 ──
        combo_stats = defaultdict(lambda: {"signals": 0, "stopped": 0, "total_profit": 0.0})
        for r in results:
            c = r["combo"]
            combo_stats[c]["signals"] += 1
            if r["stopped"]:
                combo_stats[c]["stopped"] += 1
            else:
                combo_stats[c]["total_profit"] += r["mfe_pct"]

        combo_data = {}
        for c, s in combo_stats.items():
            surv = round((1 - s["stopped"] / s["signals"]) * 100, 1)
            avg_profit = round(s["total_profit"] / (s["signals"] - s["stopped"]), 2) if s["signals"] > s["stopped"] else 0
            combo_data[c] = {
                "signals": s["signals"],
                "survive_rate": surv,
                "avg_profit": avg_profit,
            }

        # ── 4. ATR 环境 ──
        atr_buckets = {"低波(<1%)": [], "中波(1-2%)": [], "高波(>2%)": []}
        for r in results:
            a = r["atr_pct"]
            if a < 1.0:
                atr_buckets["低波(<1%)"].append(r)
            elif a < 2.0:
                atr_buckets["中波(1-2%)"].append(r)
            else:
                atr_buckets["高波(>2%)"].append(r)

        atr_data = {}
        for label, lst in atr_buckets.items():
            if not lst:
                atr_data[label] = {"signals": 0, "survive_rate": 0, "avg_profit": 0}
                continue
            s = len([r for r in lst if r["stopped"]])
            surv = round((1 - s / len(lst)) * 100, 1)
            surv_trades = [r for r in lst if not r["stopped"]]
            avg_p = round(sum(r["mfe_pct"] for r in surv_trades) / len(surv_trades), 2) if surv_trades else 0
            atr_data[label] = {"signals": len(lst), "survive_rate": surv, "avg_profit": avg_p}

        # ── 5. 盈利速度 ──
        speed_summary = {}
        BAR_MINUTES = 15  # 每根15m K线 = 15分钟
        for tgt in ["to_1%", "to_2%", "to_3%", "to_5%"]:
            bars = [r["profit_speed"].get(tgt) for r in survived if r["profit_speed"].get(tgt) is not None]
            if bars:
                avg_min = round(sum(bars) / len(bars) * BAR_MINUTES, 0)
                med_min = round(sorted(bars)[len(bars) // 2] * BAR_MINUTES, 0) if bars else 0
                speed_summary[tgt] = {
                    "reach_rate": round(len(bars) / len(survived) * 100, 1),
                    "avg_minutes": int(avg_min),
                    "median_minutes": int(med_min),
                    "avg_bars": round(sum(bars) / len(bars), 1),  # 保留K线数
                }
            else:
                speed_summary[tgt] = {"reach_rate": 0, "avg_minutes": 0, "median_minutes": 0, "avg_bars": 0}

        # ── 6. 趋势对齐 ──
        trend_data = {}
        for n in range(4):  # 0-3个TF对齐
            group = [r for r in results if r["trend_aligned"] == n]
            if not group:
                trend_data[f"{n}TF看多"] = {"signals": 0, "survive_rate": 0, "avg_profit": 0}
                continue
            s = len([r for r in group if r["stopped"]])
            surv = round((1 - s / len(group)) * 100, 1)
            surv_trades = [r for r in group if not r["stopped"]]
            avg_p = round(sum(r["mfe_pct"] for r in surv_trades) / len(surv_trades), 2) if surv_trades else 0
            trend_data[f"{n}TF看多"] = {"signals": len(group), "survive_rate": surv, "avg_profit": avg_p}

        return {
            "symbol": sym,
            "sl_pct": self.sl_pct * 100,
            "total_signals": total,
            "stopped_count": len(stopped),
            "survive_rate": round(len(survived) / total * 100, 1),
            "avg_mae": round(sum(r["mae_pct"] for r in survived) / len(survived), 2) if survived else 0,
            "mae_buckets": mae_buckets,
            "hour_data": hour_data,
            "combo_data": combo_data,
            "atr_data": atr_data,
            "speed_summary": speed_summary,
            "trend_data": trend_data,
            "raw_results": results,  # 保留原始数据供前端表格
        }


def main():
    symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "DOGE-USDT"]
    all_data = []

    os.makedirs("results", exist_ok=True)

    for sym in symbols:
        da = DetailAnalyzer(sl_pct=0.02)
        result = da.run_symbol(sym, days=90)
        if result and "error" not in result:
            all_data.append(result)
            print(f"  ✅ {sym}: {result['total_signals']}信号, "
                  f"MAE均{result['avg_mae']:.2f}%, "
                  f"存活{result['survive_rate']:.1f}%")

    # 保存
    path = "results/detail_analysis.json"
    with open(path, "w") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ 细节分析已保存: {path} ({len(all_data)} 品种)")

    # 生成细节报告
    _print_detail_report(all_data)


def _print_detail_report(data: List[Dict]):
    """打印关键发现"""
    for d in data:
        sym = d["symbol"]
        print(f"\n{'='*60}")
        print(f"📊 {sym} 细节报告 (2%止损)")
        print(f"{'='*60}")

        # MAE
        print(f"\n  📉 最大不利偏移 (MAE) 分布:")
        for label, cnt in d["mae_buckets"].items():
            pct = round(cnt / d["total_signals"] * 100, 1)
            bar = "█" * max(1, int(pct))
            print(f"    {label:<10} {cnt:>4} ({pct:>5.1f}%) {bar}")

        # 最佳时段
        hours = d["hour_data"]
        best_hours = sorted(
            [(h, v) for h, v in hours.items() if v["signals"] >= 5],
            key=lambda x: x[1]["survive_rate"], reverse=True
        )[:5]
        print(f"\n  🕐 最佳入场时段 (Top5):")
        for h, v in best_hours:
            print(f"    {h:02d}:00  │  信号{v['signals']:>4}  │  存活率{v['survive_rate']:>6.1f}%")

        # 波动率
        print(f"\n  📊 波动率环境:")
        for label, v in d["atr_data"].items():
            if v["signals"] > 0:
                print(f"    {label:<15} 信号{v['signals']:>5} 存活{v['survive_rate']:>6.1f}% 均盈{v['avg_profit']:>6.2f}%")

        # 盈利速度
        print(f"\n  ⏱ 盈利速度:")
        for tgt, v in d["speed_summary"].items():
            if v["reach_rate"] > 0:
                def fmt_m(m): return f"{m//60}h{m%60:02d}m" if m >= 60 else f"{m}m"
                print(f"    {tgt.replace('to_','+')}: {v['reach_rate']:.0f}%达到 "
                      f"平均{fmt_m(v['avg_minutes'])} "
                      f"中位数{fmt_m(v['median_minutes'])}")

        # 信号叠加
        print(f"\n  🔗 信号叠加:")
        combos = sorted(d["combo_data"].items(), key=lambda x: x[1]["survive_rate"], reverse=True)
        for c, v in combos[:5]:
            print(f"    {c:<25} 信号{v['signals']:>4} 存活{v['survive_rate']:>6.1f}% 均盈{v['avg_profit']:>6.2f}%")


if __name__ == "__main__":
    main()
