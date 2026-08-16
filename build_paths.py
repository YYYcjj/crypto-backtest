#!/usr/bin/env python3
"""从 OKX 拉取 15m K线，为所有月份的已平仓交易生成真实走势数据 paths_data_XX.json

在 GitHub Actions 中运行（工作目录 = 仓库根）。依赖根目录的 data_fetcher.py 和 indicators.py。
"""
import json, os, sys, time
from datetime import datetime, timezone

ROOT = os.getcwd()
sys.path.insert(0, ROOT)

from data_fetcher import fetch_historical
from indicators import calc_stoch_rsi

DAYS = 90
CACHE_DIR = os.path.join(ROOT, 'cache')


def load_cache(coin):
    safe = coin.replace('-', '_')
    for p in [os.path.join(CACHE_DIR, f'{safe}_SWAP_15m.json'),
              os.path.join(CACHE_DIR, f'{safe}_15m.json')]:
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    return None


def generate_full_path(trade, candles, entry_idx):
    PRE_BARS = 80
    start_idx = max(0, entry_idx - PRE_BARS)
    all_raw = []; all_times = []
    for j in range(start_idx, len(candles)):
        c = candles[j]; ts = int(c['ts'])
        all_raw.append(c['c'])
        all_times.append(datetime.fromtimestamp(ts/1000, tz=timezone.utc).strftime('%m-%d %H:%M'))
        if ts > trade['entry_ts'] + 5 * 24 * 3600 * 1000:
            break
    n = len(all_raw)
    if n < PRE_BARS + 10:
        return generate_minimal_path(trade)

    ep = all_raw[PRE_BARS]
    normalized = [round((p/ep-1)*100, 2) for p in all_raw]
    RS, ST, KS, DS = 20, 10, 3, 3; W = RS+ST+KS+DS
    kf = [None]*min(W, n); df = [None]*min(W, n)
    for j in range(W, n+1):
        k, d = calc_stoch_rsi(all_raw[:j], RS, ST, KS, DS)
        kf.append(round(k, 1)); df.append(round(d, 1))
    while len(kf) < n: kf.append(None); df.append(None)

    xp = trade['exit_price']; exit_idx = PRE_BARS
    for j in range(PRE_BARS, min(PRE_BARS+300, n)):
        if abs(all_raw[j]-xp)/xp < 0.005:
            exit_idx = j; break

    hb = normalized[PRE_BARS:exit_idx+1] if exit_idx >= PRE_BARS else [0]
    hm, hx = min(hb), max(hb)
    ps = exit_idx+1; pe = min(n, ps+48)
    pb = normalized[ps:pe] if ps < pe else [0]
    pm, px = min(pb), max(pb)

    return {'b': normalized, 's': kf, 'd': df, 't': all_times,
            'ei': PRE_BARS, 'ex': exit_idx, 'hm': hm, 'hx': hx,
            'pm': pm, 'px': px, 'tf': '15m'}


def generate_minimal_path(trade):
    pct_chg = trade['pnl_pct']
    steps = 20
    entry_dt = datetime.strptime(trade['entry_time'][:16], '%Y-%m-%d %H:%M')
    exit_dt = datetime.strptime(trade['exit_time'][:16], '%Y-%m-%d %H:%M')
    diff_hours = max(1, (exit_dt - entry_dt).total_seconds() / 3600)
    bars = []; times = []
    null_kd = [None] * (steps + 20)
    for i in range(steps + 20):
        progress = (i - 20) / steps
        bars.append(0.0 if progress <= 0 else round(pct_chg * progress, 1))
        if i < 20:
            pre_h = entry_dt.timestamp() - (20-i) * diff_hours * 3600 / steps
            times.append(datetime.fromtimestamp(pre_h, tz=timezone.utc).strftime('%m-%d %H:%M'))
        elif i == 20:
            times.append(entry_dt.strftime('%m-%d %H:%M'))
        else:
            post_h = entry_dt.timestamp() + (i-20) * diff_hours * 3600 / steps
            times.append(datetime.fromtimestamp(post_h, tz=timezone.utc).strftime('%m-%d %H:%M'))
    return {'b': bars, 's': null_kd, 'd': null_kd, 't': times,
            'ei': 20, 'ex': 20 + steps, 'hm': min(0, pct_chg), 'hx': max(0, pct_chg),
            'pm': 0, 'px': 0, 'tf': 'minimal'}


def process_month(trades):
    paths = []
    for t in trades:
        candles = load_cache(t['coin'])
        if candles:
            entry_ts = t['entry_ts']
            best_idx = 0; best_diff = float('inf')
            for j, c in enumerate(candles):
                diff = abs(int(c['ts']) - entry_ts)
                if diff < best_diff:
                    best_diff = diff; best_idx = j
            if best_diff < 24 * 3600 * 1000:
                paths.append(generate_full_path(t, candles, best_idx))
            else:
                paths.append(generate_minimal_path(t))
        else:
            paths.append(generate_minimal_path(t))
    return paths


def main():
    journal_path = os.path.join(ROOT, 'results', 'journal_trades.json')
    if not os.path.exists(journal_path):
        print('journal_trades.json 不存在，退出')
        return

    with open(journal_path) as f:
        trades = json.load(f)

    months = {}
    for t in trades:
        m = t['entry_time'][5:7]
        months.setdefault(m, []).append(t)
    print(f'月份: {sorted(months.keys())}')

    coins = sorted({t['coin'] for t in trades})
    print(f'涉及币种: {len(coins)} 个')
    for coin in coins:
        sym = f'{coin}-SWAP'
        try:
            fetch_historical(sym, '15m', DAYS, cache_dir=CACHE_DIR)
        except Exception as e:
            print(f'  ⚠️ {coin} 拉取失败: {e}')
        time.sleep(0.2)

    os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'results'), exist_ok=True)
    for m in sorted(months.keys()):
        paths = process_month(months[m])
        data = json.dumps(paths, ensure_ascii=False)
        with open(os.path.join(ROOT, 'docs', f'paths_data_{m}.json'), 'w') as f:
            f.write(data)
        with open(os.path.join(ROOT, 'results', f'paths_data_{m}.json'), 'w') as f:
            f.write(data)
        hits = sum(1 for p in paths if p.get('tf') == '15m')
        print(f'  {m}月: {len(paths)} 条 (真实K线 {hits} / 最小 {len(paths)-hits})')

    print('build_paths 完成')


if __name__ == '__main__':
    main()
