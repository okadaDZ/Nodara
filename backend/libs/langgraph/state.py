from __future__ import annotations

import operator
from typing import Annotated, TypedDict


def merge_maps(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    return {**left, **right}


class WorkflowGraphState(TypedDict):
    original_input: str
    outputs: Annotated[dict[str, str], merge_maps]
    routes: Annotated[dict[str, str], merge_maps]
    errors: Annotated[list[str], operator.add]
    steps: Annotated[int, operator.add]
