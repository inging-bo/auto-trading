from strategies.base import BaseStrategy
from strategies.ma_cross import MACrossStrategy
from strategies.rsi import RSIStrategy
from strategies.bollinger import BollingerStrategy
from strategies.volatility_breakout import VolatilityBreakoutStrategy

STRATEGY_MAP = {
    "ma_cross": MACrossStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "volatility_breakout": VolatilityBreakoutStrategy,
}


def load_strategy(name: str, config: dict) -> BaseStrategy:
    if name not in STRATEGY_MAP:
        available = list(STRATEGY_MAP.keys())
        raise ValueError(f"알 수 없는 전략: '{name}'. 사용 가능: {available}")
    return STRATEGY_MAP[name](config.get(name, {}))
