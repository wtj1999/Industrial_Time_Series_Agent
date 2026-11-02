"""Recall real database values and resolve model-selected IDs back to those values."""

import re
import unicodedata
from difflib import SequenceMatcher

from .schemas import FILTER_LABELS, NgFilters, NgMatchingResult


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    # Common equipment numbering spellings: 1号 / 1# / #1.
    return re.sub(r"[\W_]|号", "", value)


def rank_candidates(mention: str, values: list[str], limit: int) -> list[str]:
    needle = normalized(mention)
    numbers = re.findall(r"\d+", needle)

    def score(value: str) -> tuple:
        candidate = normalized(value)
        candidate_numbers = re.findall(r"\d+", candidate)
        exact = bool(needle) and needle == candidate
        contains = bool(needle) and (needle in candidate or candidate in needle)
        # Preserve the device number while allowing extra station/channel numbers.
        # "1号切卷机" must rank #1切卷一体机 above 11#切卷机 despite substring similarity.
        same_number = bool(numbers) and candidate_numbers[:len(numbers)] == numbers
        return exact, same_number, contains, SequenceMatcher(None, needle, candidate).ratio()

    return sorted(dict.fromkeys(values), key=score, reverse=True)[:limit]


def prepare_requests(mentions: NgFilters, options: dict[str, dict], limit: int) -> list[dict]:
    requests = []
    for field, inputs in mentions.nonempty().items():
        for value in inputs:
            choices = rank_candidates(value, options.get(field, {}).get("values", []), limit)
            requests.append({
                "input_id": len(requests), "field": field, "field_name": FILTER_LABELS[field],
                "input_value": value,
                "candidates": [{"id": index, "value": choice} for index, choice in enumerate(choices)],
                "truncated": options.get(field, {}).get("truncated", False),
                "candidate_total": len(options.get(field, {}).get("values", [])),
                "recall_limited": len(choices) < len(options.get(field, {}).get("values", [])),
            })
    return requests


def resolve_decisions(requests: list[dict], result: NgMatchingResult) -> tuple[NgFilters, list[dict]]:
    by_id: dict[int, list] = {}
    for decision in result.decisions:
        by_id.setdefault(decision.input_id, []).append(decision)
    filters: dict[str, list[str]] = {}
    matches = []
    for request in requests:
        decisions = by_id.get(request["input_id"], [])
        choices = request["candidates"]
        status, values, note = "unmatched", [], "未找到可靠匹配，请搜索实际选项后勾选；留空表示该条件不限制。"
        if len(decisions) == 1:
            decision = decisions[0]
            ids = list(dict.fromkeys(decision.candidate_ids))
            valid = all(0 <= index < len(choices) for index in ids)
            if valid and ids and decision.status != "unmatched":
                values = [choices[index]["value"] for index in ids]
                status = decision.status
                if request["truncated"] or (request["recall_limited"] and len(values) > 1):
                    status = "ambiguous"
                note = "已匹配数据库实际值并预选，可修改或清空。" if status == "matched" else "存在多个可能或候选尚不完整，请勾选确认；留空表示该条件不限制。"
        if status == "matched":
            filters.setdefault(request["field"], []).extend(values)
        matches.append({
            "field": request["field"], "field_name": request["field_name"],
            "input_value": request["input_value"], "status": status,
            "values": values, "message": note,
        })
    return NgFilters.model_validate(filters), matches
