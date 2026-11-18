"""Interval bubbles count each target product once within each numeric interval."""

import bisect
import math


SHARED_MATERIAL_PROCESSES = {"C1101", "C1103", "C1201", "C1202", "C1301", "C1302"}


def parameter_record_stats(observations):
    """Summarize distinct valid source records separately within NG and OK."""
    records = {"NG": {}, "OK": {}}
    for value, _target, group, record in observations:
        records[group][record] = value
    result = {}
    for group, sources in records.items():
        values = sorted(sources.values())
        count = len(values)
        median = None
        if count:
            low, high = values[(count - 1) // 2], values[count // 2]
            span = high - low
            median = low + span / 2 if math.isfinite(span) else low / 2 + high / 2
        result[group] = {"parameter_record_count": count, "parameter_record_median": median}
    return result


def interval_bubbles(observations, *, max_bins=10):
    """Input tuples: (finite value, target key, NG/OK group, source record key)."""
    values = sorted({row[0] for row in observations})
    result = {"strategy": "equal_width", "max_bins": max_bins,
              "denominator": "distinct_target_products_within_interval",
              "size_metric": "product_count", "range_min": None, "range_max": None,
              "covered_products": 0, "bins": []}
    if not values:
        return result
    low, high = values[0], values[-1]
    count = min(max_bins, len(values))
    if low == high:
        edges = [low, high]
    else:
        span = high - low
        edges = [low + span * i / count if math.isfinite(span)
                 else low * (1 - i / count) + high * (i / count) for i in range(count + 1)]
        edges[0], edges[-1] = low, high
        edges = sorted(set(edges))
    buckets = [{"NG": set(), "OK": set(), "records": set(), "codes": set(), "associations": 0}
               for _ in range(len(edges) - 1)]
    covered = set()
    for value, target, group, record in observations:
        index = min(len(buckets) - 1, max(0, bisect.bisect_right(edges, value) - 1))
        bucket = buckets[index]
        bucket[group].add(target)
        bucket["records"].add(record)
        bucket["codes"].add(record[:2])
        bucket["associations"] += 1
        covered.add(target)
    bins = []
    for index, bucket in enumerate(buckets):
        ng, ok = len(bucket["NG"]), len(bucket["OK"])
        total = ng + ok
        bins.append({"index": index, "lower": edges[index], "upper": edges[index + 1],
                     "upper_inclusive": index == len(buckets) - 1,
                     "NG": ng, "OK": ok, "product_count": total,
                     "ng_rate": ng / total if total else None,
                     "source_record_count": len(bucket["records"]),
                     "upstream_code_count": len(bucket["codes"]),
                     "association_count": bucket["associations"]})
    return {**result, "range_min": low, "range_max": high, "covered_products": len(covered), "bins": bins}
