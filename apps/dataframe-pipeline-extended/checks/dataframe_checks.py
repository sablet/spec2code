# Auto-generated skeleton for Check functions
import pandas as pd


def check_step_a(payload: pd.DataFrame) -> bool:
    """Step A DataFrame validation"""
    required_cols = {"timestamp", "value"}
    if not required_cols.issubset(payload.columns):
        return False
    return len(payload) > 0


def check_normalized(payload: pd.DataFrame) -> bool:
    """Normalized DataFrame validation"""
    required_cols = {"timestamp", "value", "normalized"}
    if not required_cols.issubset(payload.columns):
        return False
    return len(payload) > 0


def check_step_b(payload: pd.DataFrame) -> bool:
    """Step B DataFrame validation"""
    required_cols = {"timestamp", "value", "normalized"}
    if not required_cols.issubset(payload.columns):
        return False
    return len(payload) > 0
