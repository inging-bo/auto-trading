import json
import logging
import math
import os
import time
import yaml
import schedule
from datetime import datetime
from zoneinfo import ZoneInfo

from kis_client import KisClient
from screener import Screener
from strategies import load_strategy

# ── 로깅 설정 ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("trading.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_market_open(market: str = "KR") -> bool:
    """장 운영 시간 여부 확인"""
    if market == "US":
        et = datetime.now(ZoneInfo("America/New_York"))
        if et.weekday() >= 5:
            return False
        start = et.replace(hour=9, minute=30, second=0, microsecond=0)
        end = et.replace(hour=16, minute=0, second=0, microsecond=0)
        return start <= et <= end
    else:  # KR
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        start = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return start <= now <= end


class Trader:
    def __init__(self, config: dict):
        self.config = config
        self.virtual = config.get("virtual", True)
        self.client = KisClient(virtual=self.virtual)
        self.screener = Screener(self.client, config)
        self.strategy = load_strategy(config["strategy"], config)
        self.holdings: set[str] = set()

    def connect(self):
        self.client.connect()
        mode = "모의투자" if self.virtual else "실전투자"
        market = self.config.get("market", "KR")
        logger.info(f"═══════════════════════════════")
        logger.info(f" 자동매매 시작 ({mode})")
        logger.info(f" 전략: {self.strategy.name}")
        logger.info(f" 시장: {market}")
        logger.info(f"═══════════════════════════════")

    def _sync_holdings(self):
        holdings = self.client.get_holdings()
        self.holdings = {h["symbol"] for h in holdings}

    def _check_risk(self, holdings: list[dict]):
        risk = self.config.get("risk", {})
        stop_loss = risk.get("stop_loss_pct", -5.0)
        take_profit = risk.get("take_profit_pct", 10.0)

        for h in holdings:
            symbol = h["symbol"]
            rate = h["profit_rate"]
            market = h.get("kis_market", "KRX")

            if rate <= stop_loss:
                logger.warning(f"[{symbol}] 손절 실행 ({rate:.1f}%)")
                self.client.sell(symbol, market=market)
                self.holdings.discard(symbol)
            elif rate >= take_profit:
                logger.info(f"[{symbol}] 익절 실행 ({rate:.1f}%)")
                self.client.sell(symbol, market=market)
                self.holdings.discard(symbol)

    def _calc_qty(self, price: float, market: str = "KRX") -> int:
        risk = self.config.get("risk", {})
        if market == "KRX":
            max_amount = risk.get("max_buy_amount", 500000)
        else:
            max_amount = risk.get("us_max_buy_amount_usd", 300)
        qty = math.floor(max_amount / price)
        return max(qty, 1)

    def _process_target(self, target: dict):
        symbol = target["symbol"]
        market = target["market"]
        is_kr = (market == "KRX")

        # KR: 전략별 봉 유형, US: 항상 일봉
        if is_kr:
            if self.config["strategy"] == "volatility_breakout":
                chart_days, interval = "30d", "day"
            else:
                chart_days, interval = "60d", 5
        else:
            chart_days, interval = "60d", "day"

        df = self.client.get_chart(symbol, market=market,
                                   days=chart_days, interval=interval)
        if df.empty:
            return

        signal = self.strategy.generate_signal(symbol, df)

        quote = self.client.get_quote(symbol, market=market)
        if not quote:
            return
        price = quote["price"]
        price_str = f"{price:,.0f}원" if is_kr else f"${price:.2f}"

        if signal == "BUY" and symbol not in self.holdings:
            qty = self._calc_qty(price, market)
            logger.info(f"[{symbol}] 매수 실행 - {qty}주 @ {price_str}")
            order = self.client.buy(symbol, qty, market=market)
            if order:
                self.holdings.add(symbol)

        elif signal == "SELL" and symbol in self.holdings:
            logger.info(f"[{symbol}] 매도 실행 @ {price_str}")
            self.client.sell(symbol, market=market)
            self.holdings.discard(symbol)

        else:
            logger.info(f"[{symbol}] {signal} - 관망")

    def _load_accumulation(self) -> dict:
        if os.path.exists("accumulation.json"):
            try:
                with open("accumulation.json", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self.config.get("accumulation", {"enabled": False, "targets": []})

    def _run_accumulation(self):
        acc = self._load_accumulation()
        if not acc.get("enabled", False):
            return
        targets = acc.get("targets", [])
        if not targets:
            return
        logger.info("─── 모으기 실행 ───")
        for t in targets:
            symbol = str(t.get("symbol", "")).strip()
            amount = float(t.get("amount", 0))
            market = str(t.get("market", "KRX"))
            is_kr = (market == "KRX")

            if not symbol or amount <= 0:
                continue

            quote = self.client.get_quote(symbol, market=market)
            if not quote:
                logger.warning(f"[{symbol}] 모으기: 시세 조회 실패")
                continue

            price = quote["price"]
            qty = math.floor(amount / price)
            if qty < 1:
                unit = "원" if is_kr else "USD"
                logger.warning(f"[{symbol}] 모으기: {amount:,.0f}{unit}으로 1주 미만 (현재가 {price:,.2f})")
                continue

            actual = qty * price
            price_str = f"{price:,.0f}원" if is_kr else f"${price:.2f}"
            logger.info(f"[{symbol}] 모으기 매수 {qty}주 @ {price_str} (≈{actual:,.0f})")
            self.client.buy(symbol, qty, market=market)
        logger.info("─── 모으기 완료 ───")

    def run_once(self):
        market_config = self.config.get("market", "KR")

        kr_open = is_market_open("KR") if market_config in ("KR", "BOTH") else False
        us_open = is_market_open("US") if market_config in ("US", "BOTH") else False

        if not kr_open and not us_open:
            logger.info("장 운영 시간이 아닙니다. 대기 중...")
            return

        open_labels = []
        if kr_open: open_labels.append("한국")
        if us_open: open_labels.append("미국")
        logger.info(f"─── 매매 사이클 시작 [{' · '.join(open_labels)} 장 운영 중] ───")

        # 1. 보유 종목 동기화 및 리스크 체크
        self._sync_holdings()
        holdings = self.client.get_holdings()
        if holdings:
            self._check_risk(holdings)

        # 2. 스크리너 (열려있는 시장만)
        active = []
        if kr_open: active.append("KR")
        if us_open: active.append("US")
        targets = self.screener.run(active_markets=active)

        if not targets:
            logger.info("조건을 만족하는 종목이 없습니다.")
        else:
            for target in targets:
                self._process_target(target)

        # 3. 모으기
        self._run_accumulation()

        # 4. 잔고 출력
        balance = self.client.get_balance()
        logger.info(
            f"잔고: 현금 {balance['cash']:,.0f}원 | 총자산 {balance['total_assets']:,.0f}원"
        )
        logger.info("─── 매매 사이클 종료 ───\n")


def main():
    config = load_config()

    if not config.get("virtual", True):
        print("\n" + "=" * 50)
        print("  [경고] 실전투자 모드입니다")
        print("  실제 계좌에서 실제 돈으로 매매가 실행됩니다.")
        print("=" * 50)
        answer = input("계속 진행하시겠습니까? (yes 입력): ").strip().lower()
        if answer != "yes":
            print("취소되었습니다.")
            return
        print()

    trader = Trader(config)
    trader.connect()

    interval = config.get("interval_minutes", 5)
    logger.info(f"매매 주기: {interval}분")

    trader.run_once()
    schedule.every(interval).minutes.do(trader.run_once)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
