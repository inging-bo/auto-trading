import json
import logging
import os

from kis_client import KisClient, parse_us_ticker

logger = logging.getLogger(__name__)

EXCLUDED_FILE = "excluded.json"


def load_excluded() -> set[str]:
    try:
        with open(EXCLUDED_FILE, encoding="utf-8") as f:
            return {s.upper() for s in json.load(f)}
    except Exception:
        return set()


class Screener:
    """
    종목 스크리너.
    - KR: 감시 목록 또는 동적 유니버스(거래량 상위)
    - US: 감시 목록(us_screener.watchlist) 고정
    반환값: [{"symbol": str, "market": str}, ...]  (market = "KRX" | "NASDAQ" | ...)
    """

    def __init__(self, client: KisClient, config: dict):
        self.client = client
        self.config = config

    def run(self, active_markets: list[str] | None = None) -> list[dict]:
        """
        active_markets: ['KR'], ['US'], ['KR','US'], None(config 기준)
        """
        market_config = self.config.get("market", "KR")
        run_kr = ("KR" in (active_markets or [])) if active_markets is not None \
            else market_config in ("KR", "BOTH")
        run_us = ("US" in (active_markets or [])) if active_markets is not None \
            else market_config in ("US", "BOTH")

        results: list[dict] = []

        if run_kr:
            results.extend(self._run_kr())
        if run_us:
            results.extend(self._run_us())

        if results:
            summary = [f"{r['symbol']}({r['market']})" for r in results]
            logger.info(f"스크리너 최종 선택: {summary}")
        return results

    # ── 한국 주식 ────────────────────────────────────────────
    def _run_kr(self) -> list[dict]:
        cfg = self.config.get("screener", {})
        min_volume: int = cfg.get("min_volume", 500000)
        min_price: int = cfg.get("min_price", 5000)
        max_price: int = cfg.get("max_price", 200000)
        max_stocks: int = cfg.get("max_stocks", 5)
        use_dynamic: bool = self.config.get("use_dynamic_universe", False)

        if use_dynamic:
            candidates = self._get_dynamic_candidates(cfg)
        else:
            candidates = self._get_kr_watchlist_candidates(cfg)

        excluded = load_excluded()
        passed: list[dict] = []
        for c in candidates:
            if c["symbol"].upper() in excluded:
                logger.info(f"[{c['symbol']}] KR 제외 종목 - 스킵")
                continue
            if c["volume"] < min_volume:
                logger.debug(f"[{c['symbol']}] KR 제외 - 거래량 부족 ({c['volume']:,})")
                continue
            if not (min_price <= c["price"] <= max_price):
                logger.debug(f"[{c['symbol']}] KR 제외 - 가격 범위 초과 ({c['price']:,}원)")
                continue
            logger.info(f"[{c['symbol']}] KR 통과 - {c['price']:,}원, 거래량 {c['volume']:,}")
            passed.append({"symbol": c["symbol"], "market": "KRX"})
            if len(passed) >= max_stocks:
                break

        logger.info(f"KR 스크리너: {len(passed)}개 선택")
        return passed

    def _get_kr_watchlist_candidates(self, cfg: dict) -> list[dict]:
        watchlist: list[str] = cfg.get("watchlist", [])
        if not watchlist:
            logger.warning("watchlist가 비어 있습니다.")
            return []
        logger.info(f"KR 감시 목록 검사 중 ({len(watchlist)}개)...")
        candidates = []
        for symbol in watchlist:
            quote = self.client.get_quote(symbol, market="KRX")
            if quote:
                candidates.append({"symbol": symbol,
                                   "price": quote["price"],
                                   "volume": quote["volume"]})
        return candidates

    def _get_dynamic_candidates(self, cfg: dict) -> list[dict]:
        min_vol: int = cfg.get("min_universe_volume", 100000)
        logger.info("전체 시장 탐색 중 (KR 거래량 상위)...")
        universe = self.client.get_universe(min_vol=min_vol)
        if not universe:
            logger.warning("유니버스 조회 실패. KR 감시 목록으로 대체합니다.")
            return self._get_kr_watchlist_candidates(cfg)
        return universe

    # ── 미국 주식 ────────────────────────────────────────────
    def _run_us(self) -> list[dict]:
        us_cfg      = self.config.get("us_screener", {})
        min_volume  = us_cfg.get("min_volume", 1_000_000)
        max_stocks  = us_cfg.get("max_stocks", 3)
        use_dynamic = self.config.get("use_dynamic_universe_us", False)

        excluded = load_excluded()

        if use_dynamic:
            candidates = self._get_us_dynamic_candidates(us_cfg)
        else:
            candidates = self._get_us_watchlist_candidates(us_cfg)

        if not candidates:
            return []

        passed: list[dict] = []
        for c in candidates:
            sym      = c["symbol"].upper()
            exchange = c.get("exchange", c.get("market", "NASDAQ"))
            if sym in excluded:
                logger.info(f"[{sym}] US 제외 종목 - 스킵")
                continue
            if c.get("volume", 0) < min_volume:
                logger.debug(f"[{sym}] US 제외 - 거래량 부족 ({c.get('volume', 0):,})")
                continue
            logger.info(f"[{sym}] US 통과 - ${c.get('price', 0):.2f}, 거래량 {c.get('volume', 0):,}")
            passed.append({"symbol": sym, "market": exchange})
            if len(passed) >= max_stocks:
                break

        logger.info(f"US 스크리너: {len(passed)}개 선택")
        return passed

    def _get_us_watchlist_candidates(self, us_cfg: dict) -> list[dict]:
        watchlist: list = us_cfg.get("watchlist", [])
        if not watchlist:
            logger.warning("US watchlist가 비어 있습니다.")
            return []
        logger.info(f"US 감시 목록 검사 중 ({len(watchlist)}개)...")
        candidates = []
        for item in watchlist:
            symbol, exchange = parse_us_ticker(str(item))
            if not symbol:
                continue
            quote = self.client.get_quote(symbol, market=exchange)
            if quote:
                candidates.append({"symbol": symbol, "exchange": exchange,
                                   "price": quote["price"], "volume": quote["volume"]})
        return candidates

    def _get_us_dynamic_candidates(self, us_cfg: dict) -> list[dict]:
        min_vol = us_cfg.get("min_universe_volume", 500_000)
        logger.info("전체 시장 탐색 중 (US 거래량 상위)...")
        universe = self.client.get_us_universe(min_vol=min_vol)
        if not universe:
            logger.warning("US 유니버스 조회 실패. US 감시 목록으로 대체합니다.")
            return self._get_us_watchlist_candidates(us_cfg)
        return universe
