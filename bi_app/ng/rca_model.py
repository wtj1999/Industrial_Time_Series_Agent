"""Target-product datasets with chronological 70/30 splits and fixed 1000-round training."""

from collections import Counter

from .root_cause import CONTROLS, context_value

MAX_ITERATIONS = 1000


def temporal_split(products, indices):
    """Keep equal timestamps together; retain products sharing upstream codes."""
    indices = sorted(indices, key=lambda i: (products[i]["_anchor"], products[i]["_key"]))
    if len(indices) < 80:
        return [], []
    training_end = products[indices[len(indices)*7//10]]["_anchor"]
    return ([i for i in indices if products[i]["_anchor"] < training_end],
            [i for i in indices if products[i]["_anchor"] >= training_end])


def fit_validated_model(products, inputs, progress=None, *, preprocessor=None):
    result = {"status": "insufficient", "reason": "暂无足够的可用候选因素或NG/OK样本。", "contributions": [], "interactions": [],
              "train_products": 0, "validation_products": 0, "test_products": 0, "purged_products": 0,
              "baseline": None, "augmented": None, "validation": "chronological_70_30", "cross_date": False,
              "evaluation_set": "validation", "sample_unit": "target_product", "shared_material_policy": "retain_each_target_product",
              "split_ratios": {"train": .7, "validation": .3},
              "training": {"iterations": MAX_ITERATIONS, "early_stopping": False},
              "note": "SHAP解释验证集预测依据，不能解释为因果贡献；验证集不参与选因、清洗阈值拟合、训练或轮数选择。不同目标产品共享上游码时分别保留。"}
    result["selected_fields"] = []
    if not inputs:
        return result
    members = [(i,p) for i,p in enumerate(products) if p["_group"] in {"NG", "OK"}]
    initial_train, initial_validation = temporal_split(products, [i for i,p in members])
    result["initial_split_products"] = {"train": len(initial_train), "validation": len(initial_validation)}
    if not initial_train or not initial_validation:
        return {**result, "reason": "产品数量或不同目标时点不足，无法按时间构建非空的7:3训练集和验证集；同一时点不会拆分。"}
    if preprocessor:
        inputs,cleaning = preprocessor(products,inputs,initial_train,initial_validation)
        result["statistical_cleaning"] = cleaning
    available = []
    for data in inputs:
        rows = [data["samples"][products[i]["_key"]] for i in initial_train if products[i]["_key"] in data["samples"]]
        if (len(rows) >= max(40, len(initial_train)*.5)
                and any(len({s[key] for s in rows}) > 1 for key in ("median", "spread"))):
            available.append(data)
    if not available:
        return {**result, "reason": "训练数据中没有同时具备变化和足够覆盖的上游因素。"}
    # Only training labels rank candidates; shared upstream codes never remove target products.
    from scipy.stats import ks_2samp
    ranked = []
    for data in available:
        covered = {g:[data["samples"][products[i]["_key"]] for i in initial_train
                      if products[i]["_group"] == g and products[i]["_key"] in data["samples"]] for g in ("NG","OK")}
        if min(map(len, covered.values())) >= 5:
            score = max(float(ks_2samp([s[key] for s in covered["NG"]], [s[key] for s in covered["OK"]]).statistic)
                        for key in ("median", "spread"))
            ranked.append((score,data))
    selected = [data for score,data in sorted(ranked, key=lambda item:(-item[0],item[1]["field"]["id"]))[:12]]
    result["selected_fields"] = [d["field"]["id"] for d in selected]
    result["selection_method"] = "training_only_median_and_spread_KS_top12_by_target_product"
    complete = {i for i,p in members if selected and all(p["_key"] in data["samples"] for data in selected)}
    train = [i for i in initial_train if i in complete]
    validation = [i for i in initial_validation if i in complete]
    result.update(complete_products=len(complete), train_products=len(train), validation_products=len(validation))
    result["missing_products"] = {"train": len(initial_train)-len(train), "validation": len(initial_validation)-len(validation)}
    counts = lambda indices: dict(Counter(products[i]["_group"] for i in indices))
    result.update(train_counts=counts(train), validation_counts=counts(validation))
    if len(complete) > 50000:
        return {**result, "reason": "完整模型样本超过50000个，请缩小范围；画像与单因素统计仍使用全量数据。"}
    if min([counts(indices).get(g,0) for indices in (train,validation) for g in ("NG","OK")], default=0) < 10:
        return {**result, "reason": "清洗后训练集或验证集的NG/OK少于10个，暂无法完成验证集评估。"}
    training_dates = {context_value(products[i], "shift_date") for i in train}
    validation_dates = {context_value(products[i], "shift_date") for i in validation}
    result["cross_date"] = training_dates.isdisjoint(validation_dates) and "未知" not in training_dates|validation_dates
    for name,indices in (("train",train),("validation",validation)):
        result[name+"_period"] = [str(min(products[i]["_anchor"] for i in indices)), str(max(products[i]["_anchor"] for i in indices))]
    if progress:
        progress.emit("modeling", f"7:3样本已划分 · 训练{len(train)}、验证{len(validation)}；固定训练{MAX_ITERATIONS}轮，共享上游码产品保留")
    from catboost import CatBoostClassifier, Pool
    import numpy as np
    from sklearn.metrics import roc_auc_score, average_precision_score
    # Both models use the same training rows. No holdout pool is supplied to fit().
    controls = [name for name in CONTROLS if name != "shift_date"]
    origin = min(products[i]["_anchor"] for i in train)
    def context(i):
        p = products[i]
        return [(p["_anchor"]-origin).total_seconds()/3600, *[context_value(p,k) for k in controls]]
    def features(i):
        return [v for data in selected for v in (data["samples"][products[i]["_key"]]["median"],
                                                  data["samples"][products[i]["_key"]]["spread"])]
    numeric_count = 2*len(selected)
    def pool(indices, augmented):
        offset = numeric_count if augmented else 0
        x = [(features(i) if augmented else [])+context(i) for i in indices]
        return Pool(x, [int(products[i]["_group"] == "NG") for i in indices],
                    cat_features=list(range(offset+1, offset+1+len(controls))))
    class ProgressCallback:
        def __init__(self, label):
            self.label = label
        def after_iteration(self, info):
            if progress and progress.cancelled.is_set():
                return False
            if progress and info.iteration % 40 == 0:
                progress.emit("modeling", f"{self.label}训练 · {info.iteration}/{MAX_ITERATIONS}轮")
            return True
    models = []
    for augmented in (False, True):
        training = pool(train, augmented)
        model = CatBoostClassifier(iterations=MAX_ITERATIONS, depth=4, learning_rate=.06, random_seed=42,
                                   thread_count=4, loss_function="Logloss", eval_metric="Logloss", verbose=False, allow_writing_files=False)
        model.fit(training, use_best_model=False,
                  callbacks=[ProgressCallback("多因素模型" if augmented else "生产上下文基线")])
        if progress:
            progress.check()
        run = {"tree_count": int(model.tree_count_),
               "trained_iterations": len(model.get_evals_result()["learn"]["Logloss"])}
        if run["tree_count"] != MAX_ITERATIONS or run["trained_iterations"] != MAX_ITERATIONS:
            raise RuntimeError("Model did not complete the fixed training iterations")
        result["training"]["augmented" if augmented else "baseline"] = run
        if progress:
            progress.emit("modeling", f"{'多因素模型' if augmented else '生产上下文基线'}训练完成 · 固定{run['tree_count']}轮")
        if progress:
            progress.check()
        models.append(model)
    if progress:
        progress.emit("validation", f"两模型均已完成{MAX_ITERATIONS}轮训练，正在计算验证集ROC-AUC、AP及SHAP")
    metrics = []
    y = [int(products[i]["_group"] == "NG") for i in validation]
    for augmented, model in zip((False, True), models):
        predictions = model.predict_proba(pool(validation, augmented))[:,1]
        metrics.append({"roc_auc": float(roc_auc_score(y, predictions)), "average_precision": float(average_precision_score(y, predictions)),
                        "NG_share": sum(y)/len(y)})
    shap = models[1].get_feature_importance(pool(validation, True), type="ShapValues", thread_count=4)
    importance = np.abs(shap[:,:-1]).mean(axis=0)
    contributions = [{"field_id":data["field"]["id"], "name":data["field"]["name"],
                      "mean_abs_shap":float(importance[2*i]+importance[2*i+1])} for i,data in enumerate(selected)]
    interactions = []
    for a,b,strength in models[1].get_feature_importance(type="Interaction"):
        a,b = int(a),int(b)
        if a < numeric_count and b < numeric_count and a//2 != b//2:
            ids = sorted({selected[a//2]["field"]["id"],selected[b//2]["field"]["id"]})
            if not any(row["field_ids"] == ids for row in interactions):
                interactions.append({"field_ids":ids,"strength":float(strength),"status":"exploratory"})
        if len(interactions) >= 5:
            break
    gain = metrics[1]["average_precision"]-metrics[0]["average_precision"]
    return {**result, "status":"completed", "reason":f"已完成7:3时间划分、固定{MAX_ITERATIONS}轮训练和验证集评估；因果关系仍待现场验证。",
            "baseline":metrics[0], "augmented":metrics[1], "average_precision_gain":gain,
            "contributions":sorted(contributions,key=lambda r:-r["mean_abs_shap"]), "interactions":interactions,
            "assessment":"上游因素在验证集提供额外预测信息" if gain > .01 else "相对生产上下文基线，额外预测增益有限"}
