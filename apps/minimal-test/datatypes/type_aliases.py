"""生成されたTypeAlias（AnnotatedメタデータでExampleSpec/CheckedSpecを付与）

このファイルは spectool が spec.yaml から自動生成します。
新アーキテクチャでは、全ての型にAnnotatedメタ型でメタデータを付与します。
"""
from typing import TypeAlias
import pandas as pd

# === DataFrame TypeAliases ===

# Simple DataFrame with basic columns
SampleFrame: TypeAlias = pd.DataFrame
