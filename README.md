# ORB Backtester — SPY Opening Range Breakout Strategy

A Python backtesting engine for the **Opening Range Breakout (ORB)** strategy on SPY (S&P 500 ETF), built with `yfinance`, `pandas`, and `matplotlib`.

---

## What is ORB?

The Opening Range Breakout strategy works like this:

1. Wait for the first **15 minutes** after the NY market opens (9:30–9:45 AM ET)
2. Record the **highest high** and **lowest low** of those 15 minutes — this is the "opening range"
3. If price **breaks above** the range high with momentum → **BUY**
4. If price **breaks below** the range low with momentum → **SHORT**
5. Exit at your target, stop, or 2:00 PM ET — whichever comes first

Think of the opening range as the market "deciding" which direction it wants to go for the day. A clean breakout with volume behind it usually follows through.

---

## Strategy Rules (v3)

| Rule | Detail |
|---|---|
| Opening range | First 15 minutes (9:30–9:45 AM ET) |
| Entry trigger | A bar must **close** beyond the range (not just wick through it) |
| Volume filter | Breakout bar volume must be > 1.1× the average OR volume |
| Trend filter | LONG only when SPY is above its 20-day MA; SHORT only below |
| Stop loss | Other side of the opening range |
| Take profit | 2× the opening range width (2:1 reward/risk) |
| EOD exit | 2:00 PM ET — any open trade is closed |

---

## How to Read the Results

### Terminal Output

```
Days: 20  |  Trades taken: 3  |  No signal: 17  |  Trend/Vol filtered: 0
Win rate   : 66.7%  (2W / 1L)
Target hit : 2  |  Stopped : 0  |  EOD : 1
Total P&L  : $+745.59
Expectancy : $+248.53 per trade
Prof factor: 6.04
Max DD     : $147.80
```

| Term | What it means |
|---|---|
| **Days** | Total trading days in the window |
| **Trades taken** | Days where a valid signal fired and a trade was placed |
| **No signal** | Days where price never broke the opening range — no trade |
| **Trend/Vol filtered** | Days where a breakout happened but was rejected by the trend or volume filter |
| **Win rate** | % of trades that made money |
| **Target hit** | Trade hit the 2:1 take-profit level |
| **Stopped** | Trade hit the stop loss (other side of the OR) |
| **EOD** | Trade was still open at 2PM and was closed at market price |
| **Total P&L** | Total dollars made/lost across all trades (100 shares per trade) |
| **Expectancy** | Average P&L per trade — if positive, the strategy has an edge |
| **Profit factor** | Total wins ÷ total losses. Above 1.5 is good. Above 2.0 is strong |
| **Max drawdown** | Biggest peak-to-trough loss during the period |

### Charts (orb_results_v3.png)

The chart has **3 rows**:

**Row 1 — Cumulative P&L per month**
- The line going up = money being made over time
- Green shading = in profit, red shading = in drawdown
- Each panel is one 20-day window

**Row 2 — Daily P&L bars**
- Green bar = winning trade, red bar = losing trade
- Shows win rate visually and how big wins compare to losses
- Win rate % and profit factor shown in the title

**Row 3 — Combined equity curve (all 3 months)**
- The most important chart — shows whether the strategy is consistently profitable
- Dotted vertical lines mark where each month starts
- A smooth upward slope = consistent edge across different market conditions

---

## Backtest Results (v3, 60-day walk-forward)

| Period | Trades | Win Rate | Total P&L | Profit Factor |
|---|---|---|---|---|
| Month 1 (Mar) | 3 | 66.7% | +$745 | 6.04 |
| Month 2 (Apr) | 3 | 100% | +$674 | 674 |
| Month 3 (May) | 2 | 100% | +$340 | 340 |
| **Combined** | **8** | **87.5%** | **+$1,760** | **12.91** |

> ⚠️ **Important:** Only 8 trades across 60 days is a small sample. These results are promising but not statistically conclusive. Paper trade for at least 20–30 live setups before risking real money.

---

## Installation

```bash
# 1. Create and activate conda environment
conda create -n trading python=3.11 -y
conda activate trading

# 2. Install dependencies
pip install yfinance pandas numpy matplotlib

# 3. Run the backtest
python orb_backtest.py
```

---

## Output Files

| File | Description |
|---|---|
| `orb_results_v3.png` | Walk-forward chart (3 months, 3 rows) |
| `orb_trade_log_v3.csv` | Full trade-by-trade log with entry/exit prices and P&L |

---

## Configuration

At the top of `orb_backtest.py` you can adjust:

```python
TICKER            = "SPY"    # Change to any ticker (e.g. "QQQ", "AAPL")
OPENING_MINUTES   = 15       # Length of opening range in minutes
REWARD_RISK       = 2.0      # Take profit = 2× stop distance
TRADE_SIZE        = 100      # Number of shares per trade
VOLUME_MULTIPLIER = 1.1      # Min volume vs OR average to confirm breakout
EOD_EXIT_TIME     = time(14, 0)  # Exit all trades by 2PM ET
MA_PERIOD         = 20       # Days for trend filter moving average
```

---

## Version History

| Version | Change | Result |
|---|---|---|
| v1 | Basic ORB, 30-min range, no filters | -$1,271 (losing) |
| v2 | 15-min range + close filter + trend filter + 2PM exit | +$1,025 (profitable) |
| v3 | Added volume filter + walk-forward test across 3 months | +$1,760 combined |

---

## Disclaimer

This is for educational and research purposes only. Past backtest performance does not guarantee future results. Do not risk money you cannot afford to lose.
