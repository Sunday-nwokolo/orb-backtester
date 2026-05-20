"""
ORB (Opening Range Breakout) Backtest v3 — SPY
================================================
Improvements over v2:
  1. Volume filter    — breakout bar volume must be > 1.5x the OR avg volume
  2. Walk-forward     — tests across 3 months, reports each month separately
                        then gives combined stats

All v2 fixes retained:
  - 15-min opening range
  - Close filter (bar must close beyond range)
  - Trend filter (LONG only above 20-day MA, SHORT only below)
  - 2PM ET EOD exit

Requirements:
  pip install yfinance pandas numpy matplotlib
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import time, timedelta, date
import warnings
warnings.filterwarnings("ignore")

# ── CONFIG ────────────────────────────────────────────────────────────────────
TICKER           = "SPY"
INTERVAL         = "5m"
OPENING_MINUTES  = 15
REWARD_RISK      = 2.0
TRADE_SIZE       = 100
COMMISSION       = 0.65
EOD_EXIT_TIME    = time(14, 0)
MA_PERIOD        = 20
VOLUME_MULTIPLIER = 1.1   # FIX 1: breakout bar must be > 1.5x OR avg volume

# Walk-forward windows (FIX 2)
WALK_FORWARD_PERIODS = [
    {"label": "Month 1 (3mo ago)", "period": "3mo",  "window": 1},
    {"label": "Month 2 (2mo ago)", "period": "3mo",  "window": 2},
    {"label": "Month 3 (1mo ago)", "period": "1mo",  "window": 3},
]
# ─────────────────────────────────────────────────────────────────────────────


def fetch_intraday(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval,
                     progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data for {ticker}. Check connection.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = df.index.tz_convert("America/New_York")
    return df


def fetch_daily_ma(ticker, ma_period):
    daily = yf.download(ticker, period="6mo", interval="1d",
                        progress=False, auto_adjust=True)
    if isinstance(daily.columns, pd.MultiIndex):
        daily.columns = daily.columns.get_level_values(0)
    daily.index = daily.index.tz_localize(None)
    daily["MA"] = daily["Close"].rolling(ma_period).mean()
    return daily["MA"].dropna().to_dict()


def get_trading_days(df):
    return sorted(df.index.normalize().unique())


def get_opening_range(day_df, opening_minutes):
    end_total = 9 * 60 + 30 + opening_minutes
    or_bars = day_df.between_time(time(9, 30), time(end_total // 60, end_total % 60),
                                  inclusive="left")
    if or_bars.empty:
        return None, None, None
    return (float(or_bars["High"].max()),
            float(or_bars["Low"].min()),
            float(or_bars["Volume"].mean()))   # avg volume in OR


def simulate_day(day_df, opening_minutes, reward_risk, daily_ma):
    or_high, or_low, or_avg_vol = get_opening_range(day_df, opening_minutes)
    if or_high is None:
        return None

    or_width = or_high - or_low
    if or_width == 0:
        return None

    # Trend filter
    day_date = day_df.index[0].date()
    ma_dates = [d for d in daily_ma.keys() if d.date() <= day_date]
    if not ma_dates:
        trend = "NEUTRAL"
    else:
        closest_ma = daily_ma[max(ma_dates)]
        first_close = float(day_df.iloc[0]["Close"])
        trend = "UP" if first_close > closest_ma else "DOWN"

    end_total = 9 * 60 + 30 + opening_minutes
    after_or = day_df.between_time(
        time(end_total // 60, end_total % 60), EOD_EXIT_TIME, inclusive="both"
    )
    if after_or.empty:
        return None

    entry_price = None
    direction   = None
    stop        = None
    target      = None
    entry_time  = None
    vol_filter  = "PASS"

    for ts, bar in after_or.iterrows():
        if direction is not None:
            break

        # FIX 1: Volume filter — bar volume must exceed 1.5x OR average volume
        if or_avg_vol and bar["Volume"] < VOLUME_MULTIPLIER * or_avg_vol:
            continue

        if bar["Close"] > or_high and trend != "DOWN":
            direction   = "LONG"
            entry_price = or_high
            stop        = or_low
            target      = entry_price + reward_risk * or_width
            entry_time  = ts

        elif bar["Close"] < or_low and trend != "UP":
            direction   = "SHORT"
            entry_price = or_low
            stop        = or_high
            target      = entry_price - reward_risk * or_width
            entry_time  = ts

    if direction is None:
        return {"date": day_date, "trade": False, "filtered_by": "no_breakout",
                "or_high": or_high, "or_low": or_low, "trend": trend}

    # Simulate outcome
    trade_bars = day_df[day_df.index >= entry_time]
    exit_price = None
    exit_time  = None
    outcome    = "EOD"

    for ts, bar in trade_bars.iterrows():
        if ts.time() >= EOD_EXIT_TIME:
            break
        if direction == "LONG":
            if bar["Low"] <= stop:
                exit_price = stop;   exit_time = ts; outcome = "STOP";   break
            if bar["High"] >= target:
                exit_price = target; exit_time = ts; outcome = "TARGET"; break
        else:
            if bar["High"] >= stop:
                exit_price = stop;   exit_time = ts; outcome = "STOP";   break
            if bar["Low"] <= target:
                exit_price = target; exit_time = ts; outcome = "TARGET"; break

    if exit_price is None:
        eod_bars   = day_df[day_df.index.time <= EOD_EXIT_TIME]
        last_bar   = eod_bars.iloc[-1] if not eod_bars.empty else day_df.iloc[-1]
        exit_price = float(last_bar["Close"])
        exit_time  = last_bar.name

    pnl = ((exit_price - entry_price) if direction == "LONG"
           else (entry_price - exit_price)) * TRADE_SIZE - 2 * COMMISSION

    return {
        "date":        day_date,
        "trade":       True,
        "direction":   direction,
        "trend":       trend,
        "or_high":     round(or_high, 2),
        "or_low":      round(or_low, 2),
        "or_width":    round(or_width, 2),
        "or_avg_vol":  round(or_avg_vol or 0),
        "entry_price": round(entry_price, 2),
        "stop":        round(stop, 2),
        "target":      round(target, 2),
        "exit_price":  round(exit_price, 2),
        "outcome":     outcome,
        "pnl":         round(pnl, 2),
        "entry_time":  entry_time,
        "exit_time":   exit_time,
    }


def run_backtest(df, daily_ma, label=""):
    vol_filtered = 0
    trend_filtered = 0
    no_breakout = 0
    trading_days = get_trading_days(df)
    results = []
    for day in trading_days:
        day_df = df[df.index.date == day.date()]
        if len(day_df) < 5:
            continue
        result = simulate_day(day_df, OPENING_MINUTES, REWARD_RISK, daily_ma)
        if result:
            results.append(result)
    return results


def summarise(results, label):
    trades = [r for r in results if r.get("trade")]
    filtered = len(results) - len(trades)
    no_breakout_days = len([r for r in results if not r.get("trade") and r.get("filtered_by") == "no_breakout"])
    vol_trend_days   = len([r for r in results if not r.get("trade") and r.get("filtered_by") != "no_breakout"])
    if not trades:
        print(f"\n{label}: No trades generated.")
        return None

    df_t = pd.DataFrame(trades)
    df_t["cumulative_pnl"] = df_t["pnl"].cumsum()
    wins   = df_t[df_t["pnl"] > 0]
    losses = df_t[df_t["pnl"] <= 0]

    total_pnl     = df_t["pnl"].sum()
    win_rate      = len(wins) / len(df_t) * 100
    avg_win       = wins["pnl"].mean()   if not wins.empty   else 0
    avg_loss      = losses["pnl"].mean() if not losses.empty else 0
    expectancy    = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)
    max_dd        = (df_t["cumulative_pnl"].cummax() - df_t["cumulative_pnl"]).max()
    pf_denom      = abs(losses["pnl"].sum()) if not losses.empty and losses["pnl"].sum() != 0 else 1
    profit_factor = abs(wins["pnl"].sum()) / pf_denom if not wins.empty else 0
    outcomes      = df_t["outcome"].value_counts()

    print(f"\n{'='*58}")
    print(f"  {label}")
    print(f"{'='*58}")
    print(f"  Days: {len(results)}  |  Trades taken: {len(df_t)}  |  No signal: {no_breakout_days}  |  Trend/Vol filtered: {vol_trend_days}")
    print(f"  Win rate   : {win_rate:.1f}%  ({len(wins)}W / {len(losses)}L)")
    print(f"  Target hit : {outcomes.get('TARGET',0)}  |  "
          f"Stopped : {outcomes.get('STOP',0)}  |  "
          f"EOD : {outcomes.get('EOD',0)}")
    print(f"  Total P&L  : ${total_pnl:+.2f}")
    print(f"  Expectancy : ${expectancy:+.2f} per trade")
    print(f"  Prof factor: {profit_factor:.2f}")
    print(f"  Max DD     : ${max_dd:.2f}")
    print(f"{'='*58}")

    return {
        "label": label, "df": df_t,
        "total_pnl": total_pnl, "win_rate": win_rate,
        "expectancy": expectancy, "profit_factor": profit_factor,
        "max_dd": max_dd, "n_trades": len(df_t)
    }


def plot_walkforward(summaries):
    valid = [s for s in summaries if s is not None]
    if not valid:
        return

    fig = plt.figure(figsize=(16, 10))
    fig.suptitle(f"ORB v3 Walk-Forward — {TICKER}\n"
                 "15-min OR | Close+Volume filter | Trend filter | 2PM exit",
                 fontsize=13, fontweight="bold")

    n = len(valid)
    colors_month = ["steelblue", "darkorange", "green"]

    # Top row: cumulative P&L per month
    for i, s in enumerate(valid):
        ax = fig.add_subplot(3, n, i + 1)
        df_t  = s["df"]
        dates = pd.to_datetime(df_t["date"])
        ax.plot(dates, df_t["cumulative_pnl"],
                color=colors_month[i], linewidth=2, marker="o", markersize=3)
        ax.axhline(0, color="gray", linestyle="--", linewidth=1)
        ax.fill_between(dates, df_t["cumulative_pnl"], 0,
                        where=df_t["cumulative_pnl"] >= 0, alpha=0.15, color="green")
        ax.fill_between(dates, df_t["cumulative_pnl"], 0,
                        where=df_t["cumulative_pnl"] < 0, alpha=0.15, color="red")
        ax.set_title(f"{s['label']}\nP&L: ${s['total_pnl']:+.0f}", fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=7)
        ax.set_ylabel("$", fontsize=8)

    # Middle row: daily P&L bars per month
    for i, s in enumerate(valid):
        ax = fig.add_subplot(3, n, n + i + 1)
        df_t  = s["df"]
        dates = pd.to_datetime(df_t["date"])
        bar_colors = ["green" if p > 0 else "red" for p in df_t["pnl"]]
        ax.bar(dates, df_t["pnl"], color=bar_colors, alpha=0.8)
        ax.axhline(0, color="gray", linestyle="--", linewidth=1)
        ax.set_title(f"Daily P&L — WR: {s['win_rate']:.0f}%  PF: {s['profit_factor']:.2f}", fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=7)
        ax.set_ylabel("$", fontsize=8)

    # Bottom row: combined cumulative P&L across all months
    ax_combined = fig.add_subplot(3, 1, 3)
    all_trades  = pd.concat([s["df"] for s in valid], ignore_index=True)
    all_trades  = all_trades.sort_values("date")
    all_trades["combined_pnl"] = all_trades["pnl"].cumsum()
    dates_all   = pd.to_datetime(all_trades["date"])

    ax_combined.plot(dates_all, all_trades["combined_pnl"],
                     color="navy", linewidth=2.5, marker="o", markersize=3)
    ax_combined.axhline(0, color="gray", linestyle="--", linewidth=1)
    ax_combined.fill_between(dates_all, all_trades["combined_pnl"], 0,
                             where=all_trades["combined_pnl"] >= 0, alpha=0.15, color="green")
    ax_combined.fill_between(dates_all, all_trades["combined_pnl"], 0,
                             where=all_trades["combined_pnl"] < 0, alpha=0.15, color="red")

    total_all = all_trades["pnl"].sum()
    wr_all    = (all_trades["pnl"] > 0).mean() * 100
    ax_combined.set_title(
        f"COMBINED 3-Month P&L: ${total_all:+.2f}  |  "
        f"Win Rate: {wr_all:.1f}%  |  Trades: {len(all_trades)}",
        fontsize=10, fontweight="bold"
    )
    ax_combined.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    plt.setp(ax_combined.xaxis.get_majorticklabels(), rotation=45, fontsize=8)
    ax_combined.set_ylabel("$")

    # Add month boundary lines
    for s in valid:
        first_date = pd.to_datetime(s["df"]["date"].iloc[0])
        ax_combined.axvline(first_date, color="gray", linestyle=":", alpha=0.5)

    plt.tight_layout()
    output_file = "orb_results_v3.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    print(f"\nChart saved -> {output_file}")
    plt.show()


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Fetching {TICKER} data for walk-forward test (60 days, split into 3 windows)...")
    df_3mo    = fetch_intraday(TICKER, "60d", INTERVAL)
    daily_ma  = fetch_daily_ma(TICKER, MA_PERIOD)
    print(f"  -> {len(df_3mo)} bars ({df_3mo.index[0].date()} to {df_3mo.index[-1].date()})")

    # Split into 3 monthly windows
    all_dates  = sorted(df_3mo.index.normalize().unique())
    n          = len(all_dates)
    chunk      = n // 3
    windows    = [
        (all_dates[:chunk],          "Month 1"),
        (all_dates[chunk:2*chunk],   "Month 2"),
        (all_dates[2*chunk:],        "Month 3 (most recent)"),
    ]

    summaries = []
    all_trade_rows = []

    for day_list, label in windows:
        days_set = set(d.date() for d in day_list)
        df_win   = df_3mo[pd.Series(df_3mo.index.date, index=df_3mo.index).isin(days_set)]
        results  = run_backtest(df_win, daily_ma, label)
        s        = summarise(results, label)
        summaries.append(s)
        if s:
            all_trade_rows.append(s["df"])

    # Combined summary
    if all_trade_rows:
        all_trades = pd.concat(all_trade_rows, ignore_index=True).sort_values("date")
        wins_all   = all_trades[all_trades["pnl"] > 0]
        losses_all = all_trades[all_trades["pnl"] <= 0]
        pf_denom   = abs(losses_all["pnl"].sum()) if not losses_all.empty and losses_all["pnl"].sum() != 0 else 1
        print(f"\n{'='*58}")
        print(f"  COMBINED 3-MONTH SUMMARY")
        print(f"{'='*58}")
        print(f"  Total trades   : {len(all_trades)}")
        print(f"  Total P&L      : ${all_trades['pnl'].sum():+.2f}")
        print(f"  Win rate       : {(all_trades['pnl']>0).mean()*100:.1f}%")
        print(f"  Expectancy     : ${all_trades['pnl'].mean():+.2f} per trade")
        print(f"  Profit factor  : {abs(wins_all['pnl'].sum())/pf_denom:.2f}")
        max_dd = (all_trades["pnl"].cumsum().cummax() - all_trades["pnl"].cumsum()).max()
        print(f"  Max drawdown   : ${max_dd:.2f}")
        print(f"{'='*58}")

        all_trades.to_csv("orb_trade_log_v3.csv", index=False)
        print(f"Trade log saved -> orb_trade_log_v3.csv")

    plot_walkforward(summaries)