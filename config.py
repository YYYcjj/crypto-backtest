"""
策略回测配置 — 对应 Strategy Engine v4 参数
"""
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class BacktestConfig:
    # ── 交易品种 ──
    symbols: List[str] = field(default_factory=lambda: [
        "BTC-USDT", "ETH-USDT", "SOL-USDT",
        "APT-USDT", "ORDI-USDT", "DOGE-USDT",
        "PUMP-USDT", "HUMA-USDT", "APR-USDT",
    ])

    # ── 时间框架 ──
    timeframes: List[str] = field(default_factory=lambda: ["15m", "1H", "4H", "1D"])
    primary_tf: str = "1H"

    # ── 回测区间 ──
    backtest_days: int = 90
    warmup_bars: int = 200

    # ── 评分权重 ──
    tf_weights: Dict[str, int] = field(default_factory=lambda: {"15m": 1, "1H": 2, "4H": 3, "1D": 4})
    score_threshold: int = 9
    score_max: int = 12

    # ── StochRSI ──
    srsi_oversold: float = 20.0
    srsi_overbought: float = 80.0
    srsi_1d_bull_extra: float = 30.0

    # ── DMI/ADX ──
    dmi_period: int = 14
    use_1d_align: bool = True
    use_adx_filter: bool = True
    adx_threshold: int = 20

    # ── SuperTrend ──
    st_period: int = 10
    st_factor: float = 1.0
    near_pct: float = 0.01

    # ── ATR ──
    atr_period: int = 14

    # ── 止损 ──
    sl_atr_mult: float = 2.0
    min_sl_pct: float = 0.02
    max_sl_pct: float = 0.04
    use_zone_sl: bool = True

    # ── 止盈 ──
    tp_atr_min: float = 1.5
    use_confirm: bool = True
    step_buffer: float = 0.5

    # ── 关键区间 ──
    zone_depth: int = 5
    zone_merge_pct: float = 0.005
    zone_min_touches: int = 3

    # ── 出场冷却 ──
    cooldown_bars: int = 5

    # ── 资金管理 ──
    initial_capital: float = 10000.0
    position_pct: float = 0.95
    commission: float = 0.001
    pyramiding: int = 0

    # ── 输出路径 ──
    output_dir: str = "results"
    cache_dir: str = "cache"


# 快速预设
PRESETS = {
    "default": BacktestConfig(),
    "aggressive": BacktestConfig(
        score_threshold=7, sl_atr_mult=1.5, cooldown_bars=3,
    ),
    "conservative": BacktestConfig(
        score_threshold=11, sl_atr_mult=2.5, cooldown_bars=8, use_1d_align=True,
    ),
    "quick_test": BacktestConfig(
        symbols=["BTC-USDT"], backtest_days=30, score_threshold=8,
    ),
}
