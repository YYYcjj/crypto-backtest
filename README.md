# crypto-backtest

OKX 加密货币多时间框架策略回测引擎

基于 Strategy Engine v4 — DMI/ADX + StochRSI + SuperTrend 多维度评分系统，支持 15m/1H/4H/1D 四周期联动回测。

## 策略核心

| 组件 | 说明 |
|------|------|
| **趋势判断** | DMI 多时间框架方向打分（15m=1, 1H=2, 4H=3, 1D=4） |
| **极端检测** | StochRSI 超卖(<20)/超买(>80) 加分 |
| **入场过滤** | SuperTrend 附近 + ADX≥20 趋势确认 + 1D DMI 对齐 |
| **止损** | ATR×2 动态止损 / 关键支撑阻力区间止损 |
| **止盈** | 关键阻力/支撑位阶梯止盈 + 收盘确认突破 |
| **冷却** | 出场后 5 根 K 线冷却期 |

## 安装

```bash
pip install -r requirements.txt
```

## 使用

```bash
python run_backtest.py
```

### 自定义配置

编辑 `config.py`：

```python
config = BacktestConfig(
    symbols=["BTC-USDT", "ETH-USDT", "SOL-USDT"],
    timeframes=["15m", "1H", "4H", "1D"],
    primary_tf="1H",
    backtest_days=90,
    initial_capital=10000,
    score_threshold=9,
)
```

## 输出

- `results/backtest_report.html` — HTML 可视化报告（权益曲线、交易明细、品种汇总）
- `results/backtest_results.json` — JSON 格式回测数据

## 项目结构

```
crypto-backtest/
├── config.py           # 策略参数配置
├── indicators.py       # 指标计算 (DMI/ADX/StochRSI/SuperTrend/ATR/Pivot)
├── data_fetcher.py     # OKX API 数据获取 + 缓存
├── scoring.py          # 多时间框架评分引擎
├── zone_engine.py      # 关键支撑阻力区间管理
├── backtest_engine.py  # 回测引擎（逐K线模拟交易）
├── report.py           # HTML 报告生成
├── run_backtest.py     # 主入口
└── requirements.txt
```
