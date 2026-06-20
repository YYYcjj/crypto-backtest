"""
交易记录自动化 — 从 OKX API 拉取已平仓订单，自动生成 Excel 日记
用法: python update_trading_journal.py [月份]
      不带参数：当前月
      带参数：python update_trading_journal.py 6  (6月)
"""
import json, sys, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import requests, hmac, base64, hashlib

# ── 配置 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "results")
DATA_FILE = os.path.join(OUTPUT_DIR, "journal_trades.json")
EXCEL_FILE = os.path.join(OUTPUT_DIR, "交易记录_{month}.xlsx")
MCP_CONFIG = os.path.expanduser("~/.workbuddy/mcp.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_month_range(year, month):
    """返回指定月的开始和结束时间戳（毫秒）"""
    start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)
    if month == 12:
        end = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000) - 1
    else:
        end = int(datetime(year, month + 1, 1, tzinfo=timezone.utc).timestamp() * 1000) - 1
    return start, end


def get_okx_credentials():
    """获取 OKX API 凭证：优先环境变量，fallback MCP 配置"""
    # GitHub Actions 环境变量
    if os.environ.get("OKX_API_KEY"):
        return {
            "OKX_API_KEY": os.environ["OKX_API_KEY"],
            "OKX_API_SECRET": os.environ["OKX_API_SECRET"],
            "OKX_API_PASSPHRASE": os.environ["OKX_API_PASSPHRASE"],
        }
    # 本地 MCP 配置
    if os.path.exists(MCP_CONFIG):
        with open(MCP_CONFIG) as f:
            return json.load(f)["mcpServers"]["okx-mcp"]["env"]
    raise RuntimeError("未找到 OKX API 凭证。请设置环境变量或配置 MCP。")


def okx_get(path):
    """调用 OKX API v5"""
    env = get_okx_credentials()
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    sign = base64.b64encode(
        hmac.new(env["OKX_API_SECRET"].encode(), (ts + "GET" + path).encode(), hashlib.sha256).digest()
    ).decode()
    return requests.get("https://www.okx.com" + path, headers={
        "OK-ACCESS-KEY": env["OKX_API_KEY"],
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": env["OKX_API_PASSPHRASE"],
    }, timeout=30).json()


def fetch_trades(start_ts, end_ts):
    """从 OKX 拉取已平仓订单并重建交易"""
    path = f"/api/v5/trade/orders-history?instType=SWAP&state=filled&begin={start_ts}&end={end_ts}&limit=100"
    orders = sorted(okx_get(path).get("data", []), key=lambda x: int(x["cTime"]))

    trades = []
    pending = defaultdict(list)

    for o in orders:
        inst = o["instId"]
        pnl = float(o["pnl"])
        side = o["side"]
        sz = float(o["accFillSz"])
        px = float(o["avgPx"])
        ts = int(o["cTime"])

        if pnl != 0:
            ep_sum, ec, ots = 0.0, 0.0, []
            rem = sz
            while rem > 0 and pending[inst]:
                oo = pending[inst].pop(0)
                use = min(rem, oo["sz"])
                ep_sum += oo["px"] * use
                ec += use
                ots.append(oo["ts"])
                rem -= use
                if oo["sz"] > use:
                    pending[inst].insert(0, {"sz": oo["sz"] - use, "px": oo["px"], "ts": oo["ts"]})

            if ec > 0:
                ep = ep_sum / ec
                et = datetime.fromtimestamp(min(ots) / 1000, tz=timezone.utc)
                xt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                coin = inst.replace("-SWAP", "")
                direction = "做多" if side == "sell" else "做空"
                px_chg = (px / ep - 1) if direction == "做多" else (ep / px - 1)

                trades.append({
                    "coin": coin,
                    "direction": direction,
                    "entry_price": round(ep, 6),
                    "exit_price": round(px, 6),
                    "pnl_usdt": round(pnl, 2),
                    "pnl_pct": round(abs(px_chg) * 200, 1),  # ×2x ×100
                    "entry_time": et.strftime("%Y-%m-%d %H:%M"),
                    "exit_time": xt.strftime("%Y-%m-%d %H:%M"),
                    "entry_ts": int(et.timestamp() * 1000),
                })
        else:
            pending[inst].append({"sz": sz, "px": px, "ts": ts})

    trades.sort(key=lambda x: x["entry_ts"])
    return trades


