from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    def __init__(self, config: dict):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def generate_signal(self, symbol: str, df: pd.DataFrame) -> str:
        """
        캔들 데이터를 분석해 매매 신호를 반환합니다.
        반환값: 'BUY' | 'SELL' | 'HOLD'
        """
        pass

    def _validate_df(self, df: pd.DataFrame, min_rows: int) -> bool:
        if df is None or df.empty or len(df) < min_rows:
            return False
        return True
