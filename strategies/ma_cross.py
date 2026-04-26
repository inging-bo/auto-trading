import logging
import pandas as pd
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class MACrossStrategy(BaseStrategy):
    """
    이동평균 크로스오버 전략
    - 단기 이평선이 장기 이평선을 위로 돌파 → 매수 (골든크로스)
    - 단기 이평선이 장기 이평선을 아래로 돌파 → 매도 (데드크로스)
    """

    @property
    def name(self) -> str:
        return "이동평균 크로스"

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> str:
        short = self.config.get("short_period", 5)
        long = self.config.get("long_period", 20)

        if not self._validate_df(df, long + 2):
            logger.warning(f"[{symbol}] 데이터 부족")
            return "HOLD"

        df = df.copy()
        df["ma_short"] = df["close"].rolling(short).mean()
        df["ma_long"] = df["close"].rolling(long).mean()

        prev_short = df["ma_short"].iloc[-2]
        prev_long = df["ma_long"].iloc[-2]
        curr_short = df["ma_short"].iloc[-1]
        curr_long = df["ma_long"].iloc[-1]

        if prev_short <= prev_long and curr_short > curr_long:
            logger.info(f"[{symbol}] 골든크로스 → BUY")
            return "BUY"
        elif prev_short >= prev_long and curr_short < curr_long:
            logger.info(f"[{symbol}] 데드크로스 → SELL")
            return "SELL"

        return "HOLD"