def enrich_with_indicators(trades):
    """为每笔交易补充入场时的 1H/4H/1D DMI方向 + SRSI"""
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from data_fetcher import fetch_historical
        from indicators import calc_dmi_adx, calc_stoch_rsi
    except ImportError:
        print("⚠️ 无法导入指标模块，跳过指标计算")
        return trades

    cache = {}

    def get_candles(sym, tf, days):
        key = (sym + "-SWAP", tf)
        if key not in cache:
            c = fetch_historical(sym + "-SWAP", tf, days)
            if c:
                cache[key] = c
        return cache.get(key, [])

    def calc(candles, idx):
        if idx < 20:
            return "?", "?"
        w = candles[max(0, idx - 100): idx + 1]
        closes = [c["c"] for c in w]
        dmi, _, _ = calc_dmi_adx(w, 14)
        k, _ = calc_stoch_rsi(closes, 10, 10, 3, 3)
        return dmi, round(k, 1)

    for t in trades:
        ets = t["entry_ts"]
        for tf_name, bar, days in [("1H", "1H", 30), ("4H", "4H", 60), ("1D", "1D", 120)]:
            c = get_candles(t["coin"], bar, days)
            if not c:
                t["trend_" + tf_name.lower()] = "?"
                t["srsi_" + tf_name.lower()] = "?"
                continue
            idx = min(range(len(c)), key=lambda x: abs(int(c[x]["ts"]) - ets))
            dmi, srsi = calc(c, idx)
            t["trend_" + tf_name.lower()] = dmi
            t["srsi_" + tf_name.lower()] = srsi

    return trades


def load_existing(path):
    """加载已有交易记录"""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def merge_trades(existing, new_trades):
    """合并去重（按 entry_time + coin + entry_price 判断）"""
    existing_keys = {(t["entry_time"], t["coin"], t["entry_price"]) for t in existing}
    added = []
    for t in new_trades:
        key = (t["entry_time"], t["coin"], t["entry_price"])
        if key not in existing_keys:
            existing.append(t)
            existing_keys.add(key)
            added.append(t)
    existing.sort(key=lambda x: x["entry_ts"])
    return existing, added


