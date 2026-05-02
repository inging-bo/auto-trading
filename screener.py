import logging
from kis_client import KisClient

logger = logging.getLogger(__name__)


class Screener:
    """
    종목 스크리너.
    - 감시 목록 모드: config의 watchlist에서 조건 필터링
    - 동적 탐색 모드: 거래량 상위 종목에서 조건 필터링
    """

    def __init__(self, client: KisClient, config: dict):
        self.client = client
        self.config = config

    def run(self) -> list[str]:
        cfg = self.config.get("screener", {})
        min_volume: int = cfg.get("min_volume", 500000)
        min_price: int = cfg.get("min_price", 5000)
        max_price: int = cfg.get("max_price", 200000)
        max_stocks: int = cfg.get("max_stocks", 5)
        use_dynamic: bool = self.config.get("use_dynamic_universe", False)

        if use_dynamic:
            candidates = self._get_dynamic_candidates(cfg)
        else:
            candidates = self._get_watchlist_candidates(cfg)

        passed = []
        for c in candidates:
            symbol = c["symbol"]
            price = c["price"]
            volume = c["volume"]

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

        mode = "동적 탐색" if use_dynamic else "감시 목록"
        logger.info(f"스크리너 결과 ({mode}): {len(passed)}개 선택 → {passed}")
        return passed

    def _get_dynamic_candidates(self, cfg: dict) -> list[dict]:
        min_universe_vol: int = cfg.get("min_universe_volume", 100000)
        logger.info(f"전체 시장 탐색 중 (거래량 상위 종목)...")
        universe = self.client.get_universe(min_vol=min_universe_vol)
        if not universe:
            logger.warning("유니버스 조회 실패. 감시 목록으로 대체합니다.")
            return self._get_watchlist_candidates(cfg)
        return universe

    def _get_watchlist_candidates(self, cfg: dict) -> list[dict]:
        watchlist: list[str] = cfg.get("watchlist", [])
        if not watchlist:
            logger.warning("watchlist가 비어 있습니다. config.yaml을 확인하세요.")
            return []

        logger.info(f"감시 목록 검사 중 ({len(watchlist)}개 종목)...")
        candidates = []
        for symbol in watchlist:
            quote = self.client.get_quote(symbol)
            if not quote:
                continue
            candidates.append({
                "symbol": symbol,
                "price": quote["price"],
                "volume": quote["volume"],
            })
        return candidates
