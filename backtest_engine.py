"""
回测引擎 — 逐K线模拟交易，完整复现 Strategy Engine v4 逻辑
"""
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

from config import BacktestConfig
from indicators import calc_atr, calc_dmi_adx, calc_stoch_rsi, calc_super_trend
from scoring import compute_score, check_entry_conditions
from zone_engine import ZoneEngine
from data_fetcher import TF_SECONDS, get_close_at


class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.cfg = config
        self.equity = config.initial_capital
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []  # [{ts, equity}]
        self.position = 0  # >0 多头, <0 空头, =0 无仓位
        self.position_qty = 0.0
        self.entry_price = 0.0

        # 出场管理
        self.last_exit_bar = -999
        self.cooldown_ok = True
        self.entered_this_bar = False

        # 止损止盈
        self.long_sl = 0.0
        self.short_sl = 0.0
        self.long_target = 0.0
        self.short_target = 0.0
        self.long_step = 0
        self.short_step = 0
        self.long_pending_bar = 0
        self.short_pending_bar = 0
        self.long_pending_level = None
        self.short_pending_level = None

        # 区间引擎
        self.zone_engine = ZoneEngine(
            merge_pct=config.zone_merge_pct,
            min_touches=config.zone_min_touches
        )

        self.current_bar_idx = 0

    def reset(self):
        self.equity = self.cfg.initial_capital
        self.trades = []
        self.equity_curve = []
        self.position = 0
        self.position_qty = 0.0
        self.entry_price = 0.0
        self.last_exit_bar = -999
        self.cooldown_ok = True
        self.entered_this_bar = False
        self.long_sl = 0.0
        self.short_sl = 0.0
        self.long_target = 0.0
        self.short_target = 0.0
        self.long_step = 0
        self.short_step = 0
        self.long_pending_bar = 0
        self.short_pending_bar = 0
        self.long_pending_level = None
        self.short_pending_level = None
        self.current_bar_idx = 0

    def compute_indicators(self, candles: List[Dict]) -> Dict:
        """计算一根K线时间点的所有指标"""
        if len(candles) < 50:
            return {}

        closes = [c["c"] for c in candles]

        # DMI/ADX
        dmi_dir, adx, _ = calc_dmi_adx(candles, self.cfg.dmi_period)

        # StochRSI
        srsi = calc_stoch_rsi(closes)

        # SuperTrend
        st_val, st_dir = calc_super_trend(candles, self.cfg.st_factor, self.cfg.st_period)
        st_near = False
        if st_val is not None and st_val > 0:
            st_near = abs(candles[-1]["c"] - st_val) / st_val <= self.cfg.near_pct

        # ATR
        atr = calc_atr(candles, self.cfg.atr_period)

        return {
            "dmi_dir": 1 if dmi_dir == "多" else (-1 if dmi_dir == "空" else 0),
            "adx": adx,
            "srsi": srsi,
            "st_val": st_val,
            "st_dir": st_dir,
            "st_near": st_near,
            "atr": atr,
            "close": candles[-1]["c"]
        }

    def calc_sl_long(self, current_price: float, atr: float) -> float:
        """计算多头止损价"""
        atr_sl = current_price - max(
            self.cfg.min_sl_pct * current_price,
            min(self.cfg.max_sl_pct * current_price, self.cfg.sl_atr_mult * atr)
        )
        if not self.cfg.use_zone_sl:
            return atr_sl

        sup = self.zone_engine.nearest_support(current_price)
        if sup is not None and sup < current_price:
            zone_dist = (current_price - sup) / current_price
            if self.cfg.min_sl_pct <= zone_dist <= self.cfg.max_sl_pct:
                return sup
        return atr_sl

    def calc_sl_short(self, current_price: float, atr: float) -> float:
        """计算空头止损价"""
        atr_sl = current_price + max(
            self.cfg.min_sl_pct * current_price,
            min(self.cfg.max_sl_pct * current_price, self.cfg.sl_atr_mult * atr)
        )
        if not self.cfg.use_zone_sl:
            return atr_sl

        res = self.zone_engine.nearest_resistance(current_price)
        if res is not None and res > current_price:
            zone_dist = (res - current_price) / current_price
            if self.cfg.min_sl_pct <= zone_dist <= self.cfg.max_sl_pct:
                return res
        return atr_sl

    def enter_long(self, price: float, atr: float, bar_idx: int):
        """多头入场"""
        self.position = 1
        qty_pct = self.cfg.position_pct
        self.position_qty = (self.equity * qty_pct) / price
        self.entry_price = price

        self.long_sl = self.calc_sl_long(price, atr)
        min_dist = self.cfg.tp_atr_min * atr
        zone_tp = self.zone_engine.first_above(price, min_dist)
        self.long_target = zone_tp if zone_tp is not None else price + 4.0 * atr
        self.long_step = 0
        self.long_pending_bar = 0
        self.long_pending_level = None

        self.entered_this_bar = True

    def enter_short(self, price: float, atr: float, bar_idx: int):
        """空头入场"""
        self.position = -1
        qty_pct = self.cfg.position_pct
        self.position_qty = (self.equity * qty_pct) / price
        self.entry_price = price

        self.short_sl = self.calc_sl_short(price, atr)
        min_dist = self.cfg.tp_atr_min * atr
        zone_tp = self.zone_engine.first_below(price, min_dist)
        self.short_target = zone_tp if zone_tp is not None else price - 4.0 * atr
        self.short_step = 0
        self.short_pending_bar = 0
        self.short_pending_level = None

        self.entered_this_bar = True

    def exit_long(self, price: float, reason: str, bar_idx: int):
        """多头离场"""
        pnl = (price - self.entry_price) * self.position_qty
        pnl_pct = (price - self.entry_price) / self.entry_price * 100
        commission = self.entry_price * self.position_qty * self.cfg.commission * 2
        self.equity += pnl - commission

        self.trades.append({
            "entry_time": self.entry_time,
            "exit_time": datetime.fromtimestamp(bar_idx / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "direction": "LONG",
            "entry": self.entry_price,
            "exit": price,
            "pnl": pnl - commission,
            "pnl_pct": pnl_pct,
            "reason": reason,
            "steps": self.long_step
        })

        self.position = 0
        self.position_qty = 0
        self.last_exit_bar = bar_idx
        self.entered_this_bar = False
        self.long_pending_bar = 0
        self.long_pending_level = None

    def exit_short(self, price: float, reason: str, bar_idx: int):
        """空头离场"""
        pnl = (self.entry_price - price) * self.position_qty
        pnl_pct = (self.entry_price - price) / self.entry_price * 100
        commission = self.entry_price * self.position_qty * self.cfg.commission * 2
        self.equity += pnl - commission

        self.trades.append({
            "entry_time": self.entry_time,
            "exit_time": datetime.fromtimestamp(bar_idx / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "direction": "SHORT",
            "entry": self.entry_price,
            "exit": price,
            "pnl": pnl - commission,
            "pnl_pct": pnl_pct,
            "reason": reason,
            "steps": self.short_step
        })

        self.position = 0
        self.position_qty = 0
        self.last_exit_bar = bar_idx
        self.entered_this_bar = False
        self.short_pending_bar = 0
        self.short_pending_level = None

    def process_bar(self, candles_all_tf: Dict[str, List[Dict]], bar_ts: int,
                    bar_idx_map: Dict[str, int]):
        """
        处理一根K线
        candles_all_tf: {"15m": [...], "1H": [...], "4H": [...], "1D": [...]}
        bar_ts: 当前时间戳
        """
        self.current_bar_idx = bar_ts

        # 冷却检查
        self.cooldown_ok = (bar_ts - self.last_exit_bar) > \
                           self.cfg.cooldown_bars * TF_SECONDS[self.cfg.primary_tf]

        # 计算各TF指标
        tf_data = {}
        primary_close = None
        primary_atr = None

        for tf in self.cfg.timeframes:
            if tf not in candles_all_tf:
                continue
            candles = [c for c in candles_all_tf[tf] if c["ts"] <= bar_ts]
            if len(candles) < 50:
                continue
            tf_data[tf] = self.compute_indicators(candles)
            if tf == self.cfg.primary_tf:
                primary_close = tf_data[tf]["close"]
                primary_atr = tf_data[tf]["atr"]

        if not tf_data or primary_close is None:
            return

        # 更新关键区间
        primary_candles = [c for c in candles_all_tf[self.cfg.primary_tf] if c["ts"] <= bar_ts]
        self.zone_engine.update_from_candles(primary_candles, self.cfg.zone_depth)

        # 获取1D DMI方向
        dmi_dir_1d = 0
        if "1D" in tf_data:
            dmi_dir_1d = tf_data["1D"]["dmi_dir"]

        # ADX
        adx_primary = tf_data[self.cfg.primary_tf].get("adx")
        st_near_primary = tf_data[self.cfg.primary_tf].get("st_near", False)

        # ── 持仓管理 ──
        if self.position > 0:
            self._manage_long(primary_close, primary_atr, bar_ts)
        elif self.position < 0:
            self._manage_short(primary_close, primary_atr, bar_ts)

        # ── 入场信号 ──
        if self.position == 0:
            long_sig, short_sig = check_entry_conditions(
                tf_data, self.cfg, dmi_dir_1d, adx_primary,
                st_near_primary, self.cooldown_ok, self.position != 0
            )

            if long_sig and not self.entered_this_bar:
                self.entry_time = datetime.fromtimestamp(bar_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                self.enter_long(primary_close, primary_atr, bar_ts)

            elif short_sig and not self.entered_this_bar:
                self.entry_time = datetime.fromtimestamp(bar_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                self.enter_short(primary_close, primary_atr, bar_ts)

        # 记录权益曲线
        unrealized = 0
        if self.position > 0:
            unrealized = (primary_close - self.entry_price) * self.position_qty
        elif self.position < 0:
            unrealized = (self.entry_price - primary_close) * self.position_qty

        self.equity_curve.append({
            "ts": bar_ts,
            "equity": self.equity + unrealized
        })

    def _manage_long(self, price: float, atr: float, bar_ts: int):
        """多头持仓管理 — 阶梯止盈"""
        use_confirm = self.cfg.use_confirm
        step_buffer = self.cfg.step_buffer * atr

        # 待确认突破
        if use_confirm and self.long_pending_bar > 0 and bar_ts > self.long_pending_bar:
            if price >= self.long_pending_level:
                next_r = self.zone_engine.next_above(self.long_pending_level)
                if next_r is not None:
                    self.long_sl = self.long_pending_level - step_buffer
                    self.long_target = next_r
                    self.long_step += 1
                else:
                    self.exit_long(price, "TP", bar_ts)
                    return
            self.long_pending_bar = 0
            self.long_pending_level = None

        # 止损
        if price <= self.long_sl:
            self.exit_long(price, "SL", bar_ts)
            return

        # 达到止盈目标
        if price >= self.long_target:
            if use_confirm and self.long_pending_bar == 0:
                self.long_pending_bar = bar_ts
                self.long_pending_level = self.long_target
            else:
                next_r = self.zone_engine.next_above(self.long_target)
                if next_r is not None:
                    self.long_sl = self.long_target - step_buffer
                    self.long_target = next_r
                    self.long_step += 1
                else:
                    self.exit_long(price, "TP", bar_ts)

    def _manage_short(self, price: float, atr: float, bar_ts: int):
        """空头持仓管理 — 阶梯止盈"""
        use_confirm = self.cfg.use_confirm
        step_buffer = self.cfg.step_buffer * atr

        if use_confirm and self.short_pending_bar > 0 and bar_ts > self.short_pending_bar:
            if price <= self.short_pending_level:
                next_s = self.zone_engine.next_below(self.short_pending_level)
                if next_s is not None:
                    self.short_sl = self.short_pending_level + step_buffer
                    self.short_target = next_s
                    self.short_step += 1
                else:
                    self.exit_short(price, "TP", bar_ts)
                    return
            self.short_pending_bar = 0
            self.short_pending_level = None

        if price >= self.short_sl:
            self.exit_short(price, "SL", bar_ts)
            return

        if price <= self.short_target:
            if use_confirm and self.short_pending_bar == 0:
                self.short_pending_bar = bar_ts
                self.short_pending_level = self.short_target
            else:
                next_s = self.zone_engine.next_below(self.short_target)
                if next_s is not None:
                    self.short_sl = self.short_target + step_buffer
                    self.short_target = next_s
                    self.short_step += 1
                else:
                    self.exit_short(price, "TP", bar_ts)

    def run(self, data_all_tf: Dict[str, List[Dict]], symbol: str):
        """
        运行回测
        data_all_tf: {"15m": [...], "1H": [...], "4H": [...], "1D": [...]}
        """
        self.reset()
        primary_candles = data_all_tf.get(self.cfg.primary_tf, [])

        if len(primary_candles) < self.cfg.warmup_bars:
            print(f"  ⚠️ {symbol} 数据不足，跳过")
            return

        # 对齐所有TF的最晚起始时间
        min_starts = {}
        for tf, candles in data_all_tf.items():
            if candles:
                min_starts[tf] = candles[0]["ts"]

        # 从 warmup 之后开始逐K线
        start_idx = self.cfg.warmup_bars
        total = len(primary_candles)

        print(f"  🔬 {symbol}: {total}根K线, 从第{start_idx}根开始...")
        progress_step = max(1, (total - start_idx) // 10)

        for i in range(start_idx, total):
            bar_ts = primary_candles[i]["ts"]
            self.process_bar(data_all_tf, bar_ts, {})

            if (i - start_idx) % progress_step == 0:
                pct = (i - start_idx) * 100 // (total - start_idx)
                print(f"    进度 {pct}% ({i - start_idx}/{total - start_idx})")

        # 强制平仓
        if self.position != 0:
            last_close = primary_candles[-1]["c"]
            if self.position > 0:
                self.exit_long(last_close, "EOD", primary_candles[-1]["ts"])
            else:
                self.exit_short(last_close, "EOD", primary_candles[-1]["ts"])

        return self.generate_report(symbol)

    def generate_report(self, symbol: str) -> Dict:
        """生成回测报告"""
        trades = self.trades
        if not trades:
            return {"symbol": symbol, "trades": 0, "win_rate": 0}

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        long_trades = [t for t in trades if t["direction"] == "LONG"]
        short_trades = [t for t in trades if t["direction"] == "SHORT"]

        total_pnl = sum(t["pnl"] for t in trades)
        win_rate = len(wins) / len(trades) * 100

        # 最大回撤
        if self.equity_curve:
            peak = self.cfg.initial_capital
            max_dd = 0.0
            for pt in self.equity_curve:
                if pt["equity"] > peak:
                    peak = pt["equity"]
                dd = (peak - pt["equity"]) / peak * 100
                if dd > max_dd:
                    max_dd = dd
        else:
            max_dd = 0.0

        return {
            "symbol": symbol,
            "total_trades": len(trades),
            "win_trades": len(wins),
            "loss_trades": len(losses),
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "total_return": round(total_pnl / self.cfg.initial_capital * 100, 2),
            "max_drawdown": round(max_dd, 2),
            "sharpe": self._calc_sharpe(),
            "avg_win": round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0,
            "profit_factor": self._calc_profit_factor(wins, losses),
            "long_count": len(long_trades),
            "short_count": len(short_trades),
            "long_win_rate": round(len([t for t in long_trades if t["pnl"] > 0]) / len(long_trades) * 100, 1) if long_trades else 0,
            "short_win_rate": round(len([t for t in short_trades if t["pnl"] > 0]) / len(short_trades) * 100, 1) if short_trades else 0,
            "trades": trades,
            "equity_curve": self.equity_curve
        }

    def _calc_sharpe(self) -> float:
        """简化夏普比率"""
        if len(self.equity_curve) < 2:
            return 0.0
        returns = []
        for i in range(1, len(self.equity_curve)):
            r = (self.equity_curve[i]["equity"] - self.equity_curve[i - 1]["equity"]) / \
                self.equity_curve[i - 1]["equity"]
            returns.append(r)
        if not returns:
            return 0.0
        avg_r = sum(returns) / len(returns)
        var = sum((r - avg_r) ** 2 for r in returns) / len(returns)
        std = var ** 0.5
        if std == 0:
            return 0.0
        return avg_r / std * (252 ** 0.5)  # 年化（简化）

    def _calc_profit_factor(self, wins: List[Dict], losses: List[Dict]) -> float:
        total_win = sum(t["pnl"] for t in wins) if wins else 0
        total_loss = abs(sum(t["pnl"] for t in losses)) if losses else 0
        if total_loss == 0:
            return float('inf') if total_win > 0 else 0
        return round(total_win / total_loss, 2)
