"""Target portraits and observational evidence. No candidate is declared a cause."""

import bisect
import math
import logging
from collections import Counter, defaultdict
from statistics import median


CONTROLS = ("tenant_id", "technics_line_name", "device_name", "shift", "shift_date", "produce_order_code")
logger = logging.getLogger(__name__)


def finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def shift_label(value):
    raw = "" if value is None else str(value).strip()
    if raw.lower() in {"白班", "日班", "白", "day", "day shift"}:
        return "白班"
    if raw.lower() in {"夜班", "夜", "night", "night shift"}:
        return "夜班"
    return raw or "班次未知"


def context_value(product, name):
    if name == "shift":
        return shift_label(product.get(name))
    value = product.get(name)
    return str(value) if value is not None and str(value).strip() else "未知"


def edges_for(values, maximum=16):
    values = sorted(set(values))
    if not values:
        return []
    low, high = values[0], values[-1]
    if low == high:
        return [low, high]
    count = min(maximum, len(values))
    span = high - low
    edges = [low + span * i / count if math.isfinite(span) else low * (1-i/count) + high * i/count
             for i in range(count + 1)]
    edges[0], edges[-1] = low, high
    return sorted(set(edges))


def target_portrait(products, target, stats):
    products = [p for p in products if p['_group'] in {'NG','OK'}]
    column = target["column"]
    valid = [p for p in products if p["_group"] in {"NG", "OK"}]
    edges = edges_for([v for p in valid if (v := finite(p.get(column))) is not None])
    dimensions = {}
    for dimension in ("overall", "device", "shift", "device_shift"):
        buckets = defaultdict(list)
        for p in products:
            device, shift = context_value(p, "device_name"), context_value(p, "shift")
            identity = (context_value(p, "tenant_id"), context_value(p, "technics_line_name"))
            key = () if dimension == "overall" else (identity + (device,) if dimension == "device"
                  else (shift,) if dimension == "shift" else identity + (device, shift))
            buckets[key].append(p)
        rows = []
        multiple_lines = len({(p.get("tenant_id"), p.get("technics_line_name")) for p in products}) > 1
        for key, items in sorted(buckets.items()):
            label = ("总体" if not key else key[0] if dimension == "shift" else
                     " · ".join(key if multiple_lines else key[2:]))
            groups = {}
            histogram = [{"lower": edges[i], "upper": edges[i+1], "NG": 0, "OK": 0,
                          "upper_inclusive": i == len(edges)-2} for i in range(max(0, len(edges)-1))]
            for group in ("NG", "OK"):
                members = [p for p in items if p["_group"] == group]
                values = [v for p in members if (v := finite(p.get(column))) is not None]
                groups[group] = stats(values, len(members))
                for value in values:
                    index = min(len(histogram)-1, max(0, bisect.bisect_right(edges, value)-1))
                    histogram[index][group] += 1
            ng = sum(p["_group"] == "NG" for p in items)
            ok = sum(p["_group"] == "OK" for p in items)
            rows.append({"key": list(key), "label": label, "NG": ng, "OK": ok,
                         "excluded": len(items)-ng-ok, "ng_share": ng/(ng+ok) if ng+ok else None,
                         "groups": groups, "histogram": histogram})
        dimensions[dimension] = rows
    findings = []
    overall = dimensions["overall"][0] if dimensions["overall"] else None
    if overall:
        a,b = overall["groups"]["NG"],overall["groups"]["OK"]
        if a["count"] and b["count"]:
            findings.append(f"目标数值NG中位数{a['median']:.5g}、OK中位数{b['median']:.5g}；四分位距分别为{a['q3']-a['q1']:.5g}、{b['q3']-b['q1']:.5g}。")
    for dimension,label in (("device","设备"),("shift","班次"),("device_shift","设备×班次")):
        comparable = [r for r in dimensions[dimension] if r["NG"]+r["OK"] >= 20]
        if len(comparable) >= 2:
            high,low = max(comparable,key=lambda r:r["ng_share"]),min(comparable,key=lambda r:r["ng_share"])
            findings.append(f"{label}分组中，{high['label']}的样本NG占比最高（{high['NG']}/{high['NG']+high['OK']}，{high['ng_share']*100:.2f}%），与最低组相差{(high['ng_share']-low['ng_share'])*100:.2f}个百分点；此为定位线索。")
        else:
            findings.append(f"{label}维度尚无两个各含20个NG/OK产品的可比组，暂不判断组间差异。")
    return {"dimensions": dimensions, "findings":findings, "unit": "distinct_target_product",
            "rate_denominator": "current_NG_plus_confirmed_OK",
            "rate_note": "NG占比以本次当前缺陷NG与确认OK为分母，其他缺陷或未知质量不计入，不等同于全产线不良率。",
            "shift_note": "班次读取目标记录shift，不根据end_time的小时推断；未知班次单列。"}


