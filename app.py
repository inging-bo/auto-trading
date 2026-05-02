import re
import threading
import time
import yaml
import logging
import schedule as sched_lib
from collections import deque
from datetime import datetime
from flask import Flask, jsonify, render_template, request

from kis_client import KisClient
from strategies import STRATEGY_MAP

STOCK_NAMES: dict[str, str] = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "035720": "카카오",
    "051910": "LG화학",
    "006400": "삼성SDI",
    "207940": "삼성바이오로직스",
    "068270": "셀트리온",
    "105560": "KB금융",
    "055550": "신한지주",
    "003550": "LG",
    "066570": "LG전자",
    "028260": "삼성물산",
    "012330": "현대모비스",
    "005380": "현대차",
}

app = Flask(__name__)

# ── 로그 캡처 ─────────────────────────────────────────────
log_entries: deque[dict] = deque(maxlen=200)


class UILogHandler(logging.Handler):
    def emit(self, record):
        log_entries.appendleft({
            "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
            "level": record.levelname,
            "message": self.format(record),
        })


_ui_handler = UILogHandler()
_ui_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(_ui_handler)
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# ── 봇 상태 관리 ──────────────────────────────────────────
class BotState:
    def __init__(self):
        self.running = False
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()


bot = BotState()

# ── 잔고 캐시 ─────────────────────────────────────────────
_balance_cache: dict = {"data": None, "ts": 0.0}
_cache_lock = threading.Lock()
CACHE_TTL = 60

# ── 감시종목 캐시 ──────────────────────────────────────────
_watchlist_cache: dict = {"data": None, "ts": 0.0}
_watchlist_lock = threading.Lock()
WATCHLIST_CACHE_TTL = 60


def _fetch_balance_from_api() -> dict:
    config = _load_config()
    try:
        client = KisClient(virtual=config.get("virtual", False))
        client.connect()
        balance = client.get_balance()
        holdings = client.get_holdings()
        return {"balance": balance, "holdings": holdings}
    except Exception as e:
        logger.error(f"잔고 조회 실패: {e}")
        return {"balance": {"cash": 0, "total_assets": 0}, "holdings": []}


def get_balance_cached(force: bool = False) -> dict:
    now = time.time()
    with _cache_lock:
        if not force and _balance_cache["data"] and now - _balance_cache["ts"] < CACHE_TTL:
            return _balance_cache["data"]
    data = _fetch_balance_from_api()
    with _cache_lock:
        _balance_cache["data"] = data
        _balance_cache["ts"] = time.time()
    return data


def _fetch_watchlist_from_api() -> dict:
    config = _load_config()
    cfg = config.get("screener", {})
    watchlist: list[str] = cfg.get("watchlist", [])
    min_volume: int = cfg.get("min_volume", 500000)
    min_price: int = cfg.get("min_price", 5000)
    max_price: int = cfg.get("max_price", 200000)

    # config 종목을 항상 채워 두어 API 실패 시에도 목록은 표시
    items = [{"symbol": s, "name": STOCK_NAMES.get(s, s), "error": True} for s in watchlist]

    try:
        client = KisClient(virtual=config.get("virtual", False))
        client.connect()
        filled = []
        for symbol in watchlist:
            name = STOCK_NAMES.get(symbol, symbol)
            quote = client.get_quote(symbol)
            if not quote:
                filled.append({"symbol": symbol, "name": name, "error": True})
                continue
            price = quote["price"]
            volume = quote["volume"]
            prev = quote.get("prev_price", price)
            change_rate = round(((price - prev) / prev * 100) if prev else 0.0, 2)

            fail_reason = None
            if volume < min_volume:
                fail_reason = "거래량 부족"
            elif not (min_price <= price <= max_price):
                fail_reason = "가격 범위 초과"

            filled.append({
                "symbol": symbol,
                "name": name,
                "price": price,
                "volume": volume,
                "change_rate": change_rate,
                "passed": fail_reason is None,
                "fail_reason": fail_reason,
            })
        items = filled
    except Exception as e:
        logger.error(f"감시종목 조회 실패: {e}")

    return {
        "items": items,
        "updated_at": datetime.now().strftime("%H:%M:%S"),
    }


def get_watchlist_cached(force: bool = False) -> dict:
    now = time.time()
    with _watchlist_lock:
        if not force and _watchlist_cache["data"] and now - _watchlist_cache["ts"] < WATCHLIST_CACHE_TTL:
            return _watchlist_cache["data"]
    data = _fetch_watchlist_from_api()
    with _watchlist_lock:
        _watchlist_cache["data"] = data
        _watchlist_cache["ts"] = time.time()
    return data


# ── Config 유틸 ───────────────────────────────────────────
def _load_config() -> dict:
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_strategy(strategy: str):
    """config.yaml의 strategy 값만 교체합니다 (주석 보존)."""
    with open("config.yaml", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(
        r"^(strategy:\s*).*$", f"\\g<1>{strategy}", content, flags=re.MULTILINE
    )
    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write(content)


# ── 봇 실행 루프 ──────────────────────────────────────────
def _trading_loop():
    from main import Trader

    sched_lib.clear()
    config = _load_config()

    try:
        trader = Trader(config)
        trader.connect()
        interval = config.get("interval_minutes", 5)

        trader.run_once()
        sched_lib.every(interval).minutes.do(trader.run_once)

        while not bot.stop_event.is_set():
            sched_lib.run_pending()
            time.sleep(10)

    except Exception as e:
        logger.error(f"봇 오류: {e}")
    finally:
        sched_lib.clear()
        bot.running = False
        logger.info("봇이 중지되었습니다.")


# ── API 라우트 ─────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    config = _load_config()
    return jsonify({
        "running": bot.running,
        "strategy": config.get("strategy", "rsi"),
        "virtual": config.get("virtual", False),
        "interval": config.get("interval_minutes", 5),
    })


@app.route("/api/balance")
def api_balance():
    return jsonify(get_balance_cached())


@app.route("/api/balance/refresh")
def api_balance_refresh():
    return jsonify(get_balance_cached(force=True))


@app.route("/api/logs")
def api_logs():
    return jsonify(list(log_entries))


@app.route("/api/start", methods=["POST"])
def api_start():
    if bot.running:
        return jsonify({"status": "already_running"})
    bot.stop_event.clear()
    bot.running = True
    bot.thread = threading.Thread(target=_trading_loop, daemon=True)
    bot.thread.start()
    logger.info("봇을 시작합니다.")
    return jsonify({"status": "started"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    if not bot.running:
        return jsonify({"status": "not_running"})
    bot.stop_event.set()
    return jsonify({"status": "stopped"})


@app.route("/api/watchlist")
def api_watchlist():
    return jsonify(get_watchlist_cached())


@app.route("/api/watchlist/refresh")
def api_watchlist_refresh():
    return jsonify(get_watchlist_cached(force=True))


@app.route("/api/strategy", methods=["POST"])
def api_strategy():
    data = request.get_json() or {}
    strategy = data.get("strategy", "")
    if strategy not in STRATEGY_MAP:
        return jsonify({"error": "올바르지 않은 전략입니다."}), 400
    _save_strategy(strategy)
    logger.info(f"전략 변경: {strategy}")
    return jsonify({"status": "ok", "strategy": strategy})


if __name__ == "__main__":
    print("AutoTrader UI 시작: http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
