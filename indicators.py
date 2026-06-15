"""
指标计算库 — DMI/ADX, StochRSI, SuperTrend, ATR, Pivot
严格对齐 TradingView Pine Script v6 计算逻辑
"""
import math
from typing import List, Dict, Optional, Tuple


def calc_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """RSI (Wilder's smoothing)"""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi_vals = [100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)]
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi_vals.append(100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))

    return rsi_vals[-1]


def calc_stoch_rsi(closes: List[float], rsi_period: int = 14,
                   stoch_period: int = 14, smooth_k: int = 3) -> Optional[float]:
    """StochRSI: (K+D)/2, K经SMA(3)平滑 → 匹配 TradingView ta.stoch + ta.sma"""
    if len(closes) < rsi_period + stoch_period + smooth_k:
        return None

    # 计算RSI序列
    if len(closes) < rsi_period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[:rsi_period]) / rsi_period
    avg_loss = sum(losses[:rsi_period]) / rsi_period
    rsi_values = [100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)]
    for i in range(rsi_period, len(gains)):
        avg_gain = (avg_gain * (rsi_period - 1) + gains[i]) / rsi_period
        avg_loss = (avg_loss * (rsi_period - 1) + losses[i]) / rsi_period
        rsi_values.append(100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))

    # Stoch(RSI, RSI, RSI, period)
    k_raw = []
    for i in range(stoch_period - 1, len(rsi_values)):
        window = rsi_values[i - stoch_period + 1 : i + 1]
        lo, hi = min(window), max(window)
        k_raw.append(50.0 if hi == lo else (rsi_values[i] - lo) / (hi - lo) * 100)

    # SMA(K, smooth_k)
    k_vals = []
    for i in range(smooth_k - 1, len(k_raw)):
        k_vals.append(sum(k_raw[i - smooth_k + 1 : i + 1]) / smooth_k)

    if len(k_vals) < 4:
        return k_vals[-1] if k_vals else None

    # D = SMA(K, 3)
    d = sum(k_vals[-3:]) / 3
    return (k_vals[-1] + d) / 2


def calc_atr(candles: List[Dict], period: int = 14) -> Optional[float]:
    """ATR (Wilder's smoothing)"""
    n = len(candles)
    if n < period + 1:
        return None

    tr = [0.0] * n
    for i in range(1, n):
        h, l, pc = candles[i]["h"], candles[i]["l"], candles[i - 1]["c"]
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))

    atr = sum(tr[1 : period + 1]) / period
    for i in range(period + 1, n):
        atr = (atr * (period - 1) + tr[i]) / period
    return atr


def calc_dmi_adx(candles: List[Dict], period: int = 14) -> Tuple[str, Optional[float], Optional[float]]:
    """DMI/ADX: 返回 (方向, ADX值, ATR值)"""
    n = len(candles)
    if n < period + 2:
        return "N/A", None, None

    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    closes_arr = [c["c"] for c in candles]

    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                    abs(highs[i] - closes_arr[i - 1]),
                    abs(lows[i] - closes_arr[i - 1]))
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        if up > down and up > 0:
            plus_dm[i] = up
        if down > up and down > 0:
            minus_dm[i] = down

    atr_s = sum(tr[1 : period + 1]) / period
    spdm = sum(plus_dm[1 : period + 1]) / period
    smdm = sum(minus_dm[1 : period + 1]) / period

    dx_vals = []
    for i in range(period + 1, n):
        atr_s = (atr_s * (period - 1) + tr[i]) / period
        spdm = (spdm * (period - 1) + plus_dm[i]) / period
        smdm = (smdm * (period - 1) + minus_dm[i]) / period
        pdi = spdm / atr_s * 100 if atr_s > 0 else 0
        mdi = smdm / atr_s * 100 if atr_s > 0 else 0
        s = pdi + mdi
        dx_vals.append(abs(pdi - mdi) / s * 100 if s > 0 else 0)

    if len(dx_vals) < period:
        return "多" if spdm > smdm else "空", None, atr_s

    adx = sum(dx_vals[:period]) / period
    for i in range(period, len(dx_vals)):
        adx = (adx * (period - 1) + dx_vals[i]) / period
    return ("多" if spdm > smdm else "空"), adx, atr_s


def calc_super_trend(candles: List[Dict], factor: float = 1.0,
                     period: int = 10) -> Tuple[Optional[float], int]:
    """SuperTrend: 返回 (ST值, 方向: 1多头/-1空头)
    计算逻辑严格对齐 TradingView ta.supertrend
    """
    n = len(candles)
    if n < period + 1:
        return None, 0

    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    closes = [c["c"] for c in candles]

    # ATR
    atr_vals = []
    true_ranges = []
    for i in range(1, n):
        tr_val = max(highs[i] - lows[i],
                     abs(highs[i] - closes[i - 1]),
                     abs(lows[i] - closes[i - 1]))
        true_ranges.append(tr_val)

    # Wilder's smoothed ATR
    atr = sum(true_ranges[:period]) / period
    atr_vals = [atr]
    for i in range(period, len(true_ranges)):
        atr = (atr * (period - 1) + true_ranges[i]) / period
        atr_vals.append(atr)

    # SuperTrend calculation
    st_vals = [0.0] * n
    upper_band = [0.0] * n
    lower_band = [0.0] * n
    direction = [0] * n  # 1=long, -1=short

    for i in range(period, n):
        atr_idx = i - period
        hl2 = (highs[i] + lows[i]) / 2
        basic_upper = hl2 + factor * atr_vals[atr_idx]
        basic_lower = hl2 - factor * atr_vals[atr_idx]

        # Final upper band
        if basic_upper < upper_band[i - 1] or closes[i - 1] > upper_band[i - 1]:
            upper_band[i] = basic_upper
        else:
            upper_band[i] = upper_band[i - 1]

        # Final lower band
        if basic_lower > lower_band[i - 1] or closes[i - 1] < lower_band[i - 1]:
            lower_band[i] = basic_lower
        else:
            lower_band[i] = lower_band[i - 1]

        # Direction
        if i == period:
            direction[i] = 1 if closes[i] > upper_band[i - 1] else -1
        else:
            if direction[i - 1] == -1 and closes[i] > upper_band[i - 1]:
                direction[i] = 1
            elif direction[i - 1] == 1 and closes[i] < lower_band[i - 1]:
                direction[i] = -1
            else:
                direction[i] = direction[i - 1]

        st_vals[i] = lower_band[i] if direction[i] == 1 else upper_band[i]

    return st_vals[-1], direction[-1]


def find_pivots(candles: List[Dict], depth: int = 5) -> Tuple[List[float], List[float]]:
    """检测Pivot高点和低点"""
    n = len(candles)
    if n < 2 * depth + 1:
        return [], []

    pivot_highs = []
    pivot_lows = []

    for i in range(depth, n - depth):
        h = candles[i]["h"]
        l = candles[i]["l"]

        is_high = all(h >= candles[j]["h"] for j in range(i - depth, i + depth + 1) if j != i)
        is_low = all(l <= candles[j]["l"] for j in range(i - depth, i + depth + 1) if j != i)

        if is_high:
            pivot_highs.append(h)
        if is_low:
            pivot_lows.append(l)

    return pivot_highs, pivot_lows


def calc_ema(closes: List[float], period: int) -> Optional[float]:
    """指数移动平均"""
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return ema
