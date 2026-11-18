"""Read-only benchmark of the same product-batch queries used by the API.

Example: python -m bi_app.ng.benchmark_deep --start-date 2026-11-15
  --end-date 2026-11-15 --ng-type NG-E-YCHJ006 --target-id <catalog ID>
  --feature-id <catalog ID> --output bi_app/ng/data/query_benchmark.json
"""

import argparse
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

from .catalog import NgCatalog, write_json
from .config import NG_FACTORIES, get_ng_factory_settings
from .deep import NgDeepService
from .deep_repository import NgDeepRepository
from .errors import NgError
from .genealogy import resolve_genealogy
from .repository import NgRepository
from .schemas import NgFilters, NgParameters


def run_benchmark(settings, context, target, features, *, worker_counts=(1, 8), repeat=2, catalog=None):
    repository = NgDeepRepository(NgRepository(settings))
    products, target_timing = repository.targets(context, target)
    trace = resolve_genealogy(repository, products, target, features, catalog)
    runs = []
    for iteration in range(repeat):
        # Alternate order to reduce the effect of a warmed database cache.
        counts = worker_counts if iteration % 2 == 0 else tuple(reversed(worker_counts))
        for workers in counts:
            started = time.perf_counter()
            try:
                _, timings, elapsed = repository.features(products, features, workers=workers)
                run = {"status": "success", "iteration": iteration + 1, "workers": workers, "feature_wall_seconds": elapsed,
                       "client_wall_seconds": round(time.perf_counter() - started, 4), "query_count": len(timings),
                       "rows": sum(query["rows"] for query in timings), "queries": timings}
            except NgError as exc:
                run = {"status": "failed", "iteration": iteration + 1, "workers": workers,
                       "client_wall_seconds": round(time.perf_counter() - started, 4), "error": str(exc)}
            runs.append(run)
            print(json.dumps({key: value for key, value in run.items() if key != "queries"}), flush=True)
    comparison = repository.analyze(context, target, features, catalog=catalog)
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "factory_id": settings.factory_id, "period": context["parameters"], "filters": context["filters"],
            "ng_type": context["row"]["ng_type"], "target": {"id": target["id"], "name": target["name"]},
            "features": [{"id": field["id"], "name": field["name"], "process_name": field["process"]["name"]} for field in features],
            "batch_size": settings.deep_product_batch_size, "target_query": target_timing, "trace": trace, "runs": runs,
            "comparison": comparison,
            "notes": ["只读真实数据库，目标全量取数，无随机抽样；配置ADS的工厂按路线保留全部上游物料码，逐码取数；其他工厂沿用直接编码或唯一投入编码关联。",
                      "串行与并发使用相同产品集合及字段，交替测试顺序；耗时受网络、服务端缓存和负载影响。",
                      "报告不包含产品编码或原始生产明细。"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factory", choices=list(NG_FACTORIES), default="jinzhai-phase-3")
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument("--ng-type", required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--feature-id", action="append", required=True)
    parser.add_argument("--filters-json", default="{}")
    parser.add_argument("--repeat", type=int, choices=range(1, 6), default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = get_ng_factory_settings(args.factory)
    catalog = NgCatalog(NgRepository(settings), args.factory).load()
    fields = {field["id"]: field for field in NgDeepService.fields(catalog)}
    target = fields[args.target_id]
    features = [fields[key] for key in dict.fromkeys(args.feature_id)]
    if any(field["process"]["order"] >= target["process"]["order"] for field in features):
        parser.error("特征必须来自目标工序之前")
    parameters = NgParameters(start_date=args.start_date, end_date=args.end_date)
    filters = NgFilters.model_validate(json.loads(args.filters_json))
    context = {"parameters": parameters.model_dump(mode="json"), "filters": filters.nonempty(), "row": {"ng_type": args.ng_type, "ng_name": args.ng_type}}
    report = run_benchmark(settings, context, target, features, worker_counts=(1, settings.deep_query_workers), repeat=args.repeat, catalog=catalog)
    write_json(args.output, report)
    print(json.dumps({"report": str(args.output), "counts": report["comparison"]["counts"]}), flush=True)


if __name__ == "__main__":
    main()
