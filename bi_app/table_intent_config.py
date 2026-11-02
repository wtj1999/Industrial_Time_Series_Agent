# -*- coding: utf-8 -*-
"""表意图与指标清单配置（供问题改写节点做多轮意图识别/指标变更判断使用）

独立于 table_name_config.py：table_name_config.py 只描述表字段结构，
本文件描述每张数据表的业务意图及其可查询的指标清单。
"""

table_intent_dict = {
    # 制造
    "completion_ratio_input": {
        "intent": "电芯投入计划完成",
        "metrics": ["电芯计划投入", "电芯实际投入", "电芯投入完成率"],
    },

    "completion_ratio_output": {
        "intent": "电芯产出计划完成",
        "metrics": ["电芯计划产出", "电芯实际产出", "电芯产出完成率"],
    },

    "completion_ratio_output_pack": {
        "intent": "PACK产出计划完成",
        "metrics": ["PACK计划产出", "PACK实际产出", "PACK产出完成率"]
    },

    "labor_productivity_ratio": {
        "intent": "劳动生产率",
        "metrics": ["出勤工时", "劳动工时", "总电芯电量", "劳产率"],
    },

    "production_scrap_material": {
        "intent": "物料消耗",
        "metrics": ["生产损耗", "固废损耗", "电池损耗", "材料净消耗", "出库数量",
                    "期初原材料库存数量", "期末原材料库存数量", "期初WIP库存数量", "期末WIP库存数量",
                    "期初浆料库存数量", "期末浆料库存数量", "合格品产出消耗", "工序利用消耗", "理论用量"],
    },

    "production_pack_original": {
        "intent": "电芯利用率",
        "metrics": ["合浆投入数量", "A品数量", "电芯上线数量", "电芯装包数量", ],
    },

    "production_batch_finish": {
        "intent": "电芯批次结批情况（投入产出、报废与结批误差）",
        "metrics": ["当日投入", "激光刻码投入", "OCV3产出", "报废", "误差", "临界误差"],
    },

    "production_produce_original": {
        "intent": "电芯生产批次投入产出情况",
        "metrics": ["当日投入数", "OCV3工序产出", "报废"],
    },

    # 品质
    "quality_dm_order_alevel_rate_di": {
        "intent": "订单A品率",
        "metrics": ["总投入数", "总产出数", "A品产出数", "非A品产出数"],
    },

    "problem_close": {
        "intent": "问题关闭率",
        "metrics": ["预警数量", "已处理数量", "未处理数量"],
    },

    # 成本
    "ems_dm_analysis_power_di": {
        "intent": "各工段耗电量",
        "metrics": ["耗电量"],
    },

    "ems_input_rate_di": {
        "intent": "合浆投入电量",
        "metrics": ["投入电量", "合格率", "实际投入电量"],
    },

    "material_cost": {
        "intent": "物料成本",
        "metrics": ["库存数量", "备件解密单价", "备件加密单价", "备件总价"],
    },

    "ems_dm_analysis_power_cost": {
        "intent": "总能耗成本",
        "metrics": ["耗电量", "花费", "电费"],
    },

    "production_cost_detail": {
        "intent": "成本明细",
        "metrics": ["费用", "成本", "期间费用", "电芯制费", "PACK制费"],
    },

   # 设备
    "iot_oee_dm_metric_aggr_wide_di": {
        "intent": "设备OEE效率",
        "metrics": ["计划不生产时间", "负荷时间", "停机时间", "稼动时间", "时间稼动率",
                    "基准节拍", "实际节拍", "性能稼动率", "产出数", "合格数", "合格品率",
                    "OEE", "总运行时间", "总故障时间", "故障次数", "MTBF", "MTTR",
                    "总主动停机时间", "总待料堵料时间", "总异常数据时间", "总待料时间", "总堵料时间"],
    },

}
