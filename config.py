"""
策略回测配置 — 对应 Strategy Engine v4 参数
"""
from dataclasses import dataclass, field
from typing import List

@dataclass
class BacktestConfig:
    # ── 交易品种 ──
    symbols: List[str] = field(default_factory=lambda: [
        "BTC-USDT", "ETH-USDT", "SOL-USDT",
        "APT-USDT", "ORDI-USDT", "DOGE-USDT"
    ])

    # ── 时间框架 ──
    timeframes: List[str] = field(default_factory=lambda: ["15m", "1H", "4H", "1D"])
    primary_tf: str = "1H"  # 主交易周期

    # ── 回测区间 ──
    backtest_days: int = 90
    warmup_bars: int = 200  # 指标预热K线数

    # ── 评分权重 (按TF从小到大) ──
    tf_weights = {"15m": 1, "1H": 2, "4H": 3, "1D": 4}
    score_threshold: int = 9  # 入场最低分
    score_max: int = 12       # 理论最高分

    # ── StochRSI 极端值 ──
    srsi_oversold: float = 20
    srsi_overbought: float = 80
    srsi_1d_bull_extra: float = 30  # 1D SRSI<30给额外1分

    # ── DMI/ADX ──
    dmi_period: int = 14
    use_1d_align: bool = True       # 1D DMI必须对齐
    use_adx_filter: bool = True
    adx_threshold: int = 20

    # ── SuperTrend ──
    st_period: int = 10
    st_factor: float = 1.0
    near_pct: float = 0.01  # ST附近判定阈值

    # ── ATR ──
    atr_period: int = 14

    # ── 止损 ──
    sl_atr_mult: float = 2.0
    min_sl_pct: float = 0.02
    max_sl_pct: float = 0.04
    use_zone_sl: bool = True

    # ── 止盈 ──
    tp_atr_min: float = 1.5
    use_confirm: bool = True   # 收盘确认突破
    step_buffer: float = 0.5   # 阶梯缓冲(ATR倍数)

    # ── 关键区间 ──
    zone_depth: int = 5        # pivot左右K线
    zone_merge_pct: float = 0.005
    zone_min_touches: int = 3  # 最少触及次数才算有效区间

    # ── 出场冷却 ──
    cooldown_bars: int = 5

    # ── 资金管理 ──
    initial_capital: float = 10000
    position_pct: float = 0.95   # 仓位占比
    commission: float = 0.001    # 手续费 0.1%
    pyramiding: int = 0           # 0=不叠加

    # ── 输出 ──
    output_dir: str = "results"
    cache_dir: str = "cache"
