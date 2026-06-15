"""
OKX 数据获取 — 公开API拉取历史K线，本地JSON缓存
"""
import json
import os
import time
import requests
from typing import List, Dict, Optional

# OKX bar → 秒数映射
TF_SECONDS = {
    "15m": 900,
    "1H": 3600,
    "4H": 14400,
    "1D": 86400,
}

# 时间框架 → OKX bar 参数
TF_OKX_BAR = {
    "15m": "15m",
    "1H": "1H",
    "4H": "4H",
    "1D": "1D",
}

OKX_FETCH_LIMIT = 100


def _cache_path(symbol: str, bar: str, cache_dir: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    safe = symbol.replace("-", "_").replace("/", "_")
    return os.path.join(cache_dir, f"{safe}_{bar}.json")


def _load_cache(filepath: str) -> List[Dict]:
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return []


def _save_cache(filepath: str, candles: List[Dict]):
    with open(filepath, "w") as f:
        json.dump(candles, f, default=str)


def _fetch_page(symbol: str, bar: str, after_ts: int = None, before_ts: int = None) -> List[Dict]:
    """
    从 OKX API 拉取一页K线（最多100根）
    返回: [{"ts": int_ms, "o": float, "h": float, "l": float, "c": float, "v": float}, ...]
    """
    url = "https://www.okx.com/api/v5/market/history-candles"
    params = {"instId": symbol, "bar": bar, "limit": OKX_FETCH_LIMIT}
    if after_ts:
        params["after"] = str(after_ts)
    if before_ts:
        params["before"] = str(before_ts)

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
    except Exception:
        return []

    if data.get("code") != "0":
        return []

    raw = data.get("data", [])
    candles = []
    for row in raw:
        candles.append({
            "ts": int(row[0]),
            "o": float(row[1]),
            "h": float(row[2]),
            "l": float(row[3]),
            "c": float(row[4]),
            "v": float(row[5]),
        })

    candles.sort(key=lambda x: x["ts"])
    return candles


def fetch_historical(symbol: str, bar: str, days: int, cache_dir: str = "cache") -> List[Dict]:
    """获取历史K线（含本地缓存）"""
    path = _cache_path(symbol, bar, cache_dir)
    cached = _load_cache(path)

    now_ms = int(time.time() * 1000)
    target_start_ms = now_ms - days * 86400 * 1000

    # 检查缓存
    if cached:
        earliest = cached[0]["ts"]
        latest = cached[-1]["ts"]
        if earliest <= target_start_ms and latest >= now_ms - 3600 * 1000:
            return [c for c in cached if c["ts"] >= target_start_ms]

    # 全量拉取
    print(f"    {symbol} {bar}: 拉取 ~{days}天数据...")
    all_candles = []
    seen = set()

    after_ms = None
    while True:
        page = _fetch_page(symbol, bar, after_ts=after_ms)
        if not page:
            break
        for c in page:
            if c["ts"] not in seen:
                seen.add(c["ts"])
                all_candles.append(c)
        earliest_ts = page[0]["ts"]
        if earliest_ts <= target_start_ms:
            break
        after_ms = earliest_ts - 1
        time.sleep(0.1)

    all_candles.sort(key=lambda x: x["ts"])
    if all_candles:
        _save_cache(path, all_candles)

    filtered = [c for c in all_candles if c["ts"] >= target_start_ms]
    print(f"    {symbol} {bar}: {len(filtered)} 根K线")
    return filtered


def get_close_at(candles: List[Dict], ts: int) -> Optional[float]:
    """获取指定时间戳的收盘价"""
    for c in reversed(candles):
        if c["ts"] <= ts:
            return c["c"]
    return None