def generate_excel(trades, output_path, month_label):
    """生成 Excel"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{month_label}月交易记录"

    # 表头
    ws.append(["交易日期", "Coin", "入场判断", "", "", "", "", "", "多/空",
               "入场截图", "更多-1", "更多-2", "判断", "离场截图", "盈亏比", "交易得失分析", "整体截图", "", ""])
    ws.append(["", "", "趋势方向", "", "", "RSI高低", "", "", "",
               "", "", "", "", "", "", "", "", "", ""])
    ws.append(["", "", "1H", "4H", "1D", "1H", "4H", "1D", "",
               "", "", "", "", "", "", "", "", "", ""])

    # 样式
    hdr_fill = PatternFill("solid", fgColor="1a2436")
    green_fill = PatternFill("solid", fgColor="142b14")
    red_fill = PatternFill("solid", fgColor="2b1414")
    border = Border(
        left=Side("thin", "1a2436"), right=Side("thin", "1a2436"),
        top=Side("thin", "1a2436"), bottom=Side("thin", "1a2436"),
    )
    wrap = Alignment(wrap_text=True, vertical="top")

    for row in [1, 2, 3]:
        for col in range(1, 20):
            ws.cell(row, col).fill = hdr_fill
            ws.cell(row, col).font = Font(bold=True, color="64748b", size=10)
            ws.cell(row, col).alignment = Alignment(horizontal="center")

    for i, t in enumerate(trades):
        row = i + 4
        pnl = t["pnl_usdt"]

        ws.cell(row, 1, t["entry_time"][:16]).font = Font(size=10)
        ws.cell(row, 2, t["coin"]).font = Font(bold=True, size=11)

        for j, k in enumerate(["trend_1h", "trend_4h", "trend_1d"]):
            v = t.get(k, "?")
            ws.cell(row, 3 + j, v).font = Font(
                color="2dd47c" if v == "多" else ("f5475d" if v == "空" else "64748b"), size=10
            )

        for j, k in enumerate(["srsi_1h", "srsi_4h", "srsi_1d"]):
            v = t.get(k, "?")
            if isinstance(v, (int, float)):
                ws.cell(row, 6 + j, v).font = Font(
                    color="f5475d" if v > 80 else ("2dd47c" if v < 20 else "f5a623"), size=10
                )
            else:
                ws.cell(row, 6 + j, v).font = Font(color="64748b", size=10)

        ws.cell(row, 9, t["direction"]).font = Font(
            color="2dd47c" if "多" in t["direction"] else "f5475d", bold=True, size=10
        )

        pct = t.get("pnl_pct", 0)
        ws.cell(row, 16, f"{pct:+.1f}%").font = Font(
            color="2dd47c" if pnl > 0 else "f5475d", bold=True, size=10
        )

        if pnl > 10:
            note = "✅ 大盈利"
        elif pnl > 3:
            note = "✅ 盈利"
        elif pnl > 0:
            note = "✅ 小盈"
        elif pnl > -4:
            note = "⚠️ 小止损"
        else:
            note = "❌ 止损"
        ws.cell(row, 17, note).font = Font(size=10)

        fill = green_fill if pnl > 0 else red_fill
        for col in range(1, 20):
            ws.cell(row, col).fill = fill
            ws.cell(row, col).border = border
            ws.cell(row, col).alignment = wrap

    for col, w in {1: 16, 2: 10, 3: 6, 4: 6, 5: 6, 6: 8, 7: 8, 8: 8, 9: 8, 16: 12, 17: 16}.items():
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = w

    # 汇总行
    rr = len(trades) + 5
    total = sum(t["pnl_usdt"] for t in trades)
    wins = sum(1 for t in trades if t["pnl_usdt"] > 0)
    ws.cell(rr, 1, "汇总").font = Font(bold=True, size=12)
    ws.cell(rr, 4, f"{len(trades)}笔 | 胜{wins}/负{len(trades)-wins} | P&L:{total:+.1f}U").font = Font(bold=True, size=11)

    wb.save(output_path)
    return output_path


def main():
    now = datetime.now(timezone.utc) + timedelta(hours=8)  # CST
    month = int(sys.argv[1]) if len(sys.argv) > 1 else now.month
    year = now.year if month <= now.month else now.year

    print(f"🔄 拉取 {year}年{month}月交易记录...")
    start_ts, end_ts = get_month_range(year, month)
    new_trades = fetch_trades(start_ts, end_ts)
    print(f"   OKX返回 {len(new_trades)} 笔已平仓交易")

    # 补充指标
    new_trades = enrich_with_indicators(new_trades)

    # 合并已有
    existing = load_existing(DATA_FILE)
    merged, added = merge_trades(existing, new_trades)

    # 保存
    with open(DATA_FILE, "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    # 生成 Excel
    excel_path = EXCEL_FILE.format(month=f"{month:02d}")
    generate_excel(merged, excel_path, f"{month}")

    print(f"\n✅ 总计 {len(merged)} 笔交易")
    print(f"   本次新增 {len(added)} 笔")
    if added:
        for t in added:
            print(f"     + {t['entry_time'][:10]} {t['coin']} {t['direction']} PnL:{t['pnl_usdt']:+}U")
    print(f"   Excel: {excel_path}")

    # 返回路径
    result_file = os.path.join(OUTPUT_DIR, ".last_run.json")
    with open(result_file, "w") as f:
        json.dump({"excel": excel_path, "total": len(merged), "added": len(added)}, f)


if __name__ == "__main__":
    main()
