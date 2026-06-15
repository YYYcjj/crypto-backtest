"""
主入口 — 运行多品种多周期回测
"""
import time
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BacktestConfig
from data_fetcher import fetch_historical, TF_OKX_BAR
from backtest_engine import BacktestEngine
from report import generate_html_report


def main():
    config = BacktestConfig()

    print("=" * 60)
    print("📊 OKX 策略回测引擎 v4")
    print(f"   品种: {', '.join(config.symbols)}")
    print(f"   周期: {', '.join(config.timeframes)}")
    print(f"   主周期: {config.primary_tf}")
    print(f"   回测天数: {config.backtest_days}天")
    print(f"   初始资金: ¥{config.initial_capital:,.0f}")
    print("=" * 60)

    # ── 1. 拉取数据 ──
    print("\n【1/3】拉取历史数据...")
    all_data = {}  # {symbol: {"15m": [...], "1H": [...], ...}}

    for sym in config.symbols:
        print(f"\n  ── {sym} ──")
        tf_data = {}
        for tf in config.timeframes:
            bar = TF_OKX_BAR.get(tf, tf)
            candles = fetch_historical(sym, bar, config.backtest_days, config.cache_dir)
            tf_data[tf] = candles
            time.sleep(0.2)
        all_data[sym] = tf_data

    # ── 2. 回测 ──
    print("\n【2/3】执行回测...")
    engine = BacktestEngine(config)
    all_results = []

    for sym in config.symbols:
        print(f"\n{'=' * 50}")
        result = engine.run(all_data[sym], sym)
        if result:
            all_results.append(result)

    # ── 3. 生成报告 ──
    print("\n【3/3】生成报告...")
    if all_results:
        report_path = generate_html_report(all_results, config, config.output_dir)

        # 打印汇总
        print(f"\n{'=' * 60}")
        print("📊 回测汇总")
        print(f"{'=' * 60}")
        total_trades = sum(r["total_trades"] for r in all_results)
        total_pnl = sum(r["total_pnl"] for r in all_results)
        total_win = sum(r["win_trades"] for r in all_results)
        wr = round(total_win / total_trades * 100, 1) if total_trades > 0 else 0

        print(f"  总交易: {total_trades} | 胜率: {wr}% | 总盈亏: ¥{total_pnl:,.2f}")
        print(f"  收益率: {round(total_pnl / config.initial_capital * 100, 2)}%")

        for r in all_results:
            if r["total_trades"] > 0:
                print(f"  {r['symbol']:<12} {r['total_trades']:>3}笔  "
                      f"胜率{r['win_rate']:>5.1f}%  "
                      f"盈亏¥{r['total_pnl']:>8,.2f}  "
                      f"回撤{r['max_drawdown']:>5.1f}%")
    else:
        print("\n❌ 没有产生任何交易信号")


if __name__ == "__main__":
    main()
