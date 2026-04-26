import logging
import pandas as pd
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class BollingerStrategy(BaseStrategy):
    """
    볼린저밴드 전략
    - 주가가 하단 밴드 아래에서 회복 → 매수
    - 주가가 상단 밴드 위에서 하락 → 매도
    """

    @property
    def name(self) -> str:
        return "볼린저밴드"

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> str:
        period = self.config.get("period", 20)
        std_dev = self.config.get("std_dev", 2.0)

        if not self._validate_df(df, period + 2):
            logger.warning(f"[{symbol}] 데이터 부족")
            return "HOLD"

        df = df.copy()
        df["ma"] = df["close"].rolling(period).mean()
        df["std"] = df["close"].rolling(period).std()
        df["upper"] = df["ma"] + std_dev * df["std"]
        df["lower"] = df["ma"] - std_dev * df["std"]

        prev_close = df["close"].iloc[-2]
        curr_close = df["close"].iloc[-1]
        prev_lower = df["lower"].iloc[-2]
        curr_lower = df["lower"].iloc[-1]
        prev_upper = df["upper"].iloc[-2]
        curr_upper = df["upper"].iloc[-1]

        logger.debug(
            f"[{symbol}] 현재가 {curr_close:,} | 상단 {curr_upper:,.0f} | 하단 {curr_lower:,.0f}"
        )

        # 하단 밴드 이탈 후 회복
        if prev_close < prev_lower and curr_close >= curr_lower:
            logger.info(f"[{symbol}] 하단밴드 회복 → BUY")
            return "BUY"
        # 상단 밴드 이탈 후 하락
        elif prev_close > prev_upper and curr_close <= curr_upper:
            logger.info(f"[{symbol}] 상단밴드 이탈 → SELL")
            return "SELL"

        return "HOLD"
