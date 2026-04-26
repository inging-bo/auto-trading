import logging
from kis_client import KisClient

logger = logging.getLogger(__name__)


class Screener:
    """
    watchlist에서 거래량/가격 조건을 만족하는 종목을 필터링합니다.
    """

    def __init__(self, client: KisClient, config: dict):
        self.client = client
        self.config = config

    def run(self) -> list[str]:
        cfg = self.config.get("screener", {})
        watchlist: list[str] = cfg.get("watchlist", [])
        min_volume: int = cfg.get("min_volume", 500000)
        min_price: int = cfg.get("min_price", 5000)
        max_price: int = cfg.get("max_price", 200000)
        max_stocks: int = cfg.get("max_stocks", 5)

        if not watchlist:
            logger.warning("watchlist가 비어 있습니다. config.yaml을 확인하세요.")
            return []

        logger.info(f"스크리너 실행 중 ({len(watchlist)}개 종목 검사)...")
        passed = []

        for symbol in watchlist:
            quote = self.client.get_quote(symbol)
            if not quote:
                continue

            price = quote["price"]
            volume = quote["volume"]

            if volume < min_volume:
                logger.debug(f"[{symbol}] 제외 - 거래량 부족 ({volume:,} < {min_volume:,})")
                continue
            if not (min_price <= price <= max_price):
                logger.debug(f"[{symbol}] 제외 - 가격 범위 초과 ({price:,}원)")
                continue

            logger.info(f"[{symbol}] 통과 - 현재가 {price:,}원, 거래량 {volume:,}")
            passed.append(symbol)

            if len(passed) >= max_stocks:
                break

        logger.info(f"스크리너 결과: {len(passed)}개 종목 선택 → {passed}")
        return passed
