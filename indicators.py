"""
技术指标计算 — DMI/ADX、StochRSI、SuperTrend、ATR

所有计算基于 OHLCV K线序列。
"""
import math
from typing import List, Dict, Tuple, Optional


def calc_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Wilder's RSI — 返回最新值"""
    n = len(closes)
    if n <= period:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, n):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def _ema(values: List[float], period: int) -> List[float]:
    """EMA 数组"""
    n = len(values)
    result = [float('nan')] * n
    k = 2.0 / (period + 1)
    start = 0
    for i, v in enumerate(values):
        if not math.isnan(v):
            start = i
            result[start] = v
            break
    for i in range(start + 1, n):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def calc_atr(candles: List[Dict], period: int = 14) -> float:
    """
    ATR (Wilder's smoothing)
    candles: [{"h": float, "l": float, "c": float}, ...] 最新在末尾
    返回当前ATR值
    """
    n = len(candles)
    if n < period + 1:
        return 0.0
    tr_list = []
    for i in range(1, n):
        h, l, pc = candles[i]["h"], candles[i]["l"], candles[i - 1]["c"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_list.append(tr)
    avg = sum(tr_list[:period]) / period
    for i in range(period, len(tr_list)):
        avg = (avg * (period - 1) + tr_list[i]) / period
    return avg


def calc_dmi_adx(candles: List[Dict], period: int = 14) -> Tuple[str, float, float]:
    """
    DMI + ADX
    返回 (方向"多"/"空"/"平", ADX值, DI差值)
    """
    n = len(candles)
    if n < period * 2:
        return ("平", 0.0, 0.0)

    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    closes = [c["c"] for c in candles]

    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr_arr = [0.0] * n

    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
        tr_arr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))

    # Wilder's smoothing
    init = period
    smooth_tr = sum(tr_arr[1:init + 1])
    smooth_pdm = sum(plus_dm[1:init + 1])
    smooth_mdm = sum(minus_dm[1:init + 1])

    for i in range(init + 1, n):
        smooth_tr = smooth_tr - smooth_tr / period + tr_arr[i]
        smooth_pdm = smooth_pdm - smooth_pdm / period + plus_dm[i]
        smooth_mdm = smooth_mdm - smooth_mdm / period + minus_dm[i]

    if smooth_tr == 0:
        return ("平", 0.0, 0.0)

    pdi = 100 * smooth_pdm / smooth_tr
    mdi = 100 * smooth_mdm / smooth_tr
    total = pdi + mdi
    dx = 100 * abs(pdi - mdi) / total if total > 0 else 0

    # ADX — 简化为当前dx值（单点）
    adx = dx

    direction = "多" if pdi > mdi else ("空" if mdi > pdi else "平")
    di_diff = pdi - mdi
    return (direction, adx, di_diff)


def calc_stoch_rsi(closes: List[float], rsi_len: int = 10, stoch_len: int = 10,
                   k_smooth: int = 3, d_smooth: int = 3) -> Tuple[float, float]:
    """
    StochRSI
    返回 (K值, D值)
    """
    n = len(closes)
    if n < rsi_len + stoch_len + k_smooth + d_smooth:
        return (50.0, 50.0)

    # 计算RSI序列
    rsi_vals = []
    for end in range(rsi_len, n + 1):
        sub = closes[end - rsi_len:end]
        avg_gain = 0.0
        avg_loss = 0.0
        for i in range(1, rsi_len):
            diff = sub[i] - sub[i - 1]
            if diff > 0:
                avg_gain += diff
            else:
                avg_loss -= diff
        avg_gain /= rsi_len
        avg_loss /= rsi_len
        if avg_loss == 0:
            rsi_vals.append(100.0)
        else:
            rsi_vals.append(100.0 - 100.0 / (1 + avg_gain / avg_loss))

    # Stoch of RSI
    stoch_vals = []
    for i in range(stoch_len - 1, len(rsi_vals)):
        window = rsi_vals[i - stoch_len + 1:i + 1]
        lo, hi = min(window), max(window)
        diff = hi - lo
        stoch_vals.append(100.0 * (rsi_vals[i] - lo) / diff if diff > 0 else 50.0)

    if len(stoch_vals) < k_smooth:
        return (50.0, 50.0)

    # SMA smooth
    def _sma(arr, p):
        if len(arr) < p:
            return [float('nan')] * len(arr)
        result = [float('nan')] * len(arr)
        for i in range(p - 1, len(arr)):
            result[i] = sum(arr[i - p + 1:i + 1]) / p
        return result

    k_vals = _sma(stoch_vals, k_smooth)
    d_vals = _sma(k_vals, d_smooth)

    return (k_vals[-1] if k_vals and not math.isnan(k_vals[-1]) else 50.0,
            d_vals[-1] if d_vals and not math.isnan(d_vals[-1]) else 50.0)


def calc_super_trend(candles: List[Dict], factor: float = 1.0, period: int = 10) -> Tuple[Optional[float], int]:
    """
    SuperTrend
    返回 (st_value, direction)  direction: 1=多头, -1=空头
    """
    n = len(candles)
    if n < period + 2:
        return (None, 0)

    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    closes = [c["c"] for c in candles]

    # ATR
    tr_list = []
    for i in range(1, n):
        tr_list.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    atr_val = sum(tr_list[:period]) / period
    for i in range(period, len(tr_list)):
        atr_val = (atr_val * (period - 1) + tr_list[i]) / period

    hl2 = [(highs[i] + lows[i]) / 2.0 for i in range(n)]

    # 只用最后一部分计算方向
    upper = hl2[-1] + factor * atr_val
    lower = hl2[-1] - factor * atr_val

    # 简化为只看最后一根
    if closes[-1] > upper:
        return (lower, 1)
    elif closes[-1] < lower:
        return (upper, -1)

    # 需要更多上下文确定方向
    upper_prev = hl2[-2] + factor * atr_val if n > period + 1 else upper
    lower_prev = hl2[-2] - factor * atr_val if n > period + 1 else lower

    if closes[-2] >= lower_prev and closes[-1] >= lower:
        return (lower, 1)
    elif closes[-2] <= upper_prev and closes[-1] <= upper:
        return (upper, -1)

    return (lower, 1)  # 默认偏多


def find_pivots(candles: List[Dict], depth: int = 5) -> Tuple[List[float], List[float]]:
    """检测pivot高低点"""
    n = len(candles)
    if n < depth * 2 + 1:
        return ([], [])

    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    pivot_highs = []
    pivot_lows = []

    for i in range(depth, n - depth):
        is_high = all(highs[i] > highs[i - j] and highs[i] > highs[i + j] for j in range(1, depth + 1))
        is_low = all(lows[i] < lows[i - j] and lows[i] < lows[i + j] for j in range(1, depth + 1))
        if is_high:
            pivot_highs.append(highs[i])
        if is_low:
            pivot_lows.append(lows[i])

    return (pivot_highs, pivot_lows)
