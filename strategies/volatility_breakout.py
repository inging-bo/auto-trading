import logging
import pandas as pd
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class VolatilityBreakoutStrategy(BaseStrategy):
    """
    변동성 돌파 전략 (래리 윌리엄스)
    - 매수가 = 당일 시가 + (전일 고가 - 전일 저가) × k
    - 현재가가 매수가 돌파 시 → 매수
    - 장 마감 전 신호 없으면 보유 중인 경우 → 매도
    """

    @property
    def name(self) -> str:
        return "변동성 돌파"

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> str:
        k = self.config.get("k", 0.5)

        if not self._validate_df(df, 3):
            logger.warning(f"[{symbol}] 데이터 부족")
            return "HOLD"

        df = df.copy()

        # 전일 데이터 (일봉 기준으로 마지막 완성된 봉)
        prev_high = df["high"].iloc[-2]
        prev_low = df["low"].iloc[-2]
        today_open = df["open"].iloc[-1]
        today_close = df["close"].iloc[-1]

        range_ = prev_high - prev_low
        buy_target = today_open + range_ * k

        logger.debug(
            f"[{symbol}] 매수목표가 {buy_target:,.0f} | 현재가 {today_close:,.0f}"
        )

        if today_close >= buy_target:
            logger.info(f"[{symbol}] 변동성 돌파 {today_close:,} >= {buy_target:,.0f} → BUY")
            return "BUY"

        return "HOLD"
