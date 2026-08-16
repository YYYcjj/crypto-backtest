#!/usr/bin/env python3
"""从 OKX 拉取 15m K线，为所有月份的已平仓交易生成真实走势数据 paths_data_XX.json"""
import json, os, sys, time

_CUR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _CUR)
sys.path.insert(0, os.path.join(_CUR, 'crypto-backtest'))

from data_fetcher import fetch_historical
from generate_all_paths import process_month

BASE = _CUR
RESULTS = os.path.join(BASE, 'crypto-backtest', 'results')
DOCS = os.path.join(BASE, 'docs')
CACHE_DIR = os.path.join(BASE, 'crypto-backtest', 'cache')

DAYS = 90  # 拉取最近 90 天 15m K线，覆盖近 2-3 个月


def main():
    journal_path = os.path.join(RESULTS, 'journal_trades.json')
    if not os.path.exists(journal_path):
        print('journal_trades.json 不存在，退出')
        return

    with open(journal_path) as f:
        trades = json.load(f)

    # 1. 分月写出 journal_trades_{month}.json（供 generate_all_paths 使用）
    months = {}
    for t in trades:
        m = t['entry_time'][5:7]
        months.setdefault(m, []).append(t)

    for m, mt in months.items():
        p = os.path.join(RESULTS, f'journal_trades_{m}.json')
        with open(p, 'w') as f:
            json.dump(mt, f, ensure_ascii=False, indent=2)
    print(f'分月写出: {sorted(months.keys())}')

    # 2. 收集所有涉及币种，拉取 15m K线
    coins = sorted({t['coin'] for t in trades})
    print(f'涉及币种: {len(coins)} 个')
    for coin in coins:
        sym = f'{coin}-SWAP'
        try:
            fetch_historical(sym, '15m', DAYS, cache_dir=CACHE_DIR)
        except Exception as e:
            print(f'  ⚠️ {coin} 拉取失败: {e}')
        time.sleep(0.2)

    # 3. 为每个有交易的月份生成 paths_data
    os.makedirs(DOCS, exist_ok=True)
    for m in sorted(months.keys()):
        try:
            paths = process_month(m)
        except Exception as e:
            print(f'  ⚠️ {m}月 paths 生成失败: {e}')
            continue
        if paths is None:
            continue
        src = os.path.join(RESULTS, f'paths_data_{m}.json')
        dst = os.path.join(DOCS, f'paths_data_{m}.json')
        if os.path.exists(src):
            with open(src) as f:
                content = f.read()
            with open(dst, 'w') as f:
                f.write(content)
            print(f'  docs/paths_data_{m}.json: {len(paths)} 条')

    print('build_paths 完成')


if __name__ == '__main__':
    main()
