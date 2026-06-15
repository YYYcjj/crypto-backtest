"""
多时间框架评分引擎 — 对应 Strategy Engine v4 评分逻辑
"""
from typing import Dict, Optional, Tuple
from config import BacktestConfig


def compute_score(tf_data: Dict[str, Dict], config: BacktestConfig) -> Tuple[int, int]:
    """
    计算多空评分
    tf_data = {"15m": {dmi_dir, srsi, adx, st_near}, "1H": {...}, ...}

    DMI方向分: 15m=1, 1H=2, 4H=3, 1D=4
    StochRSI极端分: 1H超卖/买+1, 4H超卖/买+2, 1D超卖/买+3
    """
    bull_score = 0
    bear_score = 0

    for tf in config.timeframes:
        if tf not in tf_data:
            continue
        data = tf_data[tf]
        w = config.tf_weights.get(tf, 0)

        # DMI方向分
        dmi_dir = data.get("dmi_dir", 0)  # 1=多, -1=空, 0=N/A
        if dmi_dir == 1:
            bull_score += w
        elif dmi_dir == -1:
            bear_score += w

        # StochRSI极端分
        srsi = data.get("srsi")
        if srsi is not None:
            if srsi < config.srsi_oversold:
                bull_score += (3 if tf == "1D" else w)
            elif srsi < config.srsi_1d_bull_extra and tf == "1D":
                bull_score += 1
            if srsi > config.srsi_overbought:
                bear_score += (3 if tf == "1D" else w)
            elif srsi > 70 and tf == "1D":
                bear_score += 1

    return bull_score, bear_score


def check_entry_conditions(tf_data: Dict[str, Dict], config: BacktestConfig,
                           dmi_dir_1d: int, adx_primary: Optional[float],
                           st_near_primary: bool, cooldown_ok: bool,
                           has_position: bool) -> Tuple[bool, bool]:
    """
    检查入场条件
    返回: (long_signal, short_signal)
    """
    bull_score, bear_score = compute_score(tf_data, config)

    # 1D DMI对齐
    cond_1d_long = (not config.use_1d_align) or dmi_dir_1d == 1
    cond_1d_short = (not config.use_1d_align) or dmi_dir_1d == -1

    # ADX过滤
    cond_adx = (not config.use_adx_filter) or \
               (adx_primary is not None and adx_primary >= config.adx_threshold)

    # 综合信号
    long_signal = (bull_score >= config.score_threshold and st_near_primary and
                   cond_1d_long and cond_adx and not has_position and cooldown_ok)
    short_signal = (bear_score >= config.score_threshold and st_near_primary and
                    cond_1d_short and cond_adx and not has_position and cooldown_ok)

    return long_signal, short_signal
