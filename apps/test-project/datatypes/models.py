"""テスト用Pydanticモデル"""

from pydantic import BaseModel


class TimeSeriesRow(BaseModel):
    """時系列データの行モデル"""

    timestamp: str
    value: float
    status: str
    metadata: str = ""  # オプショナルフィールド


class SensorDataRow(BaseModel):
    """センサーデータの行モデル"""

    timestamp: str
    temperature: float
    humidity: float
    pressure: float
