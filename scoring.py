"""
多时间框架评分引擎 — 复刻 Strategy Engine v4
"""
from typing import Dict, Tuple, Optional


def compute_score(tf_data: Dict, weights: Dict[str, int]) -> Tuple[int, int, Dict]:
    """
    计算多TF评分
    tf_data: {"15m": {dmi_dir, srsi, st_dir, adx}, ...}
    weights: {"15m": 1, "1H": 2, ...}
    返回 (long_score, short_score, details)
    """
    total_long = 0
    total_short = 0
    details = {}

    for tf, data in tf_data.items():
        weight = weights.get(tf, 1)
        dmi_dir = data.get("dmi_dir", 0)
        srsi_k = data.get("srsi", (50, 50))[0] if isinstance(data.get("srsi"), tuple) else data.get("srsi", 50)
        st_dir = data.get("st_dir", 0)

        tf_detail = {"dmi_dir": dmi_dir, "srsi": srsi_k, "st_dir": st_dir}

        # DMI方向分
        if dmi_dir == 1:
            tf_detail["dmi_score_long"] = weight
            total_long += weight
        elif dmi_dir == -1:
            tf_detail["dmi_score_short"] = weight
            total_short += weight

        # StochRSI极端加分
        if isinstance(srsi_k, (int, float)):
            if srsi_k < 20:
                total_long += 2
                tf_detail["srsi_bonus_long"] = 2
            elif srsi_k > 80:
                total_short += 2
                tf_detail["srsi_bonus_short"] = 2

        # SuperTrend方向分
        if st_dir == 1:
            total_long += 1
            tf_detail["st_score_long"] = 1
        elif st_dir == -1:
            total_short += 1
            tf_detail["st_score_short"] = 1

        details[tf] = tf_detail

    return total_long, total_short, details


def check_entry_conditions(tf_data: Dict, config, dmi_dir_1d: int,
                           adx_primary: Optional[float], st_near_primary: bool,
                           cooldown_ok: bool, has_position: bool) -> Tuple[bool, bool]:
    """
    检查入场条件
    返回 (long_signal, short_signal)
    """
    long_sig = False
    short_sig = False

    if has_position or not cooldown_ok:
        return False, False

    # 计算评分
    long_score, short_score, _ = compute_score(tf_data, config.tf_weights)

    # ADX过滤器
    adx_pass = True
    if config.use_adx_filter and adx_primary is not None:
        adx_pass = adx_primary >= config.adx_threshold

    # 1D DMI对齐
    d1_pass_long = True
    d1_pass_short = True
    if config.use_1d_align:
        d1_pass_long = dmi_dir_1d >= 0  # 1D不空
        d1_pass_short = dmi_dir_1d <= 0  # 1D不多

    # SuperTrend附近
    st_pass = st_near_primary

    # 综合判断
    if long_score >= config.score_threshold and adx_pass and d1_pass_long and st_pass:
        long_sig = True
    if short_score >= config.score_threshold and adx_pass and d1_pass_short and st_pass:
        short_sig = True

    return long_sig, short_sig
