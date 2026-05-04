"""
전략별 백테스트 엔진.
일봉 OHLCV DataFrame을 받아 각 봉마다 시뮬레이션하고 성과 지표를 반환합니다.
매매 체결은 신호 발생 봉의 종가 기준이며, 1회 매수는 초기자본 전액 사용을 가정합니다.
"""
import logging
import pandas as pd
from strategies import STRATEGY_MAP, load_strategy

logger = logging.getLogger(__name__)

STRATEGY_LABELS: dict[str, str] = {
    "rsi":                "RSI",
    "ma_cross":           "이동평균 크로스",
    "bollinger":          "볼린저밴드",
    "volatility_breakout":"변동성 돌파",
}


def _min_rows(strategy_name: str, s_cfg: dict) -> int:
    if strategy_name == "rsi":
        return s_cfg.get("period", 14) + 2
    if strategy_name == "ma_cross":
        return s_cfg.get("long_period", 20) + 2
    if strategy_name == "bollinger":
        return s_cfg.get("period", 20) + 2
    return 3  # volatility_breakout


def run_backtest(df: pd.DataFrame, strategy_name: str,
                 config: dict, symbol: str = "_") -> dict:
    """단일 전략 백테스트를 실행하고 성과 지표 dict를 반환합니다."""
    s_cfg     = config.get(strategy_name, {})
    strategy  = load_strategy(strategy_name, config)
    min_r     = _min_rows(strategy_name, s_cfg)

    initial   = 10_000_000.0
    cash      = initial
    position  = 0
    buy_price = 0.0
    trades: list[float] = []   # 거래별 수익률(%)
    equity: list[float] = []   # 봉별 평가액

    close = df["close"].astype(float).values

    for i in range(min_r, len(df)):
        window = df.iloc[: i + 1]
        signal = strategy.generate_signal(symbol, window)
        price  = close[i]

        if signal == "BUY" and position == 0:
            qty = int(cash / price)
            if qty > 0:
                position  = qty
                buy_price = price
                cash     -= qty * price

        elif signal == "SELL" and position > 0:
            cash += position * price
            trades.append((price - buy_price) / buy_price * 100)
            position = 0

        equity.append(cash + position * price)

    # 기간 종료 시 미청산 포지션 강제 정리
    if position > 0:
        last = close[-1]
        cash += position * last
        trades.append((last - buy_price) / buy_price * 100)

    total_return = (cash - initial) / initial * 100
    n            = len(trades)
    win_rate     = sum(1 for t in trades if t > 0) / n * 100 if n else 0.0
    avg_profit   = sum(trades) / n if n else 0.0

    if equity:
        s   = pd.Series(equity)
        mdd = float(((s - s.cummax()) / s.cummax()).min() * 100)
    else:
        mdd = 0.0

    return {
        "strategy":     strategy_name,
        "label":        STRATEGY_LABELS.get(strategy_name, strategy_name),
        "total_return": round(total_return, 2),
        "num_trades":   n,
        "win_rate":     round(win_rate, 1),
        "avg_profit":   round(avg_profit, 2),
        "max_drawdown": round(mdd, 2),
    }


def run_all_backtests(df: pd.DataFrame, config: dict,
                      symbol: str = "_") -> list[dict]:
    """4개 전략 전체를 백테스트하고 결과 목록을 반환합니다."""
    results = []
    for name in STRATEGY_MAP:
        try:
            results.append(run_backtest(df, name, config, symbol))
        except Exception as e:
            logger.warning(f"백테스트 실패 ({name}): {e}")
            results.append({
                "strategy": name, "label": STRATEGY_LABELS.get(name, name),
                "total_return": 0, "num_trades": 0, "win_rate": 0,
                "avg_profit": 0, "max_drawdown": 0, "error": str(e),
            })
    return results
