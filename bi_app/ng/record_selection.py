"""Closed record-selection rules shared by target and upstream queries."""

from .catalog import identifier
from .errors import NgError

SELECTION_MODES = {"latest", "fixed_step_latest", "last_numeric_step_latest"}


def selection_config(process: dict) -> tuple[str, dict]:
    time_field = process.get("sort_time_field")
    if not time_field or time_field not in process["columns"]:
        raise NgError("宽表缺少经DDL分区确认的排序时间字段，请刷新字段字典", 422)
    identifier(time_field)
    rule = process.get("record_selection", {})
    if rule.get("mode") not in SELECTION_MODES:
        raise NgError("宽表记录选择规则无效，请刷新字段字典", 422)
    if rule["mode"] != "latest":
        if rule.get("step_field") != "technics_step_code" or rule["step_field"] not in process["columns"]:
            raise NgError("该工序缺少记录选择规则要求的工步字段", 422)
        if rule["mode"] == "fixed_step_latest" and rule.get("step_value") != "10":
            raise NgError("分容工步选择规则无效，请刷新字段字典", 422)
    return time_field, rule


def rule_filter(process: dict, alias: str = "") -> tuple[list[str], list]:
    _, rule = selection_config(process)
    prefix = f"{identifier(alias)}." if alias else ""
    if rule["mode"] == "latest":
        return [], []
    step = prefix + identifier(rule["step_field"])
    if rule["mode"] == "fixed_step_latest":
        return [f"TRIM({step}) = %s"], [rule["step_value"]]
    # Numeric comparison prevents varchar ordering such as '9' > '19'.
    return [f"TRIM({step}) REGEXP %s"], [r"^[0-9]+$"]


def order_sql(process: dict, selected: list[str], alias: str = "") -> str:
    time_field, rule = selection_config(process)
    prefix = f"{identifier(alias)}." if alias else ""
    terms = []
    if rule["mode"] == "last_numeric_step_latest":
        terms.append(f"CAST(TRIM({prefix}{identifier(rule['step_field'])}) AS BIGINT) DESC")
    terms.append(f"{prefix}{identifier(time_field)} DESC")
    # Deterministic ties without treating start_time as a second ordering clock.
    if "produce_id" in selected:
        terms.append(f"COALESCE(CAST({prefix}`produce_id` AS CHAR), '') DESC")
    for column in sorted(set(selected) - {time_field, "produce_id"}):
        terms.append(f"COALESCE(CAST({prefix}{identifier(column)} AS CHAR), 'None') DESC")
    return ", ".join(terms)


def rule_description(process: dict) -> str:
    time_field, rule = selection_config(process)
    if rule["mode"] == "fixed_step_latest":
        text = "工步10的最新记录"
    elif rule["mode"] == "last_numeric_step_latest":
        text = "每个产品数值最大工步中的最新记录"
    else:
        text = "最新记录"
    return f"{process['name']}：按{time_field}取{text}。"
