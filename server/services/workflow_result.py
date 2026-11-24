"""Shared result object for the supplementary workflow Services."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


Record = Mapping[str, object]


class WorkflowResult:
    def __init__(
        self,
        status: str,
        message: str,
        *,
        record: Record | None = None,
        records: Sequence[Record] = (),
        value: object | None = None,
    ) -> None:
        self.status = status
        self.message = message
        self.record = record
        self.records = tuple(records)
        self.value = value
        self.success = status == "success"
