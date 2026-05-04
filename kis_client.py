import os
import logging
from dotenv import load_dotenv
import pandas as pd
from pykis import PyKis, KisStock, KisOrder

load_dotenv()
logger = logging.getLogger(__name__)

# 거래소 단축코드 → PyKis market 문자열
EXCHANGE_CODE_MAP: dict[str, str] = {
    "NASD": "NASDAQ",
    "NYSE": "NYSE",
    "AMEX": "AMEX",
}


def parse_us_ticker(ticker: str) -> tuple[str, str]:
    """'AAPL.NASD' → ('AAPL', 'NASDAQ')"""
    parts = ticker.upper().split(".", 1)
    symbol = parts[0]
    exchange = EXCHANGE_CODE_MAP.get(parts[1] if len(parts) > 1 else "NASD", "NASDAQ")
    return symbol, exchange


class KisClient:
    def __init__(self, virtual: bool = False):
        self.virtual = virtual
        self._kis: PyKis = None

    def connect(self):
        required = ["KIS_ID", "KIS_ACCOUNT", "KIS_APPKEY", "KIS_SECRETKEY"]
        for key in required:
            if not os.getenv(key):
                raise EnvironmentError(f".env 파일에 {key}가 없습니다.")

        kwargs = dict(
            id=os.getenv("KIS_ID"),
            account=os.getenv("KIS_ACCOUNT"),
            appkey=os.getenv("KIS_APPKEY"),
            secretkey=os.getenv("KIS_SECRETKEY"),
            keep_token=True,
        )

        if self.virtual:
            for key in ["KIS_VIRTUAL_APPKEY", "KIS_VIRTUAL_SECRETKEY"]:
                if not os.getenv(key):
                    raise EnvironmentError(f"모의투자 사용 시 .env 파일에 {key}가 필요합니다.")
            kwargs["virtual_id"] = os.getenv("KIS_ID")
            kwargs["virtual_appkey"] = os.getenv("KIS_VIRTUAL_APPKEY")
            kwargs["virtual_secretkey"] = os.getenv("KIS_VIRTUAL_SECRETKEY")

        self._kis = PyKis(**kwargs)
        mode = "모의투자" if self.virtual else "실전투자"
        logger.info(f"KIS API 연결 완료 ({mode})")

    def _check_connected(self):
        if self._kis is None:
            raise RuntimeError("connect()를 먼저 호출하세요.")

    def stock(self, symbol: str) -> KisStock:
        self._check_connected()
        return self._kis.stock(symbol)

    def get_chart(self, symbol: str, market: str = "KRX",
                  days: str = "60d", interval: int | str = 5) -> pd.DataFrame:
        """종목 차트 데이터를 DataFrame으로 반환합니다.
        market: 'KRX' | 'NASDAQ' | 'NYSE' | 'AMEX'
        interval: 분봉 단위(KR) 또는 'day'(일봉)
        """
        self._check_connected()
        try:
            s = self._kis.stock(symbol, market=market)
            chart = s.chart(days, period=interval)
            df = chart.df()
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            logger.warning(f"[{symbol}] 차트 조회 실패: {e}")
            return pd.DataFrame()

    def get_quote(self, symbol: str, market: str = "KRX") -> dict:
        """현재가, 거래량 등 시세 정보를 반환합니다.
        market: 'KRX' | 'NASDAQ' | 'NYSE' | 'AMEX'
        """
        self._check_connected()
        try:
            q = self._kis.stock(symbol, market=market).quote()
            return {
                "symbol": symbol,
                "market": market,
                "price": float(q.price),
                "volume": int(q.volume) if hasattr(q, "volume") and q.volume else 0,
                "open": float(q.open) if hasattr(q, "open") else float(q.price),
                "high": float(q.high) if hasattr(q, "high") else float(q.price),
                "low": float(q.low) if hasattr(q, "low") else float(q.price),
                "prev_price": float(q.prev_price) if hasattr(q, "prev_price") else float(q.price),
                "market_cap": int(q.market_cap) if hasattr(q, "market_cap") and q.market_cap else 0,
            }
        except Exception as e:
            logger.warning(f"[{symbol}] 시세 조회 실패: {e}")
            return {}

    # ── 미국 주식 폴백 유니버스 (KIS API 실패 시 사용) ───────────
    _US_FALLBACK: list[tuple[str, str]] = [
        # (symbol, exchange)
        ("AAPL","NASDAQ"), ("MSFT","NASDAQ"), ("NVDA","NASDAQ"), ("GOOGL","NASDAQ"),
        ("META","NASDAQ"), ("AMZN","NASDAQ"), ("TSLA","NASDAQ"), ("AVGO","NASDAQ"),
        ("COST","NASDAQ"), ("NFLX","NASDAQ"), ("AMD","NASDAQ"),  ("ADBE","NASDAQ"),
        ("CSCO","NASDAQ"), ("QCOM","NASDAQ"), ("INTU","NASDAQ"), ("TXN","NASDAQ"),
        ("AMGN","NASDAQ"), ("SBUX","NASDAQ"), ("INTC","NASDAQ"), ("MU","NASDAQ"),
        ("PANW","NASDAQ"), ("KLAC","NASDAQ"), ("LRCX","NASDAQ"), ("MRVL","NASDAQ"),
        ("SNPS","NASDAQ"), ("CDNS","NASDAQ"), ("ADI","NASDAQ"),  ("REGN","NASDAQ"),
        ("GILD","NASDAQ"), ("VRTX","NASDAQ"),
        ("JPM","NYSE"),   ("V","NYSE"),     ("WMT","NYSE"),   ("MA","NYSE"),
        ("PG","NYSE"),    ("HD","NYSE"),    ("XOM","NYSE"),   ("JNJ","NYSE"),
        ("UNH","NYSE"),   ("CVX","NYSE"),   ("MRK","NYSE"),   ("LLY","NYSE"),
        ("ABBV","NYSE"),  ("KO","NYSE"),    ("PEP","NYSE"),   ("TMO","NYSE"),
        ("ACN","NYSE"),   ("MCD","NYSE"),   ("NKE","NYSE"),   ("WFC","NYSE"),
        ("GS","NYSE"),    ("MS","NYSE"),    ("BLK","NYSE"),   ("IBM","NYSE"),
        ("BA","NYSE"),    ("CAT","NYSE"),   ("UNP","NYSE"),   ("NEE","NYSE"),
    ]

    def get_us_universe(self, exchanges: list[str] | None = None,
                        min_vol: int = 1_000_000) -> list[dict]:
        """해외주식 거래량 상위 유니버스를 반환합니다.
        KIS 조건검색 API 호출 후 실패 시 내장 폴백 목록으로 시세를 조회합니다.
        """
        self._check_connected()
        exchanges = exchanges or ["NASDAQ", "NYSE"]
        candidates: list[dict] = []

        # KIS 해외주식 조건검색 API 시도
        excd_map = {"NASDAQ": "NAS", "NYSE": "NYS", "AMEX": "AMS"}
        for exchange in exchanges:
            excd = excd_map.get(exchange, "NAS")
            try:
                result = self._kis.fetch(
                    "/uapi/overseas-price/v1/quotations/inquire-search",
                    api="HHDFS76200200",
                    params={
                        "AUTH": "",
                        "EXCD": excd,
                        "CO_YN_PRICECUR": "",
                        "CO_ST_PRICECUR": "",
                        "CO_EN_PRICECUR": "",
                        "CO_YN_RATE": "",
                        "CO_ST_RATE": "",
                        "CO_EN_RATE": "",
                        "CO_YN_VALX": "",
                        "CO_ST_VALX": "",
                        "CO_EN_VALX": "",
                        "CO_YN_SHAR": "",
                        "CO_ST_SHAR": "",
                        "CO_EN_SHAR": "",
                        "CO_YN_VOLUME": "1",
                        "CO_ST_VOLUME": str(min_vol),
                        "CO_EN_VOLUME": "",
                        "CO_YN_AMT": "",
                        "CO_ST_AMT": "",
                        "CO_EN_AMT": "",
                        "CO_YN_EPS": "",
                        "CO_ST_EPS": "",
                        "CO_EN_EPS": "",
                        "CO_YN_PER": "",
                        "CO_ST_PER": "",
                        "CO_EN_PER": "",
                        "KEYB": "",
                    },
                )
                rows = result.get("output2") or []
                for row in rows:
                    sym = str(row.get("symb", "")).strip()
                    if not sym:
                        continue
                    candidates.append({
                        "symbol": sym,
                        "exchange": exchange,
                        "price": float(row.get("last", 0) or 0),
                        "volume": int(row.get("tvol", 0) or 0),
                    })
                logger.info(f"US 유니버스 조회 완료 ({exchange}): {len(rows)}개")
            except Exception as e:
                logger.warning(f"US 유니버스 API 실패 ({exchange}): {e}")

        if candidates:
            return candidates

        # 폴백: 내장 목록에서 시세 조회
        logger.info("US 유니버스 폴백 목록으로 시세 조회 중...")
        filtered_fallback = [
            (sym, ex) for sym, ex in self._US_FALLBACK if ex in exchanges
        ]
        for sym, exchange in filtered_fallback:
            quote = self.get_quote(sym, market=exchange)
            if quote:
                candidates.append({
                    "symbol": sym,
                    "exchange": exchange,
                    "price": quote["price"],
                    "volume": quote["volume"],
                })
        return candidates

    def get_universe(self, min_vol: int = 100000) -> list[dict]:
        """거래량 상위 종목 유니버스를 반환합니다."""
        self._check_connected()
        try:
            result = self._kis.fetch(
                "/uapi/domestic-stock/v1/ranking/volume",
                api="FHPST01710000",
                params={
                    "fid_cond_mrkt_div_code": "J",
                    "fid_cond_scr_div_code": "20171",
                    "fid_input_iscd": "0000",
                    "fid_div_cls_code": "0",
                    "fid_blng_cls_code": "0",
                    "fid_trgt_cls_code": "111111111",
                    "fid_trgt_exls_cls_code": "000000",
                    "fid_input_price_1": "",
                    "fid_input_price_2": "",
                    "fid_vol_cnt": str(min_vol) if min_vol else "",
                    "fid_input_date_1": "",
                },
            )
            rows = result.get("output", []) or []
            universe = []
            for s in rows:
                symbol = str(s.get("mksc_shrn_iscd", "")).strip()
                if not symbol:
                    continue
                universe.append({
                    "symbol": symbol,
                    "name": str(s.get("hts_kor_isnm", "")).strip(),
                    "price": float(s.get("stck_prpr", 0) or 0),
                    "volume": int(s.get("acml_vol", 0) or 0),
                })
            logger.info(f"유니버스 조회 완료: {len(universe)}개 종목")
            return universe
        except Exception as e:
            logger.warning(f"유니버스 조회 실패: {e}")
            return []

    def buy(self, symbol: str, qty: int, market: str = "KRX") -> KisOrder | None:
        """시장가 매수 주문을 실행합니다."""
        self._check_connected()
        try:
            s = self._kis.stock(symbol, market=market)
            order = s.buy(qty=qty)
            logger.info(f"[{symbol}] 매수 주문 완료 - {qty}주")
            return order
        except Exception as e:
            logger.error(f"[{symbol}] 매수 주문 실패: {e}")
            return None

    def sell(self, symbol: str, qty: int = 0, market: str = "KRX") -> KisOrder | None:
        """시장가 매도 주문을 실행합니다. qty=0이면 전량 매도."""
        self._check_connected()
        try:
            s = self._kis.stock(symbol, market=market)
            order = s.sell(qty=qty if qty > 0 else None)
            logger.info(f"[{symbol}] 매도 주문 완료")
            return order
        except Exception as e:
            logger.error(f"[{symbol}] 매도 주문 실패: {e}")
            return None

    def get_balance(self) -> dict:
        """계좌 잔고 정보를 반환합니다."""
        self._check_connected()
        try:
            balance = self._kis.account().balance()
            krw_deposit = balance.deposits.get("KRW")
            usd_deposit = balance.deposits.get("USD")
            cash = float(krw_deposit.amount) if krw_deposit else 0.0
            usd_cash = float(usd_deposit.amount) if usd_deposit else 0.0
            stock_value = float(balance.current_amount) if balance.current_amount else 0.0
            return {
                "cash": cash,
                "usd_cash": usd_cash,
                "total_assets": cash + stock_value,
            }
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            return {"cash": 0, "usd_cash": 0, "total_assets": 0}

    def get_holdings(self) -> list[dict]:
        """보유 종목 목록을 반환합니다."""
        self._check_connected()
        try:
            stocks = self._kis.account().balance().stocks
            result = []
            for s in stocks:
                qty = int(s.qty)
                current_price = float(s.price)
                profit_rate = float(s.profit_rate) if hasattr(s, "profit_rate") else 0.0
                # avg_price: purchase_amount / qty로 계산 (직접 속성 없을 경우)
                if hasattr(s, "purchase_price"):
                    avg_price = float(s.purchase_price)
                elif qty > 0 and hasattr(s, "amount") and hasattr(s, "profit"):
                    avg_price = (float(s.amount) - float(s.profit)) / qty
                else:
                    avg_price = current_price
                is_kr = str(s.symbol).isdigit()
                kis_market = "KRX" if is_kr else (
                    str(s.market) if hasattr(s, "market") and not is_kr else "NASDAQ"
                )
                result.append({
                    "symbol": s.symbol,
                    "qty": qty,
                    "avg_price": avg_price,
                    "current_price": current_price,
                    "profit_rate": profit_rate,
                    "market": "KR" if is_kr else "US",
                    "kis_market": kis_market,
                })
            return result
        except Exception as e:
            logger.error(f"보유 종목 조회 실패: {e}")
            return []
