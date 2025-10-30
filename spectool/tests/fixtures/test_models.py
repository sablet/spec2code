"""テスト用Pydanticモデル

Normalizer テストで使用するPydanticモデル定義
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TimeSeriesRow(BaseModel):
    """時系列データの行モデル"""

    timestamp: datetime = Field(description="タイムスタンプ")
    value: float = Field(description="値")
    status: str = Field(description="ステータス")
    metadata: Optional[dict] = Field(default=None, description="メタデータ（オプショナル）")


class SensorDataRow(BaseModel):
    """センサーデータの行モデル"""

    timestamp: datetime = Field(description="タイムスタンプ")
    temperature: float = Field(description="温度")
    humidity: float = Field(description="湿度")
    pressure: float = Field(description="気圧")
