from .types import DiffPlan


def build_diff(
    fetched_ids: set[str], active_ids: set[str], expired_ids: set[str]
) -> DiffPlan:
    return DiffPlan(
        new=frozenset(fetched_ids - active_ids - expired_ids),
        present=frozenset(fetched_ids & active_ids),
        missing=frozenset(active_ids - fetched_ids),
        reappeared=frozenset(fetched_ids & expired_ids),
    )
