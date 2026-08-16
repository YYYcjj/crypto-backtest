#!/usr/bin/env python3
"""从 journal_trades.json + paths_data 重建 all_analysis.js（供分析报告等页面使用）"""
import json, os, sys

ROOT = os.getcwd()
sys.path.insert(0, ROOT)

RESULTS = os.path.join(ROOT, 'results')
DOCS = os.path.join(ROOT, 'docs')


def compute_sl_verdict(pnl_usdt, hm, pm, px):
    if pm < -1.0:
        return "合适"
    elif px > 2.0:
        return "过早"
    return "中性"


def compute_tp_verdict(pnl_usdt, pnl_pct, hm, hx, pm, px):
    if pm < -1.0 and abs(pm) >= abs(px):
        return "合适"
    elif px > 3.0:
        return f"过早(+{px:.0f}%)"
    elif hx > 0 and (hx - abs(pm or 0)) > 5.0:
        return "过早"
    elif hx > 0 and hx > (pnl_pct or 0) + 3.0:
        return "过晚"
    return "中性"


def to_dir_mae_mfe(hm, hx, pm, px, direction):
    """把原始价格高低点(相对入场价%) 转成 已方向调整的 持仓/离场 最大不利/有利偏移"""
    if direction == '做空':
        hold_mae = round(-hx, 1)
        hold_mfe = round(-hm, 1)
        post_mae = round(-px, 1)
        post_mfe = round(-pm, 1)
    else:
        hold_mae = round(hm, 1)
        hold_mfe = round(hx, 1)
        post_mae = round(pm, 1)
        post_mfe = round(px, 1)
    return hold_mae, hold_mfe, post_mae, post_mfe


