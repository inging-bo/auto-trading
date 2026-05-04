"""
자동매매 런타임 상태 공유 모듈.
스크리너 결과와 전략 신호를 스레드 안전하게 저장하며,
app.py(Flask)와 main.py(Trader) 양쪽에서 접근합니다.
"""
import threading
from datetime import datetime

_lock = threading.Lock()

_state: dict = {
    "updated_at": None,   # 마지막 사이클 시각
    "selected":   [],     # 스크리너 통과 {"symbol", "market"}
    "rejected":   [],     # 스크리너 탈락 {"symbol", "reason"}
    "signals":    [],     # 전략 신호    {"symbol", "market", "signal", "price", "price_str", "action"}
}


def set_screener_result(selected: list[dict], rejected: list[dict]) -> None:
    with _lock:
        _state["selected"]   = list(selected)
        _state["rejected"]   = list(rejected)
        _state["signals"]    = []
        _state["updated_at"] = datetime.now().strftime("%H:%M:%S")


def add_signal(symbol: str, market: str, signal: str,
               price: float, price_str: str, action: str) -> None:
    with _lock:
        for s in _state["signals"]:
            if s["symbol"] == symbol:
                s.update({"signal": signal, "price": price,
                          "price_str": price_str, "action": action})
                return
        _state["signals"].append({
            "symbol": symbol, "market": market,
            "signal": signal, "price": price,
            "price_str": price_str, "action": action,
        })


def get_state() -> dict:
    with _lock:
        return {
            "updated_at": _state["updated_at"],
            "selected":   list(_state["selected"]),
            "rejected":   list(_state["rejected"]),
            "signals":    list(_state["signals"]),
        }
