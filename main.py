import json
import logging
import math
import os
import time
import yaml
import schedule
from datetime import datetime

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


def is_market_open() -> bool:
    """장 운영 시간 여부 확인 (평일 09:00 ~ 15:30)"""
    now = datetime.now()
    if now.weekday() >= 5:  # 토/일
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
        self.holdings: set[str] = set()  # 현재 보유 종목

    def connect(self):
        self.client.connect()
        mode = "모의투자" if self.virtual else "실전투자"
        logger.info(f"═══════════════════════════════")
        logger.info(f" 자동매매 시작 ({mode})")
        logger.info(f" 전략: {self.strategy.name}")
        logger.info(f"═══════════════════════════════")

    def _sync_holdings(self):
        """실제 보유 종목과 동기화합니다."""
        holdings = self.client.get_holdings()
        self.holdings = {h["symbol"] for h in holdings}

    def _check_risk(self, holdings: list[dict]):
        """손절/익절 조건을 확인하고 주문을 실행합니다."""
        risk = self.config.get("risk", {})
        stop_loss = risk.get("stop_loss_pct", -5.0)
        take_profit = risk.get("take_profit_pct", 10.0)

        for h in holdings:
            symbol = h["symbol"]
            rate = h["profit_rate"]

            if rate <= stop_loss:
                logger.warning(f"[{symbol}] 손절 실행 ({rate:.1f}%)")
                self.client.sell(symbol)
                self.holdings.discard(symbol)
            elif rate >= take_profit:
                logger.info(f"[{symbol}] 익절 실행 ({rate:.1f}%)")
                self.client.sell(symbol)
                self.holdings.discard(symbol)

    def _calc_qty(self, price: float) -> int:
        """매수 금액 기준으로 주수를 계산합니다."""
        max_amount = self.config.get("risk", {}).get("max_buy_amount", 500000)
        qty = math.floor(max_amount / price)
        return max(qty, 1)

    def _load_accumulation(self) -> dict:
        if os.path.exists("accumulation.json"):
            try:
                with open("accumulation.json", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self.config.get("accumulation", {"enabled": False, "targets": []})

    def _run_accumulation(self):
        """모으기: 설정 종목을 지정 금액만큼 매수합니다."""
        acc = self._load_accumulation()
        if not acc.get("enabled", False):
            return
        targets = acc.get("targets", [])
        if not targets:
            return
        logger.info("─── 모으기 실행 ───")
        for t in targets:
            symbol = str(t.get("symbol", "")).strip()
            amount = int(t.get("amount", 0))
            if not symbol or amount <= 0:
                continue
            quote = self.client.get_quote(symbol)
            if not quote:
                logger.warning(f"[{symbol}] 모으기: 시세 조회 실패")
                continue
            price = quote["price"]
            qty = math.floor(amount / price)
            if qty < 1:
                logger.warning(f"[{symbol}] 모으기: {amount:,}원으로 {price:,}원짜리 1주 미만")
                continue
            actual = qty * price
            logger.info(f"[{symbol}] 모으기 매수 {qty}주 @ {price:,}원 (≈{actual:,}원)")
            self.client.buy(symbol, qty)
        logger.info("─── 모으기 완료 ───")

    def run_once(self):
        """매매 사이클 1회 실행"""
        if not is_market_open():
            logger.info("장 운영 시간이 아닙니다. 대기 중...")
            return

        logger.info("─── 매매 사이클 시작 ───")

        # 1. 보유 종목 동기화 및 리스크 체크
        self._sync_holdings()
        holdings = self.client.get_holdings()
        if holdings:
            self._check_risk(holdings)

        # 2. 스크리너로 매매 대상 종목 선정
        targets = self.screener.run()
        if not targets:
            logger.info("조건을 만족하는 종목이 없습니다.")
            return

        # 3. 각 종목에 전략 적용
        for symbol in targets:
            chart_days = "60d"
            interval = 5  # 5분봉

            # 변동성 돌파 전략은 일봉 사용
            if self.config["strategy"] == "volatility_breakout":
                chart_days = "30d"
                interval = "day"

            df = self.client.get_chart(symbol, days=chart_days, interval=interval)
            if df.empty:
                continue

            signal = self.strategy.generate_signal(symbol, df)

            quote = self.client.get_quote(symbol)
            if not quote:
                continue
            price = quote["price"]

            if signal == "BUY" and symbol not in self.holdings:
                qty = self._calc_qty(price)
                logger.info(f"[{symbol}] 매수 실행 - {qty}주 @ {price:,}원")
                order = self.client.buy(symbol, qty)
                if order:
                    self.holdings.add(symbol)

            elif signal == "SELL" and symbol in self.holdings:
                logger.info(f"[{symbol}] 매도 실행 @ {price:,}원")
                self.client.sell(symbol)
                self.holdings.discard(symbol)

            else:
                logger.info(f"[{symbol}] {signal} - 관망")

        # 4. 모으기
        self._run_accumulation()

        # 5. 잔고 출력
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

    # 즉시 1회 실행 후 스케줄 등록
    trader.run_once()
    schedule.every(interval).minutes.do(trader.run_once)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