def main():
    journal_path = os.path.join(RESULTS, 'journal_trades.json')
    if not os.path.exists(journal_path):
        print('journal_trades.json 不存在')
        return

    with open(journal_path) as f:
        trades = json.load(f)

    # 按月分组
    months = {}
    for t in trades:
        m = int(t['entry_time'][5:7])
        months.setdefault(m, []).append(t)

    # 加载各月 paths_data
    paths_by_month = {}
    for m in months.keys():
        p = os.path.join(DOCS, f'paths_data_{m:02d}.json')
        if os.path.exists(p):
            with open(p) as f:
                paths_by_month[m] = json.load(f)

    all_trades = []
    for m in sorted(months.keys()):
        mt = months[m]
        paths = paths_by_month.get(m, [])
        for i, t in enumerate(mt):
            et = t.get('entry_time', '')
            xt = t.get('exit_time', '')
            es = et[5:] if len(et) >= 16 else et
            xs = xt[11:16] if len(xt) >= 16 else xt
            entry_str = f"{es}→{xs}" if xs else es

            trend = f"{t.get('trend_4h','?')}/{t.get('trend_1d','?')}"
            if t.get('trend_1h'):
                trend = f"{t['trend_1h']}/{t.get('trend_4h','?')}/{t.get('trend_1d','?')}"

            # 从 paths 取 hm/hx/pm/px（原始价格高低点）
            hm = hx = pm = px = 0.0
            if i < len(paths):
                p = paths[i]
                hm = p.get('hm') or 0
                hx = p.get('hx') or 0
                pm = p.get('pm') or 0
                px = p.get('px') or 0

            hold_mae, hold_mfe, post_mae, post_mfe = to_dir_mae_mfe(hm, hx, pm, px, t['direction'])

            # 如果 paths 是 minimal（不可靠），回退到 journal 的 mae_pct/mfe_pct
            if i < len(paths) and paths[i].get('tf') == 'minimal':
                hold_mae = -(abs(t.get('mae_pct', 0))) if t.get('mae_pct', 0) else hold_mae
                hold_mfe = t.get('mfe_pct', 0) or hold_mfe

            raw = {
                'idx': i,
                'm': m,
                'coin': t['coin'],
                'direction': t['direction'],
                'pnl_pct': round(t.get('pnl_pct', 0), 1),
                'pnl_usdt': round(t.get('pnl_usdt', 0), 2),
                'entry': entry_str,
                'holdMae': hold_mae,
                'holdMfe': hold_mfe,
                'postMae': post_mae,
                'postMfe': post_mfe,
                'trend': trend,
                'srsi4h': t.get('srsi_4h') if isinstance(t.get('srsi_4h'), (int, float)) else 0,
            }
            if t.get('pnl_usdt', 0) < 0:
                raw['slV'] = compute_sl_verdict(t.get('pnl_usdt', 0), hold_mae, post_mae, post_mfe)
            elif t.get('pnl_usdt', 0) > 0:
                raw['tpV'] = compute_tp_verdict(t.get('pnl_usdt', 0), t.get('pnl_pct', 0),
                                                hold_mae, hold_mfe, post_mae, post_mfe)
            all_trades.append(raw)

    total = len(all_trades)
    print(f'重建分析数据: {total} 笔')

    # EA
    ea = {'total': total, 'trendAlign': [], 'srsi_1h': [], 'srsi_4h': [], 'srsi_1d': []}

    for a in range(4):
        trades_a = []
        for t in all_trades:
            parts = t.get('trend', '?/?').split('/')
            if len(parts) < 2 or parts[0] == '?' or parts[1] == '?':
                continue
            align = 0
            if t['direction'] == '做多':
                if len(parts) > 0 and parts[0] == '多': align += 1
                if len(parts) > 1 and parts[1] == '多': align += 1
            else:
                if len(parts) > 0 and parts[0] == '空': align += 1
                if len(parts) > 1 and parts[1] == '空': align += 1
            if align == a:
                trades_a.append(t)
        w = sum(1 for x in trades_a if x['pnl_usdt'] > 0)
        avg = sum(x['pnl_usdt'] for x in trades_a) / len(trades_a) if trades_a else 0
        ea['trendAlign'].append({
            'a': a, 't': len(trades_a), 'w': w,
            'wr': round(w / len(trades_a) * 100) if trades_a else 0,
            'avg': round(avg, 1)
        })

    for field in ['srsi4h', 'srsi_1d']:
        zones = [(0, 19), (20, 39), (40, 59), (60, 79), (80, 100)]
        zd = []
        for lo, hi in zones:
            trades_z = [t for t in all_trades if t.get(field, 0) and lo <= t[field] <= hi]
            w = sum(1 for x in trades_z if x['pnl_usdt'] > 0)
            avg = sum(x['pnl_usdt'] for x in trades_z) / len(trades_z) if trades_z else 0
            pnls = [x['pnl_usdt'] for x in trades_z]
            zd.append({
                'zone': f'{lo}-{hi}',
                't': len(trades_z), 'w': w,
                'wr': round(w / len(trades_z) * 100) if trades_z else 0,
                'avg': round(avg, 1),
                'maxPn': round(max(pnls), 1) if pnls else 0,
                'minPn': round(min(pnls), 1) if pnls else 0,
            })
        key = 'srsi_4h' if field == 'srsi4h' else 'srsi_1d'
        ea[key] = zd

    ea['srsi_1h'] = [{'zone': f'{lo}-{hi}', 't': 0, 'w': 0, 'wr': 0, 'avg': 0,
                       'maxPn': 0, 'minPn': 0} for lo, hi in [(0, 19), (20, 39), (40, 59), (60, 79), (80, 100)]]

    raw_json = json.dumps(all_trades, ensure_ascii=False)
    ea_json = json.dumps(ea, ensure_ascii=False)
    js = f"""// 全量分析数据 ({total} trades)
var ALL_TRADES = {total};
var RAW = {raw_json};
var EA = {ea_json};
"""
    for d in [DOCS, RESULTS]:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'all_analysis.js'), 'w') as f:
            f.write(js)
    print(f'✓ all_analysis.js 已重建 ({total} 笔)')


if __name__ == '__main__':
    main()
