import { ScanSearch } from 'lucide-react';
import type { ProductionBiAgent } from '../production-bi-analysis/config';

export const NG_DEFECT_AGENT = {
  id: 'ng-defect-analysis',
  name: '不良品类型分析智能体',
  category: 'NG类型',
  icon: ScanSearch,
  description: '查询一次合格口径下的NG数量，支持按日期、设备、工序、产线、班次等维度筛选和分组统计。',
  endpoint: '/api/bi/ng/query',
  footerText: '金寨三期工厂 · 先确认日期和筛选条件，再汇总NG类型数量',
  suggestions: [
    '统计近七日的NG类型和数量',
    '查询昨天各NG类型的数量分布',
    '统计本月一次合格口径下的NG数量',
    '统计近七日切卷工序每台设备的不良数量',
    '统计近七日切卷工序每天的不良数量',
  ],
} as const satisfies ProductionBiAgent;
