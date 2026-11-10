import { Coins, Factory, Gauge, ShieldCheck, type LucideIcon } from 'lucide-react';
import type { BiAnalysisDomain } from './types';

export interface ProductionBiAgent {
  id: string;
  name: string;
  category: string;
  icon: LucideIcon;
  description: string;
  suggestions: readonly string[];
  endpoint?: string;
  footerText?: string;
  analysisDomain?: BiAnalysisDomain;
  tenantId?: string;
}

// 业务分类和推荐问题依据 bi_app/table_intent_config.py；四个入口共用 BI 查询接口。
export const PRODUCTION_BI_AGENTS = [
  {
    id: 'manufacturing-bi-analysis',
    analysisDomain: 'manufacturing',
    name: '制造BI分析智能体',
    category: '制造',
    icon: Factory,
    description: '查询电芯与PACK投入产出计划完成率、劳动生产率、物料消耗及批次结批情况。',
    suggestions: [
      '查询本月电芯计划投入、实际投入及投入完成率',
      '分析最近30天电芯计划产出与实际产出的差异',
      '查询本月PACK计划产出、实际产出及产出完成率',
      '查询本周出勤工时、劳动工时和劳产率',
      '统计上月物料的生产损耗、材料净消耗与理论用量',
      '查询本月电芯利用率及电芯上线数量、装包数量',
    ],
  },
  {
    id: 'quality-bi-analysis',
    analysisDomain: 'quality',
    name: '品质BI分析智能体',
    category: '品质',
    icon: ShieldCheck,
    description: '查询订单A品率、A品与非A品产出，以及问题预警、处理和关闭情况。',
    suggestions: [
      '查询本月各订单的A品率并按A品率排序',
      '统计本周各订单的总投入数、总产出数、A品产出数和非A品产出数',
      '查询本月问题关闭率及预警数量、已处理数量、未处理数量',
    ],
  },
  {
    id: 'cost-bi-analysis',
    analysisDomain: 'cost',
    name: '成本BI分析智能体',
    category: '成本',
    icon: Coins,
    description: '分析各工段耗电、合浆投入电量、物料成本、能耗成本及电芯和PACK制费。',
    suggestions: [
      '统计本月各工段耗电量并对各设备类型按耗电量排序',
      '查询本月合浆投入电量、合格率和实际投入电量',
      '查询物料库存数量、备件单价和备件总价',
      '分析最近30天总耗电量与电费变化',
      '查询本月成本明细中的期间费用、电芯制费和PACK制费',
    ],
  },
  {
    id: 'equipment-bi-analysis',
    analysisDomain: 'equipment',
    name: '设备BI分析智能体',
    category: '设备',
    icon: Gauge,
    description: '分析设备OEE、时间与性能稼动率、停机故障、MTBF及MTTR等运行指标。',
    suggestions: [
      '查询本月各设备OEE并按OEE排序',
      '分析本周设备时间稼动率、性能稼动率和合格品率',
      '统计最近30天每天各个设备总运行时间、总故障时间、故障次数、MTBF和MTTR',
      '查询本周设备总主动停机时间、总待料时间和总堵料时间',
    ],
  },
] as const satisfies readonly ProductionBiAgent[];

