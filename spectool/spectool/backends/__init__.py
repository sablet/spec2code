"""バックエンド層 - IR→成果物生成

IRからコード生成を行う純関数群。
各バックエンドはIRのみに依存し、相互に独立している。
"""

from . import py_code, py_skeleton, py_validators

__all__ = ["py_code", "py_validators", "py_skeleton"]
