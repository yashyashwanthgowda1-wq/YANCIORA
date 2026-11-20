"""Token metrics (BRD §5.3, §10). Pure functions, no I/O."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


def fertility(token_count: int, word_count: int) -> float | None:
    """Tokens per word. None when there are no words (undefined, not zero)."""
    return token_count / word_count if word_count > 0 else None


def relative_ratio(value: float | None, reference: float | None) -> float | None:
    """value / reference, e.g. a language's fertility over English fertility for
    equivalent content under the same tokenizer. This is a tokenization ratio, not
    a cost multiplier."""
    if value is None or reference is None or reference == 0:
        return None
    return value / reference


@dataclass(frozen=True)
class Summary:
    n: int
    mean: float | None
    median: float | None
    stdev: float | None
    ci95_low: float | None
    ci95_high: float | None


def summarize(values: list[float]) -> Summary:
    """Mean, median, sample stdev and a normal-approximation 95% CI of the mean.
    The CI is only reported for n >= 30, where the approximation is reasonable."""
    vals = [v for v in values if v is not None and not math.isnan(v)]
    n = len(vals)
    if n == 0:
        return Summary(0, None, None, None, None, None)
    mean = statistics.fmean(vals)
    median = statistics.median(vals)
    stdev = statistics.stdev(vals) if n > 1 else None
    if stdev is not None and n >= 30:
        half = 1.96 * stdev / math.sqrt(n)
        return Summary(n, mean, median, stdev, mean - half, mean + half)
    return Summary(n, mean, median, stdev, None, None)
