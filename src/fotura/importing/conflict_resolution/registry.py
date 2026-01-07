from fotura.importing.conflict_resolution.strategies.keep_both_strategy import (
    KeepBothStrategy,
)
from fotura.importing.conflict_resolution.strategies.skip_strategy import SkipStrategy

STRATEGIES = {"keep_both": KeepBothStrategy, "skip": SkipStrategy}


def get_conflict_resolver(strategy: str):
    if strategy in STRATEGIES:
        return STRATEGIES[strategy]()
    else:
        raise ValueError(f"Unsupported conflict resolution strategy: {strategy}")
