import { ClipboardList } from 'lucide-react';

export const CONTROL_PLAN_AGENT = {
  id: 'control-plan-analysis',
  name: '锂电产线Control Plan分析智能体',
  category: 'Control Plan',
  icon: ClipboardList,
  description: '按基地和路线查询工艺参数及标准范围，结合 LLM 分析参数标准、检验要求并给出核查建议。',
  suggestions: ['滁州正极涂布参数', '查询锂电产线工艺参数和标准范围'],
} as const;