def collapse_observations(field, observations):
    buckets = defaultdict(list)
    sources = defaultdict(set)
    for value, key, _group, record in observations:
        buckets[key].append(value)
        sources[key].add((field["process"]["table"], *record[:2]))
    return {"field": field, "samples": {key: {"median": median(values), "spread": max(values)-min(values),
                                               "sources": sources[key]} for key, values in buckets.items()}}


def adjusted_comparison(pairs, threshold):
    """Common-stratum standardization; an association, not an intervention effect."""
    strata = defaultdict(lambda: [[], []])
    all_groups = [[], []]
    for product, value in pairs:
        high = int(value > threshold)
        outcome = int(product["_group"] == "NG")
        all_groups[high].append(outcome)
        strata[tuple(context_value(product, name) for name in CONTROLS)][high].append(outcome)
    def difference(groups):
        return sum(groups[1])/len(groups[1])-sum(groups[0])/len(groups[0]) if all(groups) else None
    comparisons = [(len(g[0])*len(g[1])/(len(g[0])+len(g[1])), difference(g), len(g[0])+len(g[1]))
                   for g in strata.values() if min(map(len, g)) >= 3]
    weight = sum(row[0] for row in comparisons)
    return {"threshold": threshold, "raw_risk_difference": difference(all_groups),
            "adjusted_risk_difference": sum(w*d for w,d,_ in comparisons)/weight if weight else None,
            "matched_products": sum(n for _,_,n in comparisons), "comparable_strata": len(comparisons),
            "controls": list(CONTROLS), "method": "overlap_weighted_within_stratum_risk_difference"}


