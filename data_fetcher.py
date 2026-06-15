"""
OKX 历史K线数据获取
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import requests

OKX_BASE = "https://www.okx.com"


def fetch_ohlcv(symbol: str, bar: str, limit: int = 300,
                after: Optional[str] = None) -> Optional[List[Dict]]:
    """拉取单页K线数据"""
    url = f"{OKX_BASE}/api/v5/market/candles"
    params = {"instId": symbol, "bar": bar, "limit": limit}
    if after:
        params["after"] = after
    try:
        resp = requests.get(url, params=params, timeout=20)
        d = resp.json()
        if d.get("code") == "0":
            candles = []
            for c in d["data"]:
                ts = int(c[0])
                candles.append({
                    "ts": ts,
                    "o": float(c[1]), "h": float(c[2]),
                    "l": float(c[3]), "c": float(c[4]),
                    "vol": float(c[5])
                })
            candles.sort(key=lambda x: x["ts"])
            return candles
        return None
    except Exception as e:
        print(f"  ⚠️ 获取失败 {symbol} {bar}: {e}")
        return None


def fetch_historical(symbol: str, bar: str, days: int = 90,
                     cache_dir: str = "cache") -> List[Dict]:
    """拉取完整历史数据并缓存"""
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{symbol.replace('/', '_')}_{bar}.json")

    # 检查缓存
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            cached = json.load(f)
        if cached:
            newest = max(c["ts"] for c in cached)
            now_ms = int(datetime.now().timestamp() * 1000)
            if now_ms - newest < 24 * 3600 * 1000:
                return cached

    print(f"  ⬇️ {symbol} {bar}: 拉取中...")
    all_candles = []
    after = None
    pages = 0

    while pages < 10:
        candles = fetch_ohlcv(symbol, bar, limit=300, after=after)
        if not candles:
            break
        all_candles.extend(candles)
        pages += 1
        if len(candles) < 300:
            break
        after = str(candles[0]["ts"])
        time.sleep(0.3)

    # 去重排序
    seen = set()
    unique = []
    for c in sorted(all_candles, key=lambda x: x["ts"]):
        if c["ts"] not in seen:
            seen.add(c["ts"])
            unique.append(c)

    # 缓存
    with open(cache_file, 'w') as f:
        json.dump(unique, f)

    # 只保留需要的天数
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=days + 10)).timestamp() * 1000)
    unique = [c for c in unique if c["ts"] >= cutoff]

    print(f"  ✅ {symbol} {bar}: {len(unique)}根K线")
    return unique


def candles_before(data: List[Dict], ts: int) -> List[Dict]:
    """返回 ts 之前的K线（含等于）"""
    return [c for c in data if c["ts"] <= ts]


def get_close_at(data: List[Dict], ts: int) -> Optional[float]:
    """获取指定时间的收盘价"""
    for c in reversed(data):
        if c["ts"] <= ts:
            return c["c"]
    return None


TF_SECONDS = {
    "15m": 15 * 60 * 1000,
    "1H": 60 * 60 * 1000,
    "4H": 4 * 60 * 60 * 1000,
    "1D": 24 * 60 * 60 * 1000,
}

TF_OKX_BAR = {
    "15m": "15m",
    "1H": "1H",
    "4H": "4H",
    "1D": "1D",
}
