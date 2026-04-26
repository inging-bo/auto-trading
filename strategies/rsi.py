import logging
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class RSIStrategy(BaseStrategy):
    """
    RSI (상대강도지수) 전략
    - RSI < oversold(30) → 매수 (과매도 구간)
    - RSI > overbought(70) → 매도 (과매수 구간)
    """

    @property
    def name(self) -> str:
        return "RSI"

    def _calc_rsi(self, series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> str:
        period = self.config.get("period", 14)
        oversold = self.config.get("oversold", 30)
        overbought = self.config.get("overbought", 70)

        if not self._validate_df(df, period + 2):
            logger.warning(f"[{symbol}] 데이터 부족")
            return "HOLD"

        df = df.copy()
        df["rsi"] = self._calc_rsi(df["close"], period)

        rsi_prev = df["rsi"].iloc[-2]
        rsi_curr = df["rsi"].iloc[-1]

        logger.debug(f"[{symbol}] RSI: {rsi_curr:.1f}")

        # 과매도 구간 진입 후 반등 확인
        if rsi_prev < oversold and rsi_curr >= oversold:
            logger.info(f"[{symbol}] RSI 과매도 반등 {rsi_curr:.1f} → BUY")
            return "BUY"
        # 과매수 구간 진입 후 하락 확인
        elif rsi_prev > overbought and rsi_curr <= overbought:
            logger.info(f"[{symbol}] RSI 과매수 하락 {rsi_curr:.1f} → SELL")
            return "SELL"

        return "HOLD"