def screen_factor(data, products, box, target_column=None):
    from scipy.stats import ks_2samp, mannwhitneyu, spearmanr
    samples = data["samples"]
    pairs = [(p, samples[p["_key"]]["median"]) for p in products if p["_key"] in samples and p["_group"] in {"NG", "OK"}]
    values = {g: [v for p,v in pairs if p["_group"] == g] for g in ("NG", "OK")}
    totals = Counter(p["_group"] for p in products)
    source_usage = Counter(s for sample in samples.values() for s in sample["sources"])
    shared = any(n > 1 for n in source_usage.values())
    records = set()
    # Source-code count describes independent material identities, not repeated cell associations.
    for sample in samples.values():
        records.update(sample["sources"])
    ng, ok = values["NG"], values["OK"]
    field = data["field"]
    result = {"field_id": field["id"], "name": field["name"], "process_name": field["process"]["name"],
              "status": "insufficient", "reason": "NG或OK有效产品少于5个，暂不排序。", "score": 0.0,
              "coverage": {g: {"valid": len(values[g]), "total": totals[g]} for g in ("NG", "OK")},
              "source_codes": len(records), "shared_sources": shared, "distinct_values": len(set(ng+ok)),
              "median_NG": median(ng) if ng else None, "median_OK": median(ok) if ok else None,
              "distribution_effect": None, "rank_effect": None, "p_value": None, "q_value": None,
              "spread_effect": None,
              "adjustment": None, "stability": {"status": "insufficient", "periods": [], "consistent_fraction": None},
              "worst_interval": None, "model_contribution": None,
              "target_relation": {"products":0,"spearman":None},
              "mechanism": "数值关系为观察性证据，需工程师核对工艺机制及替代解释。"}
    result["mechanism_hypothesis"] = field.get("mechanism_hypothesis")
    correlated = [(v,finite(p.get(target_column))) for p,v in pairs] if target_column else []
    correlated = [(a,b) for a,b in correlated if b is not None]
    result["target_relation"]["products"] = len(correlated)
    if len(correlated) >= 5 and len({a for a,b in correlated}) > 1 and len({b for a,b in correlated}) > 1:
        result["target_relation"]["spearman"] = float(spearmanr([a for a,b in correlated],[b for a,b in correlated]).statistic)
    if min(len(ng), len(ok)) < 5:
        return result
    if len(set(ng+ok)) <= 1 and not any(s["spread"] for s in samples.values()):
        return {**result, "status": "constant", "reason": "当前字段无有效变化，不能区分NG与OK。"}
    ks = float(ks_2samp(ng, ok).statistic)
    spreads = {g:[samples[p["_key"]]["spread"] for p,v in pairs if p["_group"] == g] for g in ("NG","OK")}
    spread_effect = float(ks_2samp(spreads["NG"],spreads["OK"]).statistic)
    u = mannwhitneyu(ng, ok, alternative="two-sided", method="asymptotic")
    rank = float(2*u.statistic/(len(ng)*len(ok))-1)
    result.update(distribution_effect=ks, spread_effect=spread_effect, rank_effect=rank, score=max(ks,spread_effect))
    if not shared:
        result["p_value"] = float(u.pvalue)
    threshold = median(ng+ok)
    comparison = adjusted_comparison(pairs, threshold)
    result["adjustment"] = comparison
    baseline = len(ng)/(len(ng)+len(ok))
    bins = [b for b in box["bubble"]["bins"] if b["product_count"] >= 10 and b["NG"] >= 2]
    if bins:
        worst = max(bins, key=lambda b: b["ng_rate"])
        result["worst_interval"] = {"lower": worst["lower"], "upper": worst["upper"],
                                    "ng_share": worst["ng_rate"], "products": worst["product_count"],
                                    "baseline_share": baseline, "lift": worst["ng_rate"]/baseline}
    by_date = defaultdict(list)
    for p,value in pairs:
        by_date[context_value(p, "shift_date")].append((p, value))
    periods = []
    for date, members in sorted(by_date.items()):
        split = [[], []]
        for p,value in members:
            split[int(value > threshold)].append(int(p["_group"] == "NG"))
        if min(map(len, split)) >= 5:
            periods.append({"date": date, "risk_difference": sum(split[1])/len(split[1])-sum(split[0])/len(split[0]),
                            "products": len(members)})
    raw, adjusted = comparison["raw_risk_difference"], comparison["adjusted_risk_difference"]
    direction = adjusted if adjusted is not None else raw
    consistent = sum(p["risk_difference"]*direction > 0 for p in periods)/len(periods) if len(periods) >= 2 and direction else None
    result["stability"] = {"status": "consistent" if consistent is not None and consistent >= .75 else "mixed" if consistent is not None else "insufficient",
                           "periods": periods, "consistent_fraction": consistent}
    if shared and len(records) < 10:
        result.update(status="limited_sources", reason="共享物料独立编码少于10个，仅作描述，不能以电芯数量放大证据。")
    elif min(len(ng)/max(1, totals["NG"]), len(ok)/max(1, totals["OK"])) < .5:
        result.update(status="low_coverage", reason="至少一组覆盖不足50%，仅作描述，不进入模型候选。")
    elif result["score"] < .1:
        result.update(status="no_difference", reason="当前NG/OK在参数位置与多码极差上的区分度较弱，尚无优先验证依据。")
    elif raw is not None and abs(raw) > .01 and adjusted is not None and (raw*adjusted <= 0 or abs(adjusted) < .2*abs(raw)):
        result.update(status="confounded", reason="在相同设备、班次、日期等条件内比较后，关系明显减弱或反向。")
    else:
        result.update(status="candidate", reason="存在待验证的分布差异；需结合多因素验证和现场试验。")
    return result


