"""
关键区间引擎 — 检测Pivot支撑阻力区间、角色翻转、合并
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from indicators import find_pivots


@dataclass
class Zone:
    level: float
    touches: int = 0
    is_resistance: bool = True  # True=阻力, False=支撑

    def flip(self):
        self.is_resistance = not self.is_resistance


class ZoneEngine:
    """关键区间管理器"""

    def __init__(self, merge_pct: float = 0.005, min_touches: int = 3):
        self.zones: List[Zone] = []
        self.merge_pct = merge_pct
        self.min_touches = min_touches

    def find_zone(self, price: float) -> int:
        """查找价格附近的已有区间，返回索引，-1表示未找到"""
        for i, z in enumerate(self.zones):
            if abs(price - z.level) / price < self.merge_pct:
                return i
        return -1

    def add_zone(self, price: float, is_resistance: bool):
        idx = self.find_zone(price)
        if idx >= 0:
            self.zones[idx].touches += 1
        else:
            self.zones.append(Zone(level=price, touches=1, is_resistance=is_resistance))

    def check_flips(self, closes: List[Dict]):
        """检查区间角色翻转（突破后阻力变支撑、支撑变阻力）"""
        if len(closes) < 2:
            return
        prev_close = closes[-2]["c"]
        curr_close = closes[-1]["c"]

        for z in self.zones:
            crosses_up = prev_close < z.level and curr_close > z.level
            crosses_down = prev_close > z.level and curr_close < z.level

            if z.is_resistance and crosses_up:
                z.flip()
            elif not z.is_resistance and crosses_down:
                z.flip()

    def get_key_zones(self, current_price: float) -> Tuple[List[float], List[float]]:
        """获取当前价格附近的阻力区和支撑区（至少min_touches次触及）"""
        resistances = []
        supports = []
        for z in self.zones:
            if z.touches >= self.min_touches:
                if z.level > current_price and z.is_resistance:
                    resistances.append(z.level)
                elif z.level < current_price and not z.is_resistance:
                    supports.append(z.level)
        resistances.sort()
        supports.sort(reverse=True)
        return resistances, supports

    def nearest_resistance(self, current_price: float) -> Optional[float]:
        resistances, _ = self.get_key_zones(current_price)
        return resistances[0] if resistances else None

    def nearest_support(self, current_price: float) -> Optional[float]:
        _, supports = self.get_key_zones(current_price)
        return supports[0] if supports else None

    def first_above(self, current_price: float, min_dist: float) -> Optional[float]:
        """最近的、距离>=min_dist的阻力位"""
        resistances, _ = self.get_key_zones(current_price)
        for r in resistances:
            if r - current_price >= min_dist:
                return r
        return None

    def first_below(self, current_price: float, min_dist: float) -> Optional[float]:
        """最近的、距离>=min_dist的支撑位"""
        _, supports = self.get_key_zones(current_price)
        for s in supports:
            if current_price - s >= min_dist:
                return s
        return None

    def next_above(self, target: float) -> Optional[float]:
        """target之上的第一个阻力位"""
        all_resistances = sorted([z.level for z in self.zones
                                  if z.is_resistance and z.touches >= self.min_touches])
        for r in all_resistances:
            if r > target:
                return r
        return None

    def next_below(self, target: float) -> Optional[float]:
        """target之下的第一个支撑位"""
        all_supports = sorted([z.level for z in self.zones
                               if not z.is_resistance and z.touches >= self.min_touches],
                              reverse=True)
        for s in all_supports:
            if s < target:
                return s
        return None

    def update_from_candles(self, candles: List[Dict], depth: int = 5):
        """从K线序列更新pivot点"""
        pivot_highs, pivot_lows = find_pivots(candles, depth)
        for ph in pivot_highs:
            self.add_zone(ph, True)
        for pl in pivot_lows:
            self.add_zone(pl, False)
        self.check_flips(candles)

    def stats(self) -> Dict:
        """区间统计"""
        total = len(self.zones)
        valid = sum(1 for z in self.zones if z.touches >= self.min_touches)
        return {"total": total, "valid": valid}
