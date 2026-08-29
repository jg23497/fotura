from enum import Enum


class ReportCategory(str, Enum):
    ignored = "ignored"
    skipped = "skipped"