def evidence_report(factors, model):
    entries = []
    evaluation_name = "测试集" if model.get("evaluation_set") == "test" else "验证集"
    labels = {"candidate": "待验证候选", "confounded": "受条件混杂影响", "constant": "缺少变化", "no_difference":"差异较弱",
              "limited_sources": "独立物料不足", "low_coverage": "覆盖不足", "insufficient": "证据不足"}
    for factor in factors:
        evidence = [factor["reason"]]
        if factor["distribution_effect"] is not None:
            evidence.append(f"分布区分效应 {factor['distribution_effect']:.3f}（0为无差异，1为完全区分）。")
            evidence.append(f"多个上游码的极差分布区分效应 {factor['spread_effect']:.3f}。")
        if factor["target_relation"]["spearman"] is not None:
            evidence.append(f"与目标数值的Spearman关联 {factor['target_relation']['spearman']:.3f}，用于描述单调联系，不能单独证明因果。")
        adjustment = factor["adjustment"]
        if adjustment and adjustment["adjusted_risk_difference"] is not None:
            evidence.append(f"可比条件内高于/不高于中位数的NG占比差 {adjustment['adjusted_risk_difference']*100:.2f} 个百分点，覆盖{adjustment['matched_products']}个产品。")
        if factor["stability"]["status"] == "insufficient":
            evidence.append("尚无足够跨日期复现证据。")
        if model["status"] != "completed":
            evidence.append(f"尚未完成留出{evaluation_name}的多因素模型评估。")
        elif factor["field_id"] not in model.get("selected_fields",[]):
            evidence.append(f"该字段未入选本轮训练候选，尚无该字段的{evaluation_name}模型证据。")
        elif model.get("average_precision_gain",0) <= .01:
            evidence.append("该字段参加了模型，但本轮上游因素整体相对生产上下文基线的额外预测增益有限。")
        entries.append({"field_id": factor["field_id"], "name": factor["name"], "process_name": factor["process_name"],
                        "status": labels[factor["status"]], "evidence": evidence,
                        "hypothesis": ("推荐阶段工艺假设（待工程师核实）："+factor["mechanism_hypothesis"] if factor.get("mechanism_hypothesis")
                                       else f"{factor['process_name']}的{factor['name']}变化可能与当前NG有关，工艺机制待工程师确认。"),
                        "alternatives": "检查设备、时间、配方/工单及共同变化因素；观测差异不能单独证明调参效果。",
                        "action": "在批准的工艺范围内设计对照，明确调整项、保持条件、前后NG/总数，并在独立批次复验。",
                        "causal_status": "unconfirmed"})
    return {"conclusion": "当前输出为根因候选与验证证据，现场验证完成前不确认根因。", "factors": entries}


def analyze_root_causes(products, inputs, boxes, progress=None, *, target_column=None, model_inputs=None, model_preprocessor=None):
    if progress:
        progress.emit("screening", "正在筛选上游候选因素并比较设备、班次等可比条件")
    factors = [screen_factor(data, products, box, target_column) for data,box in zip(inputs, boxes)]
    tested = sorted([f for f in factors if f["p_value"] is not None], key=lambda f: f["p_value"])
    running = 1.0
    for index in range(len(tested)-1, -1, -1):
        running = min(running, tested[index]["p_value"]*len(tested)/(index+1))
        tested[index]["q_value"] = running
    factors.sort(key=lambda f: (f["status"] != "candidate", -f["score"]))
    from .rca_model import fit_validated_model
    from .deep_progress import AnalysisCancelled
    try:
        model = (fit_validated_model(products,model_inputs or inputs,progress,preprocessor=model_preprocessor)
                 if model_preprocessor else fit_validated_model(products,inputs,progress))
    except AnalysisCancelled:
        raise
    except Exception as exc:
        logger.error("NG root cause model failed (%s)",type(exc).__name__)
        model = {"status":"failed", "reason":"模型阶段暂时未完成，已保留目标画像与候选证据；请检查后端分析依赖及日志后重试。",
                 "note":"当前没有完成验证集评估的模型证据，不能根据候选排序确认根因。",
                 "contributions":[],"interactions":[],"train_products":0,"validation_products":0,"test_products":0,"purged_products":0,
                 "evaluation_set":"validation", "sample_unit":"target_product",
                 "training":{"iterations":1000,"early_stopping":False},
                 "baseline":None,"augmented":None,"cross_date":False,"validation":"chronological_70_30"}
    contributions = {row["field_id"]: row["mean_abs_shap"] for row in model.get("contributions", [])}
    for factor in factors:
        factor["model_contribution"] = contributions.get(factor["field_id"])
    if progress:
        progress.emit("report", "正在生成候选根因证据与现场验证建议")
    return {"version": 1, "label": "current_defect_NG_vs_confirmed_OK", "factors": factors, "model": model,
            "report": evidence_report(factors, model),
            "methods": ["筛选和模型均以目标产品为单位；多个上游码以中位数与极差构造模型特征，原图仍使用全部关联值。",
                        "分布效应为KS距离；独立编码未复用时另给Mann–Whitney检验及BH校正，共享物料不输出伪独立p值。",
                        "条件内占比差为探索性分层关联，不是因果效应；分层控制租户、产线、设备、班次、日期和工单。",
                        "模型按目标产品一行构建；不同产品共享上游码时分别保留，不剔除重叠物料。只使用上游特征及生产上下文，不将目标数值、NG判定或产品条码作为输入。",
                        "按目标结束时间以7:3划分训练集和验证集，同一时点不拆分。训练集按中位数/极差分布效应选最多12个字段；固定训练1000轮，验证集仅计算ROC-AUC、AP和SHAP，不参与训练或轮数选择。",
                        "统计阈值用于证据筛选，不构成因果成立条件；无变化、样本不足或无可比条件时明确保留不足状态。"]}
